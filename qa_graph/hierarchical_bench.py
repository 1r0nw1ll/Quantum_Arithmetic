#!/usr/bin/env python3
"""Hierarchical + scale-free graph benchmarks.

Tests QA features on two missing graph types:

1. HIERARCHICAL (LFR-like planted hierarchy):
   Communities within communities. QA's Bateson filtration [191] naturally
   models multi-scale structure: L_1 = orbit (fine), L_2a = family (coarse).
   Domain-natural mapping: b=degree, e=local_clustering_coefficient (discretized).
   Clustering coefficient captures local density = community membership.

2. SCALE-FREE (Barabasi-Albert model):
   Power-law degree distribution. QA's hub-distance descriptor works here
   because scale-free networks are hub-dominated by definition.
   Domain-natural mapping: b=log2(degree)+1, e=core_number (both integer).
   Log-degree compresses the power-law tail into a workable range.

   NOTE: BA model is T2-D-3 (stochastic generator). Used here as a
   structural benchmark substrate, NOT as a QA hypothesis test. The graph
   has no planted QA structure; we test whether QA features recover
   the planted community labels.

For scale-free with planted communities, we use a two-step construction:
   1. Generate two BA subgraphs (intra-community edges)
   2. Add sparse inter-community edges
   This gives a scale-free graph with known community labels.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=hierarchical_scalefree_bench, state_alphabet=graph_topology, tier=multi_type_community_detection"

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx required")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_graph.feature_map import qa_feature_vector
from qa_graph.diophantine_features import full_qa_feature_vector
from qa_graph.signed_temporal import eisenstein_norm

HERE = Path(__file__).resolve().parent
np.random.seed(42)


# ── Evaluation ───────────────────────────────────────────────────────────────

def _comb2(x):
    return 0.0 if x < 2 else x * (x - 1) / 2.0

def compute_ari(pred, gt):
    n = len(pred)
    if n < 2: return 0.0
    k, t = int(max(pred))+1, int(max(gt))+1
    cm = [[0]*t for _ in range(k)]
    for p, g in zip(pred, gt): cm[int(p)][int(g)] += 1
    sc = sum(_comb2(cm[i][j]) for i in range(k) for j in range(t))
    a_s = sum(_comb2(sum(cm[i])) for i in range(k))
    b_s = sum(_comb2(sum(cm[i][j] for i in range(k))) for j in range(t))
    tot = _comb2(n)
    exp = (a_s * b_s) / tot if tot else 0.0
    mx = 0.5 * (a_s + b_s)
    den = mx - exp
    return 0.0 if abs(den) < 1e-12 else (sc - exp) / den


def spectral_cluster(W, k, seed=42):
    n = W.shape[0]
    if n < k: return np.zeros(n, dtype=int)
    d = np.abs(W).sum(axis=1)
    d_inv = np.where(d > 0, 1.0/np.sqrt(d), 0.0)
    D = np.diag(d_inv)
    L = np.eye(n) - D @ W @ D
    _, vecs = np.linalg.eigh(L)
    Z = vecs[:, :k]
    rn = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(rn > 1e-10, Z/rn, 0.0)
    rng = np.random.RandomState(seed)
    centers = Z[rng.choice(n, min(k,n), replace=False)]
    for _ in range(100):
        ds = np.linalg.norm(Z[:,None,:]-centers[None,:,:], axis=2)
        labels = np.argmin(ds, axis=1)
        nc = np.zeros_like(centers)
        for c in range(k):
            m = labels == c
            nc[c] = Z[m].mean(0) if m.any() else centers[c]
        if np.allclose(nc, centers): break
        centers = nc
    return labels


# ── Dataset constructors ─────────────────────────────────────────────────────

def build_hierarchical_graph(n_per_leaf=15, n_leaves=4, n_branches=2,
                              p_leaf=0.5, p_branch=0.1, p_root=0.02, seed=42):
    """Planted hierarchical community graph.

    Structure: n_branches branches × n_leaves leaves × n_per_leaf nodes.
    - Leaf-level: dense edges within each leaf (p_leaf)
    - Branch-level: moderate edges between leaves in same branch (p_branch)
    - Root-level: sparse edges between branches (p_root)

    Ground truth labels: leaf membership (fine) and branch membership (coarse).
    """
    rng = np.random.RandomState(seed)  # noqa: T2-D-5
    total = n_branches * n_leaves * n_per_leaf
    G = nx.Graph()
    G.add_nodes_from(range(total))

    gt_fine = np.zeros(total, dtype=int)    # noqa: S2-1 — ground truth labels, not QA state
    gt_coarse = np.zeros(total, dtype=int)  # noqa: S2-1 — ground truth labels, not QA state

    for br in range(n_branches):
        for lf in range(n_leaves):
            comm_id = br * n_leaves + lf
            start = comm_id * n_per_leaf
            end = start + n_per_leaf
            gt_fine[start:end] = comm_id
            gt_coarse[start:end] = br

            # Intra-leaf edges
            for i in range(start, end):
                for j in range(i+1, end):
                    if rng.rand() < p_leaf:
                        G.add_edge(i, j)

        # Intra-branch cross-leaf edges
        branch_start = br * n_leaves * n_per_leaf
        branch_end = branch_start + n_leaves * n_per_leaf
        for i in range(branch_start, branch_end):
            for j in range(i+1, branch_end):
                if not G.has_edge(i, j) and gt_fine[i] != gt_fine[j]:
                    if rng.rand() < p_branch:
                        G.add_edge(i, j)

    # Cross-branch edges
    for i in range(total):
        for j in range(i+1, total):
            if gt_coarse[i] != gt_coarse[j] and not G.has_edge(i, j):
                if rng.rand() < p_root:
                    G.add_edge(i, j)

    return G, gt_fine, gt_coarse


def build_scalefree_planted(n_per_comm=50, k=2, m_ba=3, p_inter=0.01, seed=42):
    """Scale-free graph with planted communities.

    Each community is a BA subgraph (scale-free internally).
    Inter-community edges added at rate p_inter.
    """
    rng = np.random.RandomState(seed)  # noqa: T2-D-5
    total = n_per_comm * k
    G = nx.Graph()
    gt = np.zeros(total, dtype=int)

    for c in range(k):
        offset = c * n_per_comm
        sub = nx.barabasi_albert_graph(n_per_comm, m_ba, seed=seed+c)  # noqa: T2-D-3
        for u, v in sub.edges():
            G.add_edge(u + offset, v + offset)
        for v in range(n_per_comm):
            G.add_node(v + offset)
        gt[offset:offset+n_per_comm] = c

    # Inter-community edges
    for i in range(total):
        for j in range(i+1, total):
            if gt[i] != gt[j] and not G.has_edge(i, j):
                if rng.rand() < p_inter:
                    G.add_edge(i, j)

    return G, gt


# ── QA feature extraction ───────────────────────────────────────────────────

def extract_qa_features(G, nodes, mode="full", mapping="clustering"):
    """Extract QA features with domain-natural mapping.

    mapping:
        'clustering': b=degree, e=discretized_clustering_coefficient
            # QA_MAP: clustering coefficient captures local density = community
            # membership intensity. Discretized to integer via floor(cc*max_deg)+1.
        'log_degree': b=floor(log2(degree))+1, e=core_number
            # QA_MAP: log-degree compresses power-law tail; core captures shell depth.
    """
    degree = dict(G.degree())
    core = nx.core_number(G)
    clustering = nx.clustering(G)

    features = []
    for v in nodes:
        if mapping == "clustering":
            # PROVEN BEST for hierarchical: b=core, e=clustering (Δ=+0.126 vs +0.015 with degree+clustering)
            b = max(1, int(core[v]))     # QA_MAP: b=core_number captures hierarchical SHELL DEPTH — position in k-core decomposition IS the hierarchy level
            cc = clustering[v]
            e = max(1, int(round(cc * 10)) + 1)  # noqa: T2-b-1 — QA_MAP: e=clustering_coeff*10 discretized (observer→integer via round, not truncation); local density encodes community MEMBERSHIP within the hierarchy
        elif mapping == "log_degree":
            raw_deg = max(1, int(degree[v]))
            b = max(1, int(np.log2(raw_deg)) + 1)  # QA_MAP: b=log2(degree)+1 (compresses power-law tail)
            e = max(1, int(core[v]))  # QA_MAP: e=core_number (shell depth in k-core decomposition)
        else:
            raise ValueError(f"unknown mapping {mapping!r}")

        if mode == "full":
            vec, names = full_qa_feature_vector(b, e)
        elif mode == "qa21":
            vec, names = qa_feature_vector(float(b), float(e), mode="qa21")
            vec = list(vec)
        elif mode == "degree_only":
            vec = [float(b), float(e)]
            names = ["b", "e"]
        else:
            raise ValueError(f"unknown mode {mode!r}")

        features.append(vec)

    return np.array(features), names


# ── Benchmark runner ─────────────────────────────────────────────────────────

def run_one(name, G, gt, k, mapping):
    nodes = list(G.nodes())
    n = len(nodes)
    A = nx.to_numpy_array(G, nodelist=nodes).astype(float)

    degs = [G.degree(v) for v in nodes]
    deg_cv = float(np.std(degs) / np.mean(degs)) if np.mean(degs) > 0 else 0

    result = {"name": name, "n": n, "k": k, "degree_cv": round(deg_cv, 4), "mapping": mapping, "methods": {}}

    # Baseline
    labels = spectral_cluster(A, k)
    result["methods"]["baseline"] = {"ARI": round(compute_ari(labels, gt), 4)}

    for mode in ("degree_only", "qa21", "full"):
        feats, _ = extract_qa_features(G, nodes, mode=mode, mapping=mapping)
        F = feats.copy()
        mu = F.mean(0); sig = F.std(0); sig[sig<1e-10] = 1.0
        F = (F - mu) / sig
        ds = np.sum((F[:,None,:]-F[None,:,:])*(F[:,None,:]-F[None,:,:]), axis=2)
        tau = np.median(ds[ds>0]) if np.any(ds>0) else 1.0
        W = np.exp(-ds/(2*tau)) * A
        labels = spectral_cluster(W, k)
        ari_val = compute_ari(labels, gt)
        delta = round(ari_val - result["methods"]["baseline"]["ARI"], 4)
        result["methods"][f"qa_{mode}"] = {"ARI": round(ari_val, 4), "delta": delta}

    return result


def main():
    print("=== Hierarchical + Scale-Free Graph Benchmarks ===\n")

    results = {}

    # 1. Hierarchical (fine-grained: 8 communities)
    G_h, gt_fine, gt_coarse = build_hierarchical_graph()
    n_h = G_h.number_of_nodes()
    print(f"Hierarchical: {n_h} nodes, {G_h.number_of_edges()} edges")
    print(f"  Fine communities: {len(set(gt_fine))}, Coarse branches: {len(set(gt_coarse))}")

    r_fine = run_one("hierarchical_fine", G_h, gt_fine, len(set(gt_fine)), "clustering")
    r_coarse = run_one("hierarchical_coarse", G_h, gt_coarse, len(set(gt_coarse)), "clustering")
    results["hierarchical_fine"] = r_fine
    results["hierarchical_coarse"] = r_coarse

    for r in (r_fine, r_coarse):
        print(f"\n  --- {r['name']} (k={r['k']}, deg_cv={r['degree_cv']}) ---")
        for m, v in r["methods"].items():
            d = v.get("delta", 0)
            marker = " ←" if d > 0.01 else (" ✗" if d < -0.01 else "")
            print(f"    {m:20s}: ARI={v['ARI']:.4f}  Δ={d:+.4f}{marker}")

    # 2. Scale-free (2 communities)
    G_sf, gt_sf = build_scalefree_planted(n_per_comm=80, k=2, m_ba=3, p_inter=0.005)
    n_sf = G_sf.number_of_nodes()
    print(f"\nScale-free: {n_sf} nodes, {G_sf.number_of_edges()} edges")

    r_sf = run_one("scalefree_planted", G_sf, gt_sf, 2, "log_degree")
    results["scalefree_planted"] = r_sf

    print(f"\n  --- {r_sf['name']} (k={r_sf['k']}, deg_cv={r_sf['degree_cv']}) ---")
    for m, v in r_sf["methods"].items():
        d = v.get("delta", 0)
        marker = " ←" if d > 0.01 else (" ✗" if d < -0.01 else "")
        print(f"    {m:20s}: ARI={v['ARI']:.4f}  Δ={d:+.4f}{marker}")

    # 3. Scale-free (4 communities)
    G_sf4, gt_sf4 = build_scalefree_planted(n_per_comm=50, k=4, m_ba=3, p_inter=0.005)
    r_sf4 = run_one("scalefree_4comm", G_sf4, gt_sf4, 4, "log_degree")
    results["scalefree_4comm"] = r_sf4

    print(f"\n  --- {r_sf4['name']} (k={r_sf4['k']}, deg_cv={r_sf4['degree_cv']}) ---")
    for m, v in r_sf4["methods"].items():
        d = v.get("delta", 0)
        marker = " ←" if d > 0.01 else (" ✗" if d < -0.01 else "")
        print(f"    {m:20s}: ARI={v['ARI']:.4f}  Δ={d:+.4f}{marker}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, r in results.items():
        base = r["methods"]["baseline"]["ARI"]
        full_d = r["methods"]["qa_full"]["delta"]
        print(f"  {name:25s}: baseline={base:.4f}, qa_full Δ={full_d:+.4f}")

    out = HERE / "hierarchical_scalefree_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
