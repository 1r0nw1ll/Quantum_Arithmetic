#!/usr/bin/env python3
"""Molecular graph-graph kernels v2 — distribution-preserving QA kernels.

Prior v1 lost to per-node aggregation because it compressed each graph to
1-10 numbers (mean Eisenstein, family histogram with 5 bins). This v2 fixes
the information loss by using kernels that preserve the full per-node
distribution:

1. EMD kernel (earth-mover's distance) on per-node Eisenstein norms:
   K(G1, G2) = exp(-EMD(norms_G1, norms_G2) / τ)

2. Weisfeiler-Lehman QA kernel:
   Iteratively update each node's QA label by incorporating neighborhood
   labels. Compare graphs by counting shared WL labels across h iterations.
   This is the standard SOTA for graph classification, QA-enhanced.

3. Rich histogram kernel: 50-bin Eisenstein histogram + 50-bin inradius
   histogram + family histogram, all concatenated. Gives 105+ features
   per graph, comparable to per-node aggregation.

Expected: these should match or beat per-node aggregation on PROTEINS/ENZYMES.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=molecular_native_kernel_v2, state_alphabet=graph_graph_distribution_kernel, tier=WL_EMD_rich_histogram"

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_graph.signed_temporal import eisenstein_norm

HERE = Path(__file__).resolve().parent
np.random.seed(42)


# ── Data loading ────────────────────────────────────────────────────────────

def load_tu_dataset(name):
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
        edge_list = g.edge_index.t().tolist()
        adj = [[] for _ in range(n)]
        for src, dst in edge_list:
            adj[src].append(dst)
        graphs.append({
            "num_nodes": n, "degrees": degs, "types": types,
            "adj": adj, "label": g.y.item(),
        })
    return graphs, ds.num_classes


# ── 1. EMD kernel on per-node Eisenstein distributions ──────────────────────

def per_node_norms(graph):
    """Per-node Eisenstein norms, sorted ascending."""
    n = graph["num_nodes"]
    norms = []
    for v in range(n):
        b = max(1, int(graph["degrees"][v]))   # QA_MAP: b=atom degree
        e = max(1, int(graph["types"][v]))     # QA_MAP: e=atom type
        norms.append(eisenstein_norm(b, e))
    return sorted(norms)


def emd_1d(a, b):
    """1D Earth-mover's distance between sorted distributions.

    Resamples both to common length, then sums absolute diffs.
    """
    n_target = max(len(a), len(b), 20)
    # Linear interpolation to common length
    def resample(arr, n_t):
        arr = np.array(arr, dtype=float)
        if len(arr) == 0:
            return np.zeros(n_t)
        if len(arr) == 1:
            return np.full(n_t, arr[0])
        x_old = np.linspace(0, 1, len(arr))
        x_new = np.linspace(0, 1, n_t)
        return np.interp(x_new, x_old, arr)
    ra, rb = resample(a, n_target), resample(b, n_target)
    return float(np.abs(ra - rb).mean())


def emd_kernel(graphs, tau=None):
    n = len(graphs)
    sigs = [per_node_norms(g) for g in graphs]
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = emd_1d(sigs[i], sigs[j])
            D[i, j] = D[j, i] = d
    if tau is None:
        tau = float(np.median(D[D > 0])) if np.any(D > 0) else 1.0
    return np.exp(-D / tau)


# ── 2. Weisfeiler-Lehman QA kernel ──────────────────────────────────────────

def wl_qa_labels(graph, h=3):
    """Compute WL labels over h iterations, seeded with QA (b,e) pairs.

    Each node starts with label (b_i, e_i). At each iteration, the new
    label is hash((old_label, sorted_neighbor_labels)). Returns a dict
    iteration -> Counter of labels.
    """
    n = graph["num_nodes"]
    adj = graph["adj"]

    # Initial labels: (b, e) per node
    labels = []
    for v in range(n):
        b = max(1, int(graph["degrees"][v]))   # QA_MAP: b=atom degree
        e = max(1, int(graph["types"][v]))     # QA_MAP: e=atom type
        labels.append((b, e))

    histograms = [Counter(labels)]
    for _ in range(h):
        new_labels = []
        for v in range(n):
            nbr_labels = tuple(sorted(labels[u] for u in adj[v]))
            new_labels.append((labels[v], nbr_labels))
        labels = new_labels
        # Hash to small integer keys
        labels = [hash(lab) for lab in labels]
        histograms.append(Counter(labels))

    return histograms


def wl_qa_kernel(graphs, h=3):
    n = len(graphs)
    print(f"  Computing WL-QA labels (h={h})...")
    all_hists = [wl_qa_labels(g, h=h) for g in graphs]

    # Build vocab per iteration
    print(f"  Building vocab and feature matrices...")
    vocabs = []
    for it in range(h + 1):
        vocab = {}
        for g_hist in all_hists:
            for lab in g_hist[it]:
                if lab not in vocab:
                    vocab[lab] = len(vocab)
        vocabs.append(vocab)

    # Build feature matrix per iteration
    feat_matrices = []
    for it in range(h + 1):
        V = len(vocabs[it])
        M = np.zeros((n, V), dtype=float)
        for i, g_hist in enumerate(all_hists):
            for lab, cnt in g_hist[it].items():
                M[i, vocabs[it][lab]] = cnt
        feat_matrices.append(M)

    # Kernel = sum of inner products across iterations
    print(f"  Computing kernel matrix...")
    K = np.zeros((n, n))
    for M in feat_matrices:
        K += M @ M.T

    # Normalize
    K_diag = np.sqrt(np.diag(K))
    K_diag[K_diag < 1e-10] = 1.0
    K = K / np.outer(K_diag, K_diag)

    return K


# ── 3. Rich histogram kernel ────────────────────────────────────────────────

def rich_histogram_features(graph, n_bins=50):
    """50-bin Eisenstein + 50-bin inradius + family histogram + degree moments."""
    n = graph["num_nodes"]
    norms = []
    inradii = []
    families = np.zeros(5, dtype=float)

    for v in range(n):
        b = max(1, int(graph["degrees"][v]))   # QA_MAP: b=degree
        e = max(1, int(graph["types"][v]))     # QA_MAP: e=type
        norm = eisenstein_norm(b, e)
        norms.append(norm)
        inradii.append(b * e)
        fam_map = {1:0, 8:0, 4:1, 5:1, 2:2, 7:2, 0:3}
        families[fam_map.get(norm % 9, 4)] += 1

    norms = np.array(norms, dtype=float)
    inradii = np.array(inradii, dtype=float)

    eis_hist, _ = np.histogram(norms, bins=n_bins, range=(-100, 300))
    inr_hist, _ = np.histogram(inradii, bins=n_bins, range=(0, 100))

    eis_hist = eis_hist.astype(float) / max(1, n)
    inr_hist = inr_hist.astype(float) / max(1, n)
    families = families / max(1, n)

    # Moments
    moments = np.array([norms.mean(), norms.std(),
                        float(((norms - norms.mean())**3).mean() / (norms.std()**3 + 1e-9)),
                        inradii.mean(), inradii.std()])

    return np.concatenate([eis_hist, inr_hist, families, moments])


def rich_histogram_kernel(graphs, tau=None):
    n = len(graphs)
    feats = np.array([rich_histogram_features(g) for g in graphs])
    feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
    mu = feats.mean(0); sig = feats.std(0); sig[sig < 1e-10] = 1.0
    feats = (feats - mu) / sig
    dists = np.sum((feats[:, None, :] - feats[None, :, :])**2, axis=2)
    if tau is None:
        tau = float(np.median(dists[dists > 0])) if np.any(dists > 0) else 1.0
    return np.exp(-dists / (2 * tau))


# ── Kernel classifier ───────────────────────────────────────────────────────

def kernel_logreg_cv(K, y, n_folds=10, lam=0.1, seed=42):
    n = len(y)
    rng = np.random.RandomState(seed)
    indices = rng.permutation(n)
    fold_size = n // n_folds
    classes = sorted(set(y))
    class_map = {c: i for i, c in enumerate(classes)}
    y_mapped = np.array([class_map[yi] for yi in y])
    accs = []
    for fold in range(n_folds):
        test_idx = indices[fold * fold_size: (fold + 1) * fold_size]
        train_idx = np.array([i for i in indices if i not in set(test_idx)])
        K_train = K[np.ix_(train_idx, train_idx)]
        K_test = K[np.ix_(test_idx, train_idx)]
        n_train = len(train_idx)
        scores = np.zeros((len(test_idx), len(classes)))
        for c in range(len(classes)):
            y_bin = (y_mapped[train_idx] == c).astype(float) - 0.5
            try:
                A = K_train + lam * n_train * np.eye(n_train)
                alpha = np.linalg.solve(A, y_bin)
                scores[:, c] = K_test @ alpha
            except np.linalg.LinAlgError:
                pass
        preds = scores.argmax(axis=1)
        accs.append(float((preds == y_mapped[test_idx]).mean()))
    return {"mean_acc": round(float(np.mean(accs)), 4),
            "std_acc": round(float(np.std(accs)), 4)}


# ── Main ────────────────────────────────────────────────────────────────────

def run(name):
    print(f"\n=== {name} ===")
    graphs, n_classes = load_tu_dataset(name)
    n = len(graphs)
    print(f"Loaded {n} graphs")

    labels = [g["label"] for g in graphs]

    results = {"dataset": name, "n": n}
    prior_q102 = {"PROTEINS": 0.7351, "ENZYMES": 0.2983}.get(name, 0)
    prior_deg = {"PROTEINS": 0.6964, "ENZYMES": 0.2450}.get(name, 0)
    print(f"prior degree_only: {prior_deg:.4f}, prior qa102: {prior_q102:.4f}")

    # 1. EMD kernel
    print("\nBuilding EMD kernel...")
    K_emd = emd_kernel(graphs)
    cv = kernel_logreg_cv(K_emd, labels)
    delta = cv["mean_acc"] - prior_q102
    print(f"  EMD kernel: acc={cv['mean_acc']:.4f} Δ vs qa102={delta:+.4f}")
    results["emd"] = {**cv, "delta_vs_qa102": round(delta, 4)}

    # 2. WL-QA kernel
    print("\nBuilding WL-QA kernel (h=3)...")
    K_wl = wl_qa_kernel(graphs, h=3)
    cv = kernel_logreg_cv(K_wl, labels)
    delta = cv["mean_acc"] - prior_q102
    print(f"  WL-QA kernel: acc={cv['mean_acc']:.4f} Δ vs qa102={delta:+.4f}")
    results["wl_qa"] = {**cv, "delta_vs_qa102": round(delta, 4)}

    # 3. Rich histogram kernel
    print("\nBuilding rich histogram kernel...")
    K_rich = rich_histogram_kernel(graphs)
    cv = kernel_logreg_cv(K_rich, labels)
    delta = cv["mean_acc"] - prior_q102
    print(f"  Rich histogram: acc={cv['mean_acc']:.4f} Δ vs qa102={delta:+.4f}")
    results["rich_hist"] = {**cv, "delta_vs_qa102": round(delta, 4)}

    # 4. WL + rich combined
    print("\nCombining WL-QA + rich histogram...")
    # Normalize both to same scale first
    K_wl_n = K_wl / (K_wl.max() + 1e-10)
    K_rich_n = K_rich / (K_rich.max() + 1e-10)
    K_comb = 0.5 * K_wl_n + 0.5 * K_rich_n
    cv = kernel_logreg_cv(K_comb, labels)
    delta = cv["mean_acc"] - prior_q102
    print(f"  Combined: acc={cv['mean_acc']:.4f} Δ vs qa102={delta:+.4f}")
    results["combined"] = {**cv, "delta_vs_qa102": round(delta, 4)}

    return results


def main():
    print("=== Molecular Native Kernels v2 — Distribution-Preserving ===")
    all_results = {}
    for ds in ("PROTEINS", "ENZYMES"):
        all_results[ds] = run(ds)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for ds, r in all_results.items():
        prior_q = {"PROTEINS": 0.7351, "ENZYMES": 0.2983}[ds]
        print(f"\n{ds} (prior qa102 = {prior_q:.4f}):")
        for kname in ("emd", "wl_qa", "rich_hist", "combined"):
            acc = r[kname]["mean_acc"]
            d = r[kname]["delta_vs_qa102"]
            marker = " ←" if d > 0.005 else (" ✗" if d < -0.005 else "")
            print(f"  {kname:15s}: {acc:.4f}  Δ={d:+.4f}{marker}")

    out_path = HERE / "molecular_native_kernel_v2_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
