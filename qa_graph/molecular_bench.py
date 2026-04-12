#!/usr/bin/env python3
"""Molecular graph classification benchmark — PROTEINS + ENZYMES via QA features.

Uses TU datasets (PROTEINS: 1113 graphs, 2 classes; ENZYMES: 600 graphs, 6 classes)
to test whether QA features improve graph-level classification.

Domain-natural (b, e) mapping for protein graphs:
    b = node degree (number of spatial neighbors in the contact graph)
    e = amino acid type index (argmax of one-hot node features + 1, A1-adjusted)

    # QA_MAP: b=degree (spatial neighbors), e=amino_acid_type (1-indexed from
    # one-hot features) — domain-natural for protein structure graphs. Degree
    # captures local connectivity density; amino acid type captures chemical
    # identity. Together they encode the structural-chemical state per residue.

Pipeline:
    1. Load TU dataset via PyTorch Geometric
    2. For each graph: extract (b, e) per node → compute 102 QA features
    3. Aggregate node features to graph level: mean + std (204-dim vector)
    4. 10-fold cross-validation with logistic regression
    5. Report accuracy: baseline (degree-only) vs qa21 vs qa102

QA axiom compliance:
    A1: b ∈ {1..max_degree}, e ∈ {1..num_types}
    A2: d, a derived from b, e (never assigned)
    T2: classification scores are observer-layer; one-hot features are discrete
    S1: b*b not b**2
    S2: (b, e) are integers
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=molecular_graph_classifier, state_alphabet=protein_graph_topology, tier=graph_level_classification"

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_graph.feature_map import qa_feature_vector, compute_qa_invariants
from qa_graph.diophantine_features import full_qa_feature_vector

HERE = Path(__file__).resolve().parent
np.random.seed(42)


# ── Data loading ─────────────────────────────────────────────────────────────

def load_tu_dataset(name="PROTEINS"):
    """Load a TU dataset via PyTorch Geometric. Returns list of graph dicts."""
    from torch_geometric.datasets import TUDataset
    from torch_geometric.utils import degree
    import torch

    ds = TUDataset(root="/tmp/TU_data", name=name)
    graphs = []

    for i in range(len(ds)):
        g = ds[i]
        n = g.num_nodes
        degs = degree(g.edge_index[0], num_nodes=n).int().tolist()
        # Node type from one-hot features
        if g.x is not None and g.x.shape[1] > 0:
            types = (g.x.argmax(dim=1) + 1).int().tolist()  # A1: 1-indexed
        else:
            types = [1] * n

        graphs.append({
            "num_nodes": n,
            "degrees": degs,
            "types": types,
            "label": g.y.item(),
            "edge_index": g.edge_index.tolist(),
        })

    return graphs, ds.num_classes


# ── QA feature extraction ───────────────────────────────────────────────────

def graph_qa_features(graph, mode="full"):
    """Extract QA features per node, aggregate to graph level.

    Domain-natural mapping:
        b = max(1, degree)   # QA_MAP: spatial neighbor count (protein contact graph)
        e = amino_acid_type  # QA_MAP: 1-indexed type from one-hot node features

    Aggregation: mean + std per feature → 2× feature dimension.
    """
    n = graph["num_nodes"]
    node_features = []

    for v in range(n):
        b = max(1, graph["degrees"][v])   # QA_MAP: b=degree (spatial neighbors in contact graph)
        e = max(1, graph["types"][v])     # QA_MAP: e=amino_acid_type (1-indexed one-hot)

        if mode == "qa21":
            vec, names = qa_feature_vector(float(b), float(e), mode="qa21")
            vec = list(vec)
        elif mode == "full":
            vec, names = full_qa_feature_vector(b, e)
        elif mode == "degree_only":
            vec = [float(b), float(e)]
            names = ["degree", "type"]
        else:
            raise ValueError(f"unknown mode {mode!r}")

        node_features.append(vec)

    node_mat = np.array(node_features)
    # Graph-level: mean + std
    mean_feats = node_mat.mean(axis=0)
    std_feats = node_mat.std(axis=0)
    graph_vec = np.concatenate([mean_feats, std_feats])
    agg_names = [f"mean_{n}" for n in names] + [f"std_{n}" for n in names]

    return graph_vec, agg_names


# ── Classification ───────────────────────────────────────────────────────────

def logistic_regression_cv(X, y, n_folds=10, seed=42):
    """10-fold cross-validation with L2-regularized logistic regression.

    Pure numpy + scipy — no sklearn dependency.
    Uses one-vs-rest for multi-class.
    """
    from scipy.optimize import minimize
    from scipy.special import expit

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

        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y_mapped[train_idx], y_mapped[test_idx]

        # Standardize (observer-layer float)
        mu = X_train.mean(axis=0)
        sigma = X_train.std(axis=0)
        sigma[sigma < 1e-10] = 1.0
        X_train = (X_train - mu) / sigma
        X_test = (X_test - mu) / sigma

        # OVR logistic regression
        n_train, d = X_train.shape
        scores = np.zeros((len(X_test), n_classes))

        for c in range(n_classes):
            y_bin = (y_train == c).astype(float)

            def loss_and_grad(w):
                z = X_train @ w
                p = expit(z)
                l = -np.mean(y_bin * np.log(p + 1e-12) + (1 - y_bin) * np.log(1 - p + 1e-12))
                l += 0.01 * np.sum(w * w)
                g = X_train.T @ (p - y_bin) / n_train + 0.02 * w
                return l, g

            w0 = np.zeros(d)
            res = minimize(loss_and_grad, w0, jac=True, method="L-BFGS-B",
                           options={"maxiter": 200})
            scores[:, c] = X_test @ res.x

        preds = scores.argmax(axis=1)
        acc = (preds == y_test).mean()
        accs.append(acc)

    return {
        "mean_acc": round(float(np.mean(accs)), 4),
        "std_acc": round(float(np.std(accs)), 4),
        "fold_accs": [round(float(a), 4) for a in accs],
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def run_benchmark(dataset_name="PROTEINS"):
    print(f"=== {dataset_name} Graph Classification Benchmark ===")

    graphs, n_classes = load_tu_dataset(dataset_name)
    print(f"Loaded {len(graphs)} graphs, {n_classes} classes")

    labels = np.array([g["label"] for g in graphs])
    label_dist = {int(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    print(f"Label distribution: {label_dist}")

    results = {"dataset": dataset_name, "n_graphs": len(graphs), "n_classes": n_classes}

    for mode in ("degree_only", "qa21", "full"):
        print(f"\n--- Extracting {mode} features ---")
        X_list = []
        for i, g in enumerate(graphs):
            vec, names = graph_qa_features(g, mode=mode)
            X_list.append(vec)
            if i == 0:
                print(f"  Feature dim: {len(vec)} (node: {len(vec)//2}, aggregated: mean+std)")

        X = np.array(X_list)
        # Handle NaN/Inf from degenerate graphs
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        print(f"  Running 10-fold CV...")
        cv = logistic_regression_cv(X, labels)
        print(f"  Accuracy: {cv['mean_acc']:.4f} ± {cv['std_acc']:.4f}")

        results[mode] = {
            "feature_dim": int(X.shape[1]),
            "accuracy": cv,
        }

    # Deltas
    baseline_acc = results["degree_only"]["accuracy"]["mean_acc"]
    for mode in ("qa21", "full"):
        delta = results[mode]["accuracy"]["mean_acc"] - baseline_acc
        results[mode]["delta_vs_baseline"] = round(delta, 4)
        print(f"\n  {mode} Δ vs baseline: {delta:+.4f}")

    return results


def main():
    all_results = {}

    for ds_name in ("PROTEINS", "ENZYMES"):
        r = run_benchmark(ds_name)
        all_results[ds_name] = r
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for ds_name, r in all_results.items():
        print(f"\n{ds_name} ({r['n_graphs']} graphs, {r['n_classes']} classes):")
        for mode in ("degree_only", "qa21", "full"):
            acc = r[mode]["accuracy"]["mean_acc"]
            std = r[mode]["accuracy"]["std_acc"]
            delta = r[mode].get("delta_vs_baseline", 0)
            dim = r[mode]["feature_dim"]
            marker = " ←" if delta > 0.005 else (" ✗" if delta < -0.005 else "")
            print(f"  {mode:15s}: {acc:.4f} ± {std:.4f}  (dim={dim:4d})  Δ={delta:+.4f}{marker}")

    out_path = HERE / "molecular_bench_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
