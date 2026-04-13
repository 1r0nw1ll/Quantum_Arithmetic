#!/usr/bin/env python3
"""Molecular graph classification via QA-native graph-graph kernels.

Extends molecular_bench.py with native kernels at the GRAPH level:

    1. Eisenstein graph kernel: K(G1, G2) = exp(-|μ_eis(G1) - μ_eis(G2)| / τ)
       where μ_eis(G) = mean Eisenstein norm over nodes
    2. Family histogram kernel: K(G1, G2) = cosine(family_hist(G1), family_hist(G2))
       where family_hist counts nodes per Pythagorean family
    3. Combined molecular kernel: weighted product of Eisenstein + family + degree-distribution

Compares against the prior aggregation-based features (mean+std of node features).

Domain-natural mapping (proven from molecular_bench.py):
    b = atom_degree   # QA_MAP: spatial bond count
    e = atom_type     # QA_MAP: amino acid type (1-indexed from one-hot)
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=molecular_native_kernel, state_alphabet=protein_graph_classification, tier=graph_graph_kernels"

import json
import sys
from pathlib import Path
from collections import Counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_graph.signed_temporal import eisenstein_norm
from qa_graph.diophantine_features import full_qa_feature_vector

HERE = Path(__file__).resolve().parent
np.random.seed(42)


# ── Data loading (reuse from molecular_bench) ───────────────────────────────

def load_tu_dataset(name="PROTEINS"):
    from torch_geometric.datasets import TUDataset
    from torch_geometric.utils import degree

    ds = TUDataset(root="/tmp/TU_data", name=name)
    graphs = []
    for i in range(len(ds)):
        g = ds[i]
        n = g.num_nodes
        degs = degree(g.edge_index[0], num_nodes=n).int().tolist()
        if g.x is not None and g.x.shape[1] > 0:
            types = (g.x.argmax(dim=1) + 1).int().tolist()
        else:
            types = [1] * n
        graphs.append({
            "num_nodes": n, "degrees": degs, "types": types,
            "label": g.y.item(),
        })
    return graphs, ds.num_classes


# ── Per-graph QA descriptors ────────────────────────────────────────────────

NORM_MOD9_TO_FAMILY_IDX = {
    1: 0, 8: 0,    # Fibonacci
    4: 1, 5: 1,    # Lucas
    2: 2, 7: 2,    # Phibonacci
    0: 3,          # null
    3: 4, 6: 4,    # other
}
N_FAMILIES = 5


def graph_qa_descriptor(graph):
    """Compute graph-level QA descriptor: per-node Eisenstein + family hist + degree dist."""
    n = graph["num_nodes"]
    norms = []
    families = np.zeros(N_FAMILIES, dtype=float)
    degrees = []

    for v in range(n):
        b = max(1, int(graph["degrees"][v]))   # QA_MAP: b=atom degree (bond count)
        e = max(1, int(graph["types"][v]))     # QA_MAP: e=atom type
        norm = eisenstein_norm(b, e)
        norms.append(norm)
        fam_idx = NORM_MOD9_TO_FAMILY_IDX.get(norm % 9, 4)
        families[fam_idx] += 1
        degrees.append(b)

    norms = np.array(norms, dtype=float)
    families = families / max(1, n)  # normalize to fraction
    deg_hist, _ = np.histogram(degrees, bins=10, range=(1, 11))
    deg_hist = deg_hist.astype(float) / max(1, n)

    return {
        "n": n,
        "eisenstein_mean": float(norms.mean()),
        "eisenstein_std": float(norms.std()),
        "eisenstein_skew": float((((norms - norms.mean()) ** 3).mean()) / (norms.std() ** 3 + 1e-9)),
        "family_hist": families,
        "degree_hist": deg_hist,
        "mean_degree": float(np.mean(degrees)),
        "std_degree": float(np.std(degrees)),
    }


# ── Graph-graph kernels ─────────────────────────────────────────────────────

def eisenstein_graph_kernel(descriptors, tau=None):
    """Pairwise kernel based on Eisenstein mean+std difference."""
    n = len(descriptors)
    eis_mean = np.array([d["eisenstein_mean"] for d in descriptors])
    eis_std = np.array([d["eisenstein_std"] for d in descriptors])
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            d_mean = abs(eis_mean[i] - eis_mean[j])
            d_std = abs(eis_std[i] - eis_std[j])
            K[i, j] = d_mean + d_std
    if tau is None:
        tau = np.median(K[K > 0]) if np.any(K > 0) else 1.0
    return np.exp(-K / tau)


def family_histogram_kernel(descriptors):
    """Cosine similarity of family histograms."""
    n = len(descriptors)
    H = np.array([d["family_hist"] for d in descriptors])  # (n, 5)
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    norms[norms < 1e-10] = 1.0
    H_norm = H / norms
    return H_norm @ H_norm.T


def degree_distribution_kernel(descriptors):
    """Histogram intersection on degree distributions."""
    n = len(descriptors)
    H = np.array([d["degree_hist"] for d in descriptors])
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            K[i, j] = float(np.minimum(H[i], H[j]).sum())
    return K


def combined_molecular_kernel(descriptors, weights=(0.4, 0.3, 0.3)):
    """Weighted product of Eisenstein + family + degree kernels."""
    w_e, w_f, w_d = weights
    K = (w_e * eisenstein_graph_kernel(descriptors) +
         w_f * family_histogram_kernel(descriptors) +
         w_d * degree_distribution_kernel(descriptors))
    return K


# ── Kernel SVM via dual formulation (numpy only) ────────────────────────────

def kernel_logreg_cv(K, y, n_folds=10, lam=0.1, seed=42):
    """Kernel logistic regression via dual representation, 10-fold CV.

    Solves (K_train + λI) α = (y - 0.5), then predicts via K_test @ α.
    Multi-class via one-vs-rest.
    """
    n = len(y)
    rng = np.random.RandomState(seed)
    indices = rng.permutation(n)
    fold_size = n // n_folds

    classes = sorted(set(y))
    n_classes = len(classes)
    class_map = {c: i for i, c in enumerate(classes)}
    y_mapped = np.array([class_map[yi] for yi in y])

    accs = []
    for fold in range(n_folds):
        test_idx = indices[fold * fold_size: (fold + 1) * fold_size]
        train_idx = np.array([i for i in indices if i not in set(test_idx)])

        K_train = K[np.ix_(train_idx, train_idx)]
        K_test = K[np.ix_(test_idx, train_idx)]

        # Center kernel
        n_train = len(train_idx)
        scores = np.zeros((len(test_idx), n_classes))

        for c in range(n_classes):
            y_bin = (y_mapped[train_idx] == c).astype(float) - 0.5
            try:
                A = K_train + lam * n_train * np.eye(n_train)
                alpha = np.linalg.solve(A, y_bin)
                scores[:, c] = K_test @ alpha
            except np.linalg.LinAlgError:
                scores[:, c] = 0

        preds = scores.argmax(axis=1)
        accs.append(float((preds == y_mapped[test_idx]).mean()))

    return {"mean_acc": round(float(np.mean(accs)), 4),
            "std_acc": round(float(np.std(accs)), 4)}


# ── Main ────────────────────────────────────────────────────────────────────

def run_dataset(name):
    print(f"\n=== {name} ===")
    graphs, n_classes = load_tu_dataset(name)
    n = len(graphs)
    print(f"Loaded {n} graphs, {n_classes} classes")

    print("Computing per-graph QA descriptors...")
    descriptors = [graph_qa_descriptor(g) for g in graphs]
    labels = np.array([g["label"] for g in graphs])

    results = {"dataset": name, "n": n, "n_classes": n_classes}

    # Build kernels
    print("Building kernels...")
    K_eis = eisenstein_graph_kernel(descriptors)
    K_fam = family_histogram_kernel(descriptors)
    K_deg = degree_distribution_kernel(descriptors)
    K_combined = combined_molecular_kernel(descriptors)

    for kname, K in [("eisenstein", K_eis), ("family_hist", K_fam),
                      ("degree_hist", K_deg), ("combined", K_combined)]:
        cv = kernel_logreg_cv(K, labels.tolist())
        results[kname] = cv
        print(f"  {kname:15s}: acc = {cv['mean_acc']:.4f} ± {cv['std_acc']:.4f}")

    # Compare to baseline accuracy from molecular_bench.py (logged from prior run)
    prior_baselines = {"PROTEINS": {"degree_only": 0.6964, "qa102": 0.7351},
                       "ENZYMES":  {"degree_only": 0.2450, "qa102": 0.2983}}
    if name in prior_baselines:
        results["prior_baselines"] = prior_baselines[name]
        print(f"  prior degree_only baseline: {prior_baselines[name]['degree_only']:.4f}")
        print(f"  prior qa102 baseline:       {prior_baselines[name]['qa102']:.4f}")

        for kname, _ in [("eisenstein", None), ("family_hist", None),
                          ("degree_hist", None), ("combined", None)]:
            delta_d = results[kname]["mean_acc"] - prior_baselines[name]["degree_only"]
            delta_q = results[kname]["mean_acc"] - prior_baselines[name]["qa102"]
            results[kname]["delta_vs_degree_only"] = round(delta_d, 4)
            results[kname]["delta_vs_qa102"] = round(delta_q, 4)
            marker = " ←" if delta_q > 0.005 else (" ✗" if delta_q < -0.005 else "")
            print(f"  {kname:15s}: Δ vs qa102 = {delta_q:+.4f}{marker}")

    return results


def main():
    print("=== Molecular Graph-Graph Native Kernel Benchmark ===")
    all_results = {}
    for ds_name in ("PROTEINS", "ENZYMES"):
        all_results[ds_name] = run_dataset(ds_name)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for ds_name, r in all_results.items():
        print(f"\n{ds_name}:")
        prior_q102 = r.get("prior_baselines", {}).get("qa102", 0)
        print(f"  prior qa102 (mean+std features):  {prior_q102:.4f}")
        for kname in ("eisenstein", "family_hist", "degree_hist", "combined"):
            acc = r[kname]["mean_acc"]
            d = r[kname].get("delta_vs_qa102", 0)
            marker = " ←" if d > 0.005 else (" ✗" if d < -0.005 else "")
            print(f"  {kname:15s} kernel:  {acc:.4f}  Δ={d:+.4f}{marker}")

    out_path = HERE / "molecular_native_kernel_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
