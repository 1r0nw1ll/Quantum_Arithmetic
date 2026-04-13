#!/usr/bin/env python3
"""Auto-kernel selection for QA graph community detection.

The full benchmark matrix showed NO single kernel wins everywhere:
    hub-dominated (florentine)   → combined QA kernel   (+0.422)
    dense-block (caveman)        → RBF full102          (+0.418)
    scale-free 4-comm            → RBF full102          (+0.305)
    hierarchical fine            → feature selection 15 (+0.139)
    dense-block (football)       → RBF full102          (+0.056)
    overlapping                  → Eisenstein kernel    (+0.037)
    uniform-degree (karate)      → baseline (at ceiling)
    spatial                      → baseline (at ceiling)

The kernel CHOICE depends on graph structure. This module predicts the
best kernel from graph invariants and applies it automatically.

Prediction features (all observer-layer, integer-derived):
    n                 — graph size
    k                 — number of communities (given)
    degree_cv         — coefficient of variation of degree (hub dominance)
    mean_clustering   — local clustering coefficient
    modularity        — baseline spectral modularity
    assortativity     — degree-degree correlation
    density           — edge count / possible edges

Decision rules (derived from the benchmark matrix):
    high CV (>0.5) + small n (<50) → hub_distance + combined kernel
    high CV + moderate n           → RBF full102 (dense-block)
    low CV (<0.3) + high clustering → Eisenstein kernel (overlapping)
    low CV + moderate clustering + many communities → feature_select_15
    low CV + low clustering + moderate n → RBF full102
    at ceiling → baseline

Usage:
    labels, info = auto_qa_cluster(G, k=2)
    # info tells you which kernel was selected and why

QA axiom compliance:
    All node features (b, e) are integer-derived from graph topology.
    Kernel scores are observer-layer measurements.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=auto_kernel_selector, state_alphabet=graph_invariant_predictor, tier=meta_kernel_selection"

import sys
from pathlib import Path

import numpy as np

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx required")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_graph.qa_native_kernel import (
    eisenstein_kernel, combined_qa_kernel, edge_qa_adjacency,
    select_features_mi, spectral_cluster, compute_ari
)
from qa_graph.diophantine_features import full_qa_feature_vector
from qa_graph.signed_temporal import eisenstein_norm

np.random.seed(42)


# ── Graph invariants for prediction ──────────────────────────────────────────

def compute_graph_invariants(G):
    """Compute structural invariants used to predict the best kernel."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    degrees = [d for _, d in G.degree()]

    mean_deg = float(np.mean(degrees)) if degrees else 0.0
    std_deg = float(np.std(degrees)) if degrees else 0.0
    deg_cv = std_deg / mean_deg if mean_deg > 0 else 0.0

    clustering = nx.average_clustering(G) if n > 2 else 0.0
    density = 2.0 * m / (n * (n - 1)) if n > 1 else 0.0

    try:
        assortativity = nx.degree_assortativity_coefficient(G) if m > 0 else 0.0
        if np.isnan(assortativity):
            assortativity = 0.0
    except Exception:
        assortativity = 0.0

    # Hub concentration: top-k degrees / total
    sorted_degs = sorted(degrees, reverse=True)
    top_k_frac = sum(sorted_degs[:max(1, n // 10)]) / max(1, sum(sorted_degs))

    return {
        "n": n,
        "m_edges": m,
        "mean_degree": round(mean_deg, 4),
        "degree_cv": round(deg_cv, 4),
        "clustering": round(float(clustering), 4),
        "density": round(density, 4),
        "assortativity": round(float(assortativity), 4),
        "top10pct_hub_concentration": round(float(top_k_frac), 4),
    }


# ── Domain-natural (b,e) mapping selector ────────────────────────────────────

def select_be_mapping(G, invariants):
    """Select domain-natural (b,e) based on graph invariants.

    Returns (b_values, e_values, mapping_name).
    """
    n = invariants["n"]
    cv = invariants["degree_cv"]
    clust = invariants["clustering"]
    nodes = list(G.nodes())
    degree = dict(G.degree())

    # Hub-dominated: use hub-distance mapping (florentine, barbell)
    if cv > 0.5 and n < 50:
        degs = dict(G.degree())
        hubs = sorted(nodes, key=lambda v: -degs[v])[:2]
        if len(hubs) >= 2:
            sp0 = nx.shortest_path_length(G, hubs[0])
            sp1 = nx.shortest_path_length(G, hubs[1])
            b_v = [max(1, sp0.get(v, n)) for v in nodes]  # noqa: MAP-1 — QA_MAP: dist to hub0 (hub-dominated mapping)
            e_v = [max(1, sp1.get(v, n)) for v in nodes]  # QA_MAP: dist to hub1
            return b_v, e_v, "hub_distance"

    # Overlapping / density-gradient: avg neighbor degree
    if clust > 0.4 and cv < 0.5:
        avg_nbr = nx.average_neighbor_degree(G)
        b_v = [max(1, int(degree[v])) for v in nodes]  # noqa: MAP-1 — QA_MAP: degree
        e_v = [max(1, int(avg_nbr[v])) for v in nodes]  # QA_MAP: avg_nbr_degree (density gradient)
        return b_v, e_v, "degree_avgnbr"

    # Scale-free: log-degree + core
    if cv > 0.5 and n > 100:
        core = nx.core_number(G)
        b_v = [max(1, int(np.log2(max(1, degree[v]))) + 1) for v in nodes]  # QA_MAP: log2(deg) for power-law
        e_v = [max(1, int(core[v])) for v in nodes]  # QA_MAP: core shell depth
        return b_v, e_v, "log_degree_core"

    # Hierarchical (moderate CV, multiple scales): core + clustering
    if 0.15 < cv < 0.5 and clust > 0.2:
        core = nx.core_number(G)
        clustering = nx.clustering(G)
        b_v = [max(1, int(core[v])) for v in nodes]  # QA_MAP: core captures shell depth
        e_v = [max(1, int(round(clustering[v] * 10)) + 1) for v in nodes]  # noqa: T2-b-1 — QA_MAP: clustering*10 discretized
        return b_v, e_v, "core_clustering"

    # Default: degree + core (football, dense-block)
    core = nx.core_number(G)
    b_v = [max(1, int(degree[v])) for v in nodes]  # noqa: MAP-1 — QA_MAP: degree (dense-block default)
    e_v = [max(1, int(core[v])) for v in nodes]  # QA_MAP: core shell depth
    return b_v, e_v, "degree_core"


# ── Kernel selector ─────────────────────────────────────────────────────────

def select_kernel(invariants, mapping_name):
    """Predict the best kernel based on graph invariants + mapping choice.

    Returns a kernel name: 'baseline', 'rbf_full102', 'feat_select_15',
    'eisenstein', 'combined_qa', 'edge_qa'.
    """
    n = invariants["n"]
    cv = invariants["degree_cv"]
    clust = invariants["clustering"]
    density = invariants["density"]

    # Hub-dominated small graphs: combined QA kernel wins (florentine)
    if mapping_name == "hub_distance" and n < 30:
        return "combined_qa"

    # Overlapping (low CV, high clustering): Eisenstein kernel
    if mapping_name == "degree_avgnbr" and clust > 0.4:
        return "eisenstein"

    # Hierarchical (moderate CV): feature selection (fsel15 wins)
    if mapping_name == "core_clustering" and 0.15 < cv < 0.5:
        return "feat_select_15"

    # Scale-free: RBF full102 wins
    if mapping_name == "log_degree_core":
        return "rbf_full102"

    # Default: RBF full102 (dense-block, football, caveman)
    return "rbf_full102"


# ── Apply selected kernel ───────────────────────────────────────────────────

def apply_kernel(adj, b_v, e_v, kernel_name, k, seed=42):
    """Apply the selected kernel and return community labels."""
    n = adj.shape[0]

    if kernel_name == "baseline":
        return spectral_cluster(adj, k, seed)

    if kernel_name == "eisenstein":
        K = eisenstein_kernel(b_v, e_v) * adj
        return spectral_cluster(K, k, seed)

    if kernel_name == "combined_qa":
        K = combined_qa_kernel(b_v, e_v) * adj
        return spectral_cluster(K, k, seed)

    if kernel_name == "edge_qa":
        W = edge_qa_adjacency(adj, b_v, e_v)
        return spectral_cluster(W, k, seed)

    # Feature-based kernels
    feats = np.array([full_qa_feature_vector(int(b_v[i]), int(e_v[i]))[0] for i in range(n)])
    feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)

    if kernel_name == "feat_select_15":
        feats, _ = select_features_mi(feats, adj, 15)

    # RBF kernel
    F = feats.copy()
    mu = F.mean(0); sig = F.std(0); sig[sig < 1e-10] = 1.0
    F = (F - mu) / sig
    ds = np.sum((F[:, None, :] - F[None, :, :])**2, axis=2)
    tau = np.median(ds[ds > 0]) if np.any(ds > 0) else 1.0
    W = np.exp(-ds / (2 * tau)) * adj
    return spectral_cluster(W, k, seed)


# ── The main auto-selector ──────────────────────────────────────────────────

def compute_modularity(adj, labels):
    """Newman modularity — higher is better, no ground truth needed.

    Q = (1/2m) Σ [A_ij - k_i k_j / 2m] δ(c_i, c_j)
    """
    m2 = adj.sum()  # 2m
    if m2 < 1e-12:
        return 0.0
    k_vec = adj.sum(axis=1)
    Q = 0.0
    for i in range(len(labels)):
        for j in range(len(labels)):
            if labels[i] == labels[j]:
                Q += adj[i, j] - k_vec[i] * k_vec[j] / m2
    return float(Q / m2)


def auto_qa_cluster(G, k, seed=42):
    """Automatically select the best QA kernel by trying all candidates and
    picking the one with highest MODULARITY (no ground truth needed).

    This is the robust version — instead of predicting from graph invariants,
    it empirically tries each candidate mapping + kernel and keeps the best.

    Returns (labels, info_dict).
    """
    invariants = compute_graph_invariants(G)
    nodes = list(G.nodes())
    adj = nx.to_numpy_array(G, nodelist=nodes).astype(float)

    # Candidate mappings
    candidate_mappings = []
    degree = dict(G.degree())
    core = nx.core_number(G)

    # 1. degree + core (dense-block default)
    b1 = [max(1, int(degree[v])) for v in nodes]  # noqa: MAP-1 — QA_MAP: degree
    e1 = [max(1, int(core[v])) for v in nodes]    # QA_MAP: core
    candidate_mappings.append(("degree_core", b1, e1))

    # 2. degree + avg_neighbor_degree
    anb = nx.average_neighbor_degree(G)
    b2 = [max(1, int(degree[v])) for v in nodes]  # noqa: MAP-1 — QA_MAP: degree
    e2 = [max(1, int(anb[v])) for v in nodes]     # QA_MAP: avg nbr degree
    candidate_mappings.append(("degree_avgnbr", b2, e2))

    # 3. core + clustering (hierarchical)
    clustering = nx.clustering(G)
    b3 = [max(1, int(core[v])) for v in nodes]    # QA_MAP: core shell depth
    e3 = [max(1, int(round(clustering[v] * 10)) + 1) for v in nodes]  # noqa: T2-b-1 — QA_MAP: clustering*10 discretized
    candidate_mappings.append(("core_clustering", b3, e3))

    # 4. hub-distance (if high CV)
    if invariants["degree_cv"] > 0.3 and invariants["n"] < 150:
        degs_d = dict(G.degree())
        hubs = sorted(nodes, key=lambda v: -degs_d[v])[:2]
        if len(hubs) >= 2:
            sp0 = nx.shortest_path_length(G, hubs[0])
            sp1 = nx.shortest_path_length(G, hubs[1])
            b4 = [max(1, sp0.get(v, invariants["n"])) for v in nodes]  # QA_MAP: hub0 dist
            e4 = [max(1, sp1.get(v, invariants["n"])) for v in nodes]  # QA_MAP: hub1 dist
            candidate_mappings.append(("hub_distance", b4, e4))

    # 5. log-degree + core (scale-free)
    if invariants["n"] > 100:
        b5 = [max(1, int(np.log2(max(1, degree[v]))) + 1) for v in nodes]  # QA_MAP: log2 degree
        e5 = [max(1, int(core[v])) for v in nodes]  # QA_MAP: core
        candidate_mappings.append(("log_degree_core", b5, e5))

    # Candidate kernels
    candidate_kernels = ["baseline", "rbf_full102", "feat_select_15",
                         "eisenstein", "combined_qa", "edge_qa"]

    # Try every (mapping, kernel) combination, score by modularity
    best = None
    all_scores = []

    for mapping_name, b_v, e_v in candidate_mappings:
        for kernel_name in candidate_kernels:
            if kernel_name == "baseline" and mapping_name != "degree_core":
                continue  # baseline doesn't depend on mapping; evaluate once
            try:
                labels = apply_kernel(adj, b_v, e_v, kernel_name, k, seed)
                Q = compute_modularity(adj, labels)
                all_scores.append({
                    "mapping": mapping_name,
                    "kernel": kernel_name,
                    "modularity": round(Q, 4),
                })
                if best is None or Q > best["modularity"]:
                    best = {
                        "mapping": mapping_name, "kernel": kernel_name,
                        "modularity": Q, "labels": labels, "b_v": b_v, "e_v": e_v,
                    }
            except Exception as exc:
                continue

    if best is None:
        # Fallback to baseline
        labels = spectral_cluster(adj, k, seed)
        return labels, {"invariants": invariants, "mapping": "none",
                        "kernel": "baseline", "rationale": "no valid candidate"}

    info = {
        "invariants": invariants,
        "mapping": best["mapping"],
        "kernel": best["kernel"],
        "modularity": round(best["modularity"], 4),
        "b_range": [int(min(best["b_v"])), int(max(best["b_v"]))],
        "e_range": [int(min(best["e_v"])), int(max(best["e_v"]))],
        "candidates_tried": len(all_scores),
        "top3_candidates": sorted(all_scores, key=lambda x: -x["modularity"])[:3],
        "rationale": f"{best['mapping']} + {best['kernel']} (Q={best['modularity']:.4f}, "
                     f"best of {len(all_scores)} candidates)",
    }
    return best["labels"], info


def _explain_choice(inv, mapping, kernel):
    cv = inv["degree_cv"]
    n = inv["n"]
    clust = inv["clustering"]
    parts = [f"n={n}", f"deg_cv={cv}", f"clust={clust}"]

    if mapping == "hub_distance":
        parts.append("hub-dominated (high CV, small n) → hub-distance mapping")
    elif mapping == "degree_avgnbr":
        parts.append("low CV + high clustering → avg_neighbor_degree captures overlap")
    elif mapping == "log_degree_core":
        parts.append("high CV + large n → log-degree compresses power-law tail")
    elif mapping == "core_clustering":
        parts.append("moderate CV + clustering → core_number + clustering captures hierarchy")
    else:
        parts.append("default dense-block → degree + core_number")

    if kernel == "combined_qa":
        parts.append("→ combined QA kernel (Eisenstein + family + inradius)")
    elif kernel == "eisenstein":
        parts.append("→ Eisenstein norm kernel (single algebraic quantity)")
    elif kernel == "feat_select_15":
        parts.append("→ feature selection to top-15 (prevents overfitting on moderate n)")
    else:
        parts.append(f"→ {kernel}")

    return " | ".join(parts)


# ── Evaluation on the full benchmark matrix ─────────────────────────────────

def evaluate_auto_selector():
    """Test auto-selector against the known-best kernel per graph."""
    from qa_graph.qa_native_kernel import load_all_benchmarks
    from qa_graph.hierarchical_bench import build_hierarchical_graph, build_scalefree_planted
    from qa_graph.overlapping_largescale_spatial_bench import (
        build_overlapping_graph, build_spatial_graph
    )

    test_cases = []

    # Load standard benchmarks
    for name, (G, nodes, gt, k, _, _) in load_all_benchmarks().items():
        test_cases.append((name, G, np.array(gt), k))

    # Hierarchical
    G, gtf, gtc = build_hierarchical_graph()
    test_cases.append(("hierarchical_fine", G, np.array(gtf), len(set(gtf))))
    test_cases.append(("hierarchical_coarse", G, np.array(gtc), len(set(gtc))))

    # Scale-free
    G, gt = build_scalefree_planted(n_per_comm=50, k=4, m_ba=3, p_inter=0.005)
    test_cases.append(("scalefree_4comm", G, np.array(gt), 4))

    # Overlapping
    G, gt, _ = build_overlapping_graph()
    test_cases.append(("overlapping", G, np.array(gt), 4))

    # Spatial
    G, gt, _ = build_spatial_graph()
    test_cases.append(("spatial", G, np.array(gt), 4))

    print(f"{'graph':25s}  {'mapping':20s}  {'kernel':20s}  {'auto':>6}  {'baseline':>8}  Δ")
    print("-" * 95)

    results = {}
    total_auto = 0.0
    total_baseline = 0.0
    for name, G, gt, k in test_cases:
        labels, info = auto_qa_cluster(G, k)
        adj = nx.to_numpy_array(G, nodelist=list(G.nodes())).astype(float)
        baseline_labels = spectral_cluster(adj, k)
        auto_ari = compute_ari(labels, gt)
        baseline_ari = compute_ari(baseline_labels, gt)
        delta = auto_ari - baseline_ari
        total_auto += auto_ari
        total_baseline += baseline_ari
        results[name] = {
            "mapping": info["mapping"],
            "kernel": info["kernel"],
            "auto_ari": round(auto_ari, 4),
            "baseline_ari": round(baseline_ari, 4),
            "delta": round(delta, 4),
            "invariants": info["invariants"],
        }
        print(f"  {name:23s}  {info['mapping']:20s}  {info['kernel']:20s}  "
              f"{auto_ari:.4f}  {baseline_ari:.4f}  {delta:+.4f}")

    mean_auto = total_auto / len(test_cases)
    mean_baseline = total_baseline / len(test_cases)
    print()
    print(f"Mean ARI:  auto={mean_auto:.4f}  baseline={mean_baseline:.4f}  Δ={mean_auto-mean_baseline:+.4f}")

    return results


if __name__ == "__main__":
    print("=== Auto-Kernel QA Community Detection ===\n")
    results = evaluate_auto_selector()

    import json
    out = Path(__file__).parent / "auto_kernel_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")
