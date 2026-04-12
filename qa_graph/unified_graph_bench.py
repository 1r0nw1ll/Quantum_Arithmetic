#!/usr/bin/env python3
"""Unified QA graph benchmark — extends integration_bench with graph-type features.

Adds features from the graph-types initiative [210-214] on top of the existing
qa21 feature backbone:

  FROM signed_temporal.py [214]:
    - eisenstein_norm(b, e) = b*b + b*e - e*e  (raw integer, per node)
    - norm_sign: +1 / -1 / 0
    - norm_mod9: Pythagorean family label (maps to Fibonacci/Lucas/Phibonacci/null)
    - norm_product(u, v): sign-agreement edge weight (positive = same cohort)

  FROM causal_dag.py [213]:
    - pair_invertible: whether gcd(2, gcd(b,e)) == 1 for this node
      (diagnostic: full QA reconstruction possible from any 2 of 4 elements)

Pipeline: load graph → extract (b=degree, e=core) per node → compute
qa21 features (baseline) → augment with norm/family features → spectral
clustering → compare ARI: baseline vs qa21 vs qa21+norm.

The norm-product edge kernel is the key new feature: it encodes whether
two adjacent nodes are in the same Eisenstein sign cohort. Communities
within a single sign cohort should cluster tighter under this kernel.

Theorem NT compliance: all features are integer-derived from graph topology
(degree, core number). No stochastic generators. No float state in QA layer.
Float arithmetic is observer-layer only (RBF kernel, spectral decomposition).

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/unified_graph_bench.py

Will Dale + Claude, 2026-04-12.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=unified_graph_bench, state_alphabet=community_topology, tier=augmented_spectral_benchmark"

import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx required: pip install networkx")

from qa_graph.feature_map import qa_feature_vector, CANONICAL_21
from qa_graph.signed_temporal import eisenstein_norm
from qa_observer.core import qa_mod

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


# ── Evaluation metrics (self-contained) ──────────────────────────────────

def _comb2(x):
    return 0.0 if x < 2 else x * (x - 1) / 2.0


def compute_ari(pred, gt):
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


# ── Dataset loaders ──────────────────────────────────────────────────────

def load_football():
    p = DATA / "football.graphml"
    if not p.exists():
        sys.exit(f"football.graphml not found at {p}")
    G = nx.read_graphml(str(p))
    nodes = list(G.nodes())
    gt = np.array([int(G.nodes[v].get("value", 0)) for v in nodes])
    k = len(set(gt))
    return G, nodes, gt, k, "football"


def load_karate():
    G = nx.karate_club_graph()
    nodes = list(G.nodes())
    gt = np.array([0 if G.nodes[v]["club"] == "Mr. Hi" else 1 for v in nodes])
    return G, nodes, gt, 2, "karate"


def load_barbell():
    G = nx.barbell_graph(10, 3)
    nodes = list(G.nodes())
    gt = np.array([0 if v < 11 else 1 for v in nodes])
    return G, nodes, gt, 2, "barbell"


def load_caveman():
    G = nx.connected_caveman_graph(4, 5)
    nodes = list(G.nodes())
    gt = np.array([v // 5 for v in nodes])
    return G, nodes, gt, 4, "caveman"


def load_florentine():
    G = nx.florentine_families_graph()
    nodes = list(G.nodes())
    medici_allies = {"Medici", "Barbadori", "Ridolfi", "Tornabuoni",
                     "Albizzi", "Salviati", "Ginori", "Pazzi"}
    gt = np.array([0 if v in medici_allies else 1 for v in nodes])
    return G, nodes, gt, 2, "florentine"


ALL_LOADERS = [load_karate, load_barbell, load_caveman, load_florentine, load_football]


# ── Feature extraction ───────────────────────────────────────────────────

def extract_node_features(G, nodes):
    """Extract per-node features: qa21 baseline + graph-type augmentations.

    Returns dict: node -> feature dict with keys:
        'b', 'e', 'qa21' (21-vector), 'eisenstein_norm', 'norm_sign',
        'norm_mod9', 'family_label'
    """
    degree = dict(G.degree())
    core = nx.core_number(G)

    features = {}
    for v in nodes:
        b = max(1, int(degree[v]))
        e = max(1, int(core[v]))

        vec, names = qa_feature_vector(float(b), float(e), mode="qa21")
        norm = eisenstein_norm(b, e)
        sign = 1 if norm > 0 else (-1 if norm < 0 else 0)
        norm_mod = norm % 9

        family = "null"
        if norm_mod in (1, 8):
            family = "Fibonacci"
        elif norm_mod in (4, 5):
            family = "Lucas"
        elif norm_mod in (2, 7):
            family = "Phibonacci"
        elif norm_mod == 0:
            family = "null"

        features[v] = {
            "b": b, "e": e,
            "qa21": vec,
            "eisenstein_norm": norm,
            "norm_sign": sign,
            "norm_mod9": norm_mod,
            "family_label": family,
        }
    return features


# ── Kernel construction ──────────────────────────────────────────────────

def build_adjacency(G, nodes, features, mode="baseline"):
    """Build weighted adjacency matrix.

    Modes:
        'baseline'   — unweighted (1/0)
        'qa21'       — RBF kernel on 21 QA invariants (existing method)
        'qa21+norm'  — RBF kernel on qa21 augmented with norm features
        'norm_product' — edge weight = sign of f(u)*f(v) (1 if same cohort, 0.1 if different)
    """
    n = len(nodes)
    A = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)

    if mode == "baseline":
        return A

    if mode in ("qa21", "qa21+norm"):
        vectors = []
        for v in nodes:
            f = features[v]
            vec = list(f["qa21"])
            if mode == "qa21+norm":
                vec.extend([
                    float(f["eisenstein_norm"]),
                    float(f["norm_sign"]),
                    float(f["norm_mod9"]),
                ])
            vectors.append(vec)
        F_mat = np.array(vectors)

        # Standardize columns
        mu = F_mat.mean(axis=0)
        sigma = F_mat.std(axis=0)
        sigma[sigma < 1e-10] = 1.0
        F_mat = (F_mat - mu) / sigma

        # RBF kernel
        dists = np.sum((F_mat[:, None, :] - F_mat[None, :, :]) * (F_mat[:, None, :] - F_mat[None, :, :]), axis=2)
        tau = np.median(dists[dists > 0]) if np.any(dists > 0) else 1.0
        W = np.exp(-dists / (2 * tau))
        return A * W

    if mode == "norm_product":
        norms = np.array([features[v]["eisenstein_norm"] for v in nodes], dtype=float)
        signs = np.sign(norms)
        # Same-sign edge gets weight 1.0; different-sign gets 0.1; zero-norm gets 0.5
        W = np.ones((n, n))
        for i in range(n):
            for j in range(n):
                if signs[i] == 0 or signs[j] == 0:
                    W[i, j] = 0.5
                elif signs[i] == signs[j]:
                    W[i, j] = 1.0
                else:
                    W[i, j] = 0.1
        return A * W

    raise ValueError(f"unknown mode: {mode!r}")


# ── Spectral clustering (pure numpy) ─────────────────────────────────────

def spectral_cluster(W, k, seed=42):
    n = W.shape[0]
    d = W.sum(axis=1)
    d_inv_sqrt = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    D_inv_sqrt = np.diag(d_inv_sqrt)
    L_norm = np.eye(n) - D_inv_sqrt @ W @ D_inv_sqrt

    eigvals, eigvecs = np.linalg.eigh(L_norm)
    Z = eigvecs[:, :k]

    row_norms = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(row_norms > 1e-10, Z / row_norms, 0.0)

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


# ── Main benchmark loop ─────────────────────────────────────────────────

def run_benchmark():
    modes = ["baseline", "qa21", "qa21+norm", "norm_product"]
    results = {}

    for loader in ALL_LOADERS:
        G, nodes, gt, k, name = loader()
        features = extract_node_features(G, nodes)

        # Degree CV (hub dominance proxy)
        degrees = [G.degree(v) for v in nodes]
        deg_mean = np.mean(degrees)
        deg_std = np.std(degrees)
        deg_cv = deg_std / deg_mean if deg_mean > 0 else 0

        # Family distribution
        families = [features[v]["family_label"] for v in nodes]
        from collections import Counter
        fam_dist = dict(Counter(families))

        graph_result = {
            "n": len(nodes),
            "k": k,
            "degree_cv": round(deg_cv, 4),
            "family_distribution": fam_dist,
            "methods": {},
        }

        for mode in modes:
            W = build_adjacency(G, nodes, features, mode=mode)
            labels = spectral_cluster(W, k)
            a = compute_ari(labels.tolist(), gt.tolist())
            graph_result["methods"][mode] = {"ARI": round(a, 4)}

        # Compute deltas from baseline
        baseline_ari = graph_result["methods"]["baseline"]["ARI"]
        for mode in modes:
            delta = graph_result["methods"][mode]["ARI"] - baseline_ari
            graph_result["methods"][mode]["delta_vs_baseline"] = round(delta, 4)

        results[name] = graph_result

    return results


def main():
    print("=== Unified QA Graph Benchmark ===")
    print("Features: baseline / qa21 / qa21+norm / norm_product")
    print()

    results = run_benchmark()

    # Pretty print
    for name, r in results.items():
        print(f"--- {name} (n={r['n']}, k={r['k']}, deg_cv={r['degree_cv']}) ---")
        print(f"  family distribution: {r['family_distribution']}")
        for mode, m in r["methods"].items():
            delta = m["delta_vs_baseline"]
            marker = " ←" if delta > 0.01 else (" ✗" if delta < -0.01 else "")
            print(f"  {mode:16s}: ARI={m['ARI']:.4f}  Δ={delta:+.4f}{marker}")
        print()

    # Save
    out_path = HERE / "unified_graph_bench_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {out_path}")

    # Summary table
    print("\n=== SUMMARY: ARI by method ===")
    print(f"{'graph':15s}", end="")
    modes = ["baseline", "qa21", "qa21+norm", "norm_product"]
    for m in modes:
        print(f"  {m:16s}", end="")
    print()
    for name, r in results.items():
        print(f"{name:15s}", end="")
        for m in modes:
            print(f"  {r['methods'][m]['ARI']:16.4f}", end="")
        print()


if __name__ == "__main__":
    main()
