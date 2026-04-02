#!/usr/bin/env python3
"""End-to-end QA graph community detection benchmark.

Pipeline: load GraphML → extract (b,e) per node via degree/core-number →
compute QA feature vectors → build QA-weighted kernel adjacency →
spectral clustering → evaluate ARI/NMI/purity against ground truth →
compare baseline (unweighted Louvain) vs QA-weighted.

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/integration_bench.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=graph_bench, state_alphabet=community_topology"

import json
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx required: pip install networkx")

from qa_graph.feature_map import qa_feature_vector, CANONICAL_21
from qa_observer.core import qa_mod

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# ── Evaluation metrics (self-contained, no sklearn dependency) ──────────


def _comb2(x):
    return 0.0 if x < 2 else x * (x - 1) / 2.0


def purity(pred, gt):
    n = len(pred)
    if n == 0:
        return 0.0
    clusters = {}
    for p, g in zip(pred, gt):
        clusters.setdefault(p, []).append(g)
    return sum(Counter(v).most_common(1)[0][1] for v in clusters.values()) / n


def ari(pred, gt):
    n = len(pred)
    if n < 2:
        return 0.0
    k = max(pred) + 1
    t = max(gt) + 1
    cm = [[0] * t for _ in range(k)]
    for p, g in zip(pred, gt):
        cm[p][g] += 1

    sum_comb = 0.0
    a_sum = 0.0
    b_sums = [0] * t
    for i in range(k):
        row_sum = sum(cm[i])
        a_sum += _comb2(row_sum)
        for j in range(t):
            sum_comb += _comb2(cm[i][j])
            b_sums[j] += cm[i][j]
    b_sum = sum(_comb2(x) for x in b_sums)
    total = _comb2(n)
    expected = (a_sum * b_sum) / total if total else 0.0
    max_idx = 0.5 * (a_sum + b_sum)
    den = max_idx - expected
    return 0.0 if abs(den) < 1e-12 else (sum_comb - expected) / den


def nmi(pred, gt):
    n = len(pred)
    if n == 0:
        return 0.0
    k = max(pred) + 1
    t = max(gt) + 1
    cm = [[0] * t for _ in range(k)]
    for p, g in zip(pred, gt):
        cm[p][g] += 1
    row_sums = [sum(cm[i]) for i in range(k)]
    col_sums = [sum(cm[i][j] for i in range(k)) for j in range(t)]
    nf = float(n)
    mi = 0.0
    for i in range(k):
        for j in range(t):
            nij = cm[i][j]
            if nij == 0:
                continue
            p_ij = nij / nf
            p_i = row_sums[i] / nf
            p_j = col_sums[j] / nf
            mi += p_ij * math.log(p_ij / (p_i * p_j))
    h_u = -sum((x / nf) * math.log(x / nf) for x in row_sums if x > 0)
    h_v = -sum((x / nf) * math.log(x / nf) for x in col_sums if x > 0)
    den = math.sqrt(h_u * h_v)
    return 0.0 if den <= 0 else mi / den


# ── QA feature extraction from graph ───────────────────────────────────


def extract_qa_features(G, mode="qa21"):
    """Extract (b, e) per node and compute QA feature vectors.

    b = degree (graph-structural)
    e = core number (graph-structural)

    Both are integers, both are graph-topological — no float state.
    """
    degree = dict(G.degree())
    core = nx.core_number(G)

    nodes = list(G.nodes())
    features = {}
    for v in nodes:
        b = max(1, int(degree[v]))  # A1: at least 1
        e = max(1, int(core[v]))    # A1: at least 1
        vec, names = qa_feature_vector(float(b), float(e), mode=mode)
        features[v] = vec
    return features, names


# ── Spectral clustering (pure numpy) ───────────────────────────────────


def spectral_cluster(W, k, seed=42):
    """Spectral clustering on weighted adjacency W. Returns labels."""
    n = W.shape[0]
    # Degree matrix
    d = W.sum(axis=1)
    d_inv_sqrt = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    # Normalized Laplacian: I - D^{-1/2} W D^{-1/2}
    D_inv_sqrt = np.diag(d_inv_sqrt)
    L_norm = np.eye(n) - D_inv_sqrt @ W @ D_inv_sqrt

    # Eigen decomposition (bottom k eigenvectors)
    eigvals, eigvecs = np.linalg.eigh(L_norm)
    Z = eigvecs[:, :k]  # first k eigenvectors

    # Normalize rows
    row_norms = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(row_norms > 1e-10, Z / row_norms, 0.0)

    # K-means (simple implementation)
    rng = np.random.RandomState(seed)
    centers = Z[rng.choice(n, k, replace=False)]
    for _ in range(100):
        dists = np.linalg.norm(Z[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(dists, axis=1)
        new_centers = np.zeros_like(centers)
        for c in range(k):
            mask = labels == c
            if mask.any():
                new_centers[c] = Z[mask].mean(axis=0)
            else:
                new_centers[c] = centers[c]
        if np.allclose(new_centers, centers):
            break
        centers = new_centers

    return labels


# ── Build QA-weighted adjacency ────────────────────────────────────────


def build_qa_weighted_adjacency(G, features, mode="X"):
    """Build weighted adjacency using QA invariant kernels.

    Modes:
      'baseline': unweighted adjacency (1 for edges, 0 otherwise)
      'X': weight by X-invariant kernel (e*d product similarity)
      'G': weight by G-invariant kernel (hypotenuse similarity)
      'F': weight by F-invariant kernel (b*a product similarity)
      'full': weight by full qa21 RBF kernel (all 21 invariants)
    """
    nodes = list(G.nodes())
    n = len(nodes)

    if mode == "baseline":
        W = nx.to_numpy_array(G, nodelist=nodes, weight=None)
        return W.astype(float)

    A = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)

    if mode == "full":
        # Full qa21 RBF kernel: exp(-||f_i - f_j||^2 / (2*tau^2))
        F_mat = np.array([features[v] for v in nodes])
        # Z-score normalize each feature
        mu = F_mat.mean(axis=0, keepdims=True)
        sigma = F_mat.std(axis=0, keepdims=True) + 1e-8
        F_norm = (F_mat - mu) / sigma
        # Pairwise squared distances
        sq_dists = np.sum((F_norm[:, None, :] - F_norm[None, :, :]) ** 2, axis=2)
        # Bandwidth: median of edge distances
        edge_dists = sq_dists[A > 0]
        tau_sq = np.median(edge_dists) + 1e-8
        W = A * np.exp(-sq_dists / (2 * tau_sq))
        return W

    # Single-invariant kernel
    _, names = qa_feature_vector(1.0, 1.0, mode="qa21")
    feat_idx = names.index(mode) if mode in names else names.index("G")
    vals = np.array([features[v][feat_idx] for v in nodes])

    diffs = np.abs(vals[:, None] - vals[None, :])
    tau = np.median(diffs[A > 0]) + 1e-8
    W = A * np.exp(-diffs / tau)

    return W


# ── Main benchmark ─────────────────────────────────────────────────────


def run_benchmark(graph_name, k_clusters=None):
    """Run full pipeline on a benchmark graph."""
    graph_path = DATA / f"{graph_name}.graphml"
    if not graph_path.exists():
        return {"error": f"Graph not found: {graph_path}"}

    G = nx.read_graphml(str(graph_path)).to_undirected()
    nodes = list(G.nodes())
    n = len(nodes)

    # Ground truth
    gt_map = {}
    for v, data in G.nodes(data=True):
        if "value" in data:
            gt_map[v] = int(data["value"])
    if not gt_map:
        return {"error": f"No ground truth 'value' attribute in {graph_name}"}

    gt_labels = [gt_map[v] for v in nodes]
    k = k_clusters or (max(gt_labels) + 1)

    # Extract QA features
    features, feat_names = extract_qa_features(G, mode="qa21")

    results = {"graph": graph_name, "nodes": n, "edges": G.number_of_edges(), "k": k}

    # Run for each adjacency mode
    for adj_mode in ["baseline", "X", "G", "F", "full"]:
        t0 = time.perf_counter()
        W = build_qa_weighted_adjacency(G, features, mode=adj_mode)
        labels = spectral_cluster(W, k)
        elapsed = time.perf_counter() - t0

        pred = list(labels)
        gt = gt_labels

        results[adj_mode] = {
            "purity": round(purity(pred, gt), 4),
            "ARI": round(ari(pred, gt), 4),
            "NMI": round(nmi(pred, gt), 4),
            "elapsed_s": round(elapsed, 3),
        }

    # Compute deltas (QA - baseline)
    for qm in ["X", "G", "F", "full"]:
        if qm in results and "baseline" in results:
            results[f"delta_{qm}"] = {
                metric: round(results[qm][metric] - results["baseline"][metric], 4)
                for metric in ["purity", "ARI", "NMI"]
            }

    return results


def main():
    print("=" * 60)
    print("QA GRAPH COMMUNITY DETECTION — INTEGRATION BENCHMARK")
    print("=" * 60)

    all_results = {}

    for graph_name in ["karate", "football", "dolphins"]:
        print(f"\n--- {graph_name.upper()} ---")
        result = run_benchmark(graph_name)
        all_results[graph_name] = result

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue

        print(f"  Nodes: {result['nodes']}, Edges: {result['edges']}, K: {result['k']}")
        print()
        print(f"  {'Mode':<12} {'Purity':>8} {'ARI':>8} {'NMI':>8} {'Time':>8}")
        print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for mode in ["baseline", "X", "G", "F", "full"]:
            if mode in result:
                m = result[mode]
                print(f"  {mode:<12} {m['purity']:>8.4f} {m['ARI']:>8.4f} {m['NMI']:>8.4f} {m['elapsed_s']:>7.3f}s")

        print()
        for qm in ["X", "G", "F", "full"]:
            dk = f"delta_{qm}"
            if dk in result:
                d = result[dk]
                direction = "+" if d["ARI"] > 0 else ("-" if d["ARI"] < 0 else "=")
                print(f"  Delta {qm} vs baseline: ARI {direction}{abs(d['ARI']):.4f}, NMI {'+' if d['NMI']>0 else ''}{d['NMI']:.4f}")

    # Save results
    out_path = HERE / "integration_bench_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved: {out_path}")

    return all_results


if __name__ == "__main__":
    main()
