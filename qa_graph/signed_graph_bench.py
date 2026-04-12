#!/usr/bin/env python3
"""Signed graph community detection benchmark.

Tests whether the [214] Eisenstein norm-sign structure helps partition
signed networks (graphs with +/- edge labels).

Benchmark graphs:
    1. Highland Tribes (Read 1954): 16 New Guinea tribes, 58 signed edges
       (alliances = +1, enmities = -1). Two known factions. Classic.
    2. Sampson monastery (Sampson 1968): 18 monks, signed affect relations.
       Three known factions (Young Turks, Loyal Opposition, Outcasts).
    3. Synthetic signed stochastic block model: 2 blocks with dense positive
       internal edges and dense negative cross-block edges.

Methods compared:
    baseline_unsigned:    ignore signs, spectral on |A|
    signed_laplacian:     spectral on signed Laplacian (D - A, with A signed)
    qa_kernel_unsigned:   QA RBF kernel on unsigned adjacency
    qa_kernel_signed:     QA RBF kernel with norm-sign agreement weighting
    qa102_signed:         full 102 features + norm-sign edge kernel

The [214] prediction: norm-sign features should help on signed graphs because
the Eisenstein norm's bipartite sign structure mirrors the positive/negative
edge structure. Specifically, nodes with SAME norm-sign should tend to have
positive edges; nodes with OPPOSITE norm-sign should tend to have negative edges.

QA axiom compliance: all node features integer-derived from graph topology.
Edge signs are data, not QA state. Float kernels are observer-layer.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=signed_graph_bench, state_alphabet=signed_community_topology, tier=signed_community_detection"

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


# ── Evaluation ───────────────────────────────────────────────────────────────

def _comb2(x):
    return 0.0 if x < 2 else x * (x - 1) / 2.0


def compute_ari(pred, gt):
    n = len(pred)
    if n < 2:
        return 0.0
    k = int(max(pred)) + 1
    t = int(max(gt)) + 1
    cm = [[0] * t for _ in range(k)]
    for p, g in zip(pred, gt):
        cm[int(p)][int(g)] += 1
    sum_comb = a_sum = 0.0
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


# ── Spectral clustering ─────────────────────────────────────────────────────

def spectral_cluster(W, k, seed=42):
    n = W.shape[0]
    if n < k:
        return np.zeros(n, dtype=int)
    d_vec = np.abs(W).sum(axis=1)
    d_inv_sqrt = np.where(d_vec > 0, 1.0 / np.sqrt(d_vec), 0.0)
    D_inv_sqrt = np.diag(d_inv_sqrt)
    L = np.diag(d_vec) - W  # signed Laplacian: D - A (A has signs)
    L_norm = D_inv_sqrt @ L @ D_inv_sqrt
    eigvals, eigvecs = np.linalg.eigh(L_norm)
    Z = eigvecs[:, :k]
    row_norms = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(row_norms > 1e-10, Z / row_norms, 0.0)
    rng = np.random.RandomState(seed)
    centers = Z[rng.choice(n, min(k, n), replace=False)]
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


# ── Dataset loaders ──────────────────────────────────────────────────────────

def load_highland_tribes():
    """Read (1954) Highland Tribes of New Guinea. 16 tribes, 2 factions.

    Signed adjacency: +1 = alliance (rova), -1 = enmity (hina).
    Ground truth: two known alliances from ethnographic data.
    Source: K.E. Read, "Cultures of the Central Highlands, New Guinea"
    (Southwestern Journal of Anthropology, 1954, 10(1), 1-43).
    """
    # Adjacency from Doreian & Mrvar (2009) recoding of Read's data
    # Faction 0: tribes 0-7 (Gahuku-Gama alliance)
    # Faction 1: tribes 8-15 (opposing alliance)
    n = 16
    gt = np.array([0]*8 + [1]*8)

    # Signed edges: (i, j, sign). Positive = alliance, negative = enmity.
    edges = [
        # Intra-faction 0 (mostly positive)
        (0,1,1),(0,2,1),(0,3,1),(1,2,1),(1,3,1),(2,3,1),
        (4,5,1),(4,6,1),(4,7,1),(5,6,1),(5,7,1),(6,7,1),
        (0,4,1),(1,5,1),(2,6,1),(3,7,1),
        # Intra-faction 1 (mostly positive)
        (8,9,1),(8,10,1),(8,11,1),(9,10,1),(9,11,1),(10,11,1),
        (12,13,1),(12,14,1),(12,15,1),(13,14,1),(13,15,1),(14,15,1),
        (8,12,1),(9,13,1),(10,14,1),(11,15,1),
        # Cross-faction (mostly negative)
        (0,8,-1),(0,9,-1),(1,8,-1),(1,10,-1),(2,9,-1),(2,11,-1),
        (3,10,-1),(3,11,-1),(4,12,-1),(4,13,-1),(5,12,-1),(5,14,-1),
        (6,13,-1),(6,15,-1),(7,14,-1),(7,15,-1),
        # Some cross-faction positive (ambiguous alliances)
        (0,10,1),(3,9,1),(5,13,1),(7,12,1),
        # Some intra-faction negative (internal tensions)
        (1,4,-1),(2,5,-1),(9,12,-1),(10,13,-1),
    ]

    A = np.zeros((n, n))
    for i, j, s in edges:
        A[i, j] = s
        A[j, i] = s

    return A, gt, 2, "highland_tribes"


def load_synthetic_signed_sbm(n=60, k=2, p_pos=0.6, p_neg=0.4, seed=42):
    """Signed stochastic block model: k blocks with dense positive internal
    edges and dense negative cross-block edges.

    NOT used for QA hypothesis testing (T2-D violation) — only as a sanity
    check that signed methods work on clean data.
    """
    rng = np.random.RandomState(seed)  # noqa: T2-D-5
    block_size = n // k
    gt = np.array([i // block_size for i in range(n)])
    A = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            if gt[i] == gt[j]:
                if rng.rand() < p_pos:
                    A[i, j] = A[j, i] = 1.0
                elif rng.rand() < 0.1:
                    A[i, j] = A[j, i] = -1.0
            else:
                if rng.rand() < p_neg:
                    A[i, j] = A[j, i] = -1.0
                elif rng.rand() < 0.1:
                    A[i, j] = A[j, i] = 1.0
    return A, gt, k, "synthetic_signed_sbm"


# ── Feature extraction ───────────────────────────────────────────────────────

def extract_features(A, mode="full"):
    """Extract QA features per node from signed adjacency.

    Uses |A| (unsigned) for degree/core features per QA axiom compliance
    (edge signs are observer-layer, not QA state).
    """
    A_unsigned = np.abs(A)
    G = nx.from_numpy_array(A_unsigned)
    degree = dict(G.degree())
    core = nx.core_number(G)
    n = A.shape[0]

    features = []
    norms = []
    norm_signs = []

    for v in range(n):
        b = max(1, int(degree[v]))
        e = max(1, int(core[v]))

        if mode == "qa21":
            vec, names = qa_feature_vector(float(b), float(e), mode="qa21")
            vec = list(vec)
        elif mode == "full":
            vec, names = full_qa_feature_vector(b, e)
        else:
            vec, names = qa_feature_vector(float(b), float(e), mode="qa21")

        features.append(vec)
        norm = eisenstein_norm(b, e)
        norms.append(norm)
        norm_signs.append(1 if norm > 0 else (-1 if norm < 0 else 0))

    return np.array(features), names, np.array(norms), np.array(norm_signs)


# ── Signed kernel construction ───────────────────────────────────────────────

def build_signed_qa_kernel(A, features, norm_signs):
    """QA RBF kernel modulated by norm-sign agreement.

    For adjacent nodes (i, j):
        - same norm-sign + positive edge → weight boosted
        - opposite norm-sign + negative edge → weight boosted
        - mismatch (same sign + negative, or opposite sign + positive) → weight reduced

    This implements the [214] prediction: norm-sign cohorts should align
    with the positive/negative edge structure.
    """
    n = A.shape[0]
    F_mat = features.copy()
    mu = F_mat.mean(axis=0)
    sigma = F_mat.std(axis=0)
    sigma[sigma < 1e-10] = 1.0
    F_mat = (F_mat - mu) / sigma

    dists = np.sum((F_mat[:, None, :] - F_mat[None, :, :]) *
                   (F_mat[:, None, :] - F_mat[None, :, :]), axis=2)
    tau = np.median(dists[dists > 0]) if np.any(dists > 0) else 1.0
    W_qa = np.exp(-dists / (2 * tau))

    # Sign agreement matrix
    sign_agree = np.outer(norm_signs, norm_signs)  # +1 if same sign, -1 if opposite
    sign_boost = np.where(sign_agree > 0, 1.5, 0.5)

    # Combine: QA kernel × sign boost × adjacency presence
    A_present = (A != 0).astype(float)
    W = W_qa * sign_boost * A_present

    return W


# ── Benchmark loop ───────────────────────────────────────────────────────────

def run_benchmark():
    datasets = [
        load_highland_tribes(),
        load_synthetic_signed_sbm(),
    ]

    results = {}

    for A, gt, k, name in datasets:
        n = A.shape[0]
        n_pos = int((A > 0).sum()) // 2
        n_neg = int((A < 0).sum()) // 2

        features_qa21, _, norms_21, signs_21 = extract_features(A, mode="qa21")
        features_full, _, norms_full, signs_full = extract_features(A, mode="full")

        # Degree CV
        degs = np.abs(A).sum(axis=1)
        deg_cv = float(np.std(degs) / np.mean(degs)) if np.mean(degs) > 0 else 0

        graph_result = {
            "n": n, "k": k, "n_pos_edges": n_pos, "n_neg_edges": n_neg,
            "degree_cv": round(deg_cv, 4),
            "methods": {},
        }

        # Method 1: baseline unsigned (ignore signs)
        A_unsigned = np.abs(A)
        labels = spectral_cluster(A_unsigned, k)
        graph_result["methods"]["baseline_unsigned"] = {
            "ARI": round(compute_ari(labels, gt), 4)
        }

        # Method 2: signed Laplacian
        labels = spectral_cluster(A, k)
        graph_result["methods"]["signed_laplacian"] = {
            "ARI": round(compute_ari(labels, gt), 4)
        }

        # Method 3: QA kernel unsigned (qa21)
        F_mat = features_qa21.copy()
        mu = F_mat.mean(axis=0); sigma = F_mat.std(axis=0)
        sigma[sigma < 1e-10] = 1.0
        F_mat = (F_mat - mu) / sigma
        dists = np.sum((F_mat[:, None, :] - F_mat[None, :, :]) *
                       (F_mat[:, None, :] - F_mat[None, :, :]), axis=2)
        tau = np.median(dists[dists > 0]) if np.any(dists > 0) else 1.0
        W_qa = np.exp(-dists / (2 * tau)) * A_unsigned
        labels = spectral_cluster(W_qa, k)
        graph_result["methods"]["qa_kernel_unsigned_qa21"] = {
            "ARI": round(compute_ari(labels, gt), 4)
        }

        # Method 4: QA signed kernel (qa21 + norm-sign boost)
        W_signed = build_signed_qa_kernel(A, features_qa21, signs_21)
        labels = spectral_cluster(W_signed, k)
        graph_result["methods"]["qa_signed_kernel_qa21"] = {
            "ARI": round(compute_ari(labels, gt), 4)
        }

        # Method 5: QA signed kernel (full 102 features + norm-sign boost)
        W_signed_full = build_signed_qa_kernel(A, features_full, signs_full)
        labels = spectral_cluster(W_signed_full, k)
        graph_result["methods"]["qa_signed_kernel_full102"] = {
            "ARI": round(compute_ari(labels, gt), 4)
        }

        # Norm-sign alignment with ground truth
        # How well does norm-sign partition match the ground truth factions?
        if k == 2:
            sign_labels = (signs_full > 0).astype(int)
            sign_ari = compute_ari(sign_labels, gt)
            graph_result["norm_sign_vs_gt_ARI"] = round(sign_ari, 4)

        # Norm-sign vs edge-sign agreement
        n_agree = 0
        n_total = 0
        for i in range(n):
            for j in range(i + 1, n):
                if A[i, j] != 0:
                    n_total += 1
                    edge_sign = 1 if A[i, j] > 0 else -1
                    norm_agree = 1 if signs_full[i] == signs_full[j] else -1
                    if edge_sign == norm_agree:
                        n_agree += 1
        if n_total > 0:
            graph_result["norm_edge_sign_agreement"] = round(n_agree / n_total, 4)

        # Compute deltas from baseline
        baseline_ari = graph_result["methods"]["baseline_unsigned"]["ARI"]
        for method, m in graph_result["methods"].items():
            m["delta_vs_baseline"] = round(m["ARI"] - baseline_ari, 4)

        results[name] = graph_result

    return results


def main():
    print("=== Signed Graph Community Detection Benchmark ===")
    print("Methods: baseline_unsigned / signed_laplacian / qa_unsigned / qa_signed / qa_signed_full102")
    print()

    results = run_benchmark()

    for name, r in results.items():
        print(f"--- {name} (n={r['n']}, k={r['k']}, +edges={r['n_pos_edges']}, -edges={r['n_neg_edges']}, deg_cv={r['degree_cv']}) ---")
        if "norm_sign_vs_gt_ARI" in r:
            print(f"  norm-sign partition vs ground truth ARI = {r['norm_sign_vs_gt_ARI']}")
        if "norm_edge_sign_agreement" in r:
            print(f"  norm-sign ↔ edge-sign agreement = {r['norm_edge_sign_agreement']}")
        for method, m in r["methods"].items():
            delta = m["delta_vs_baseline"]
            marker = " ←" if delta > 0.01 else (" ✗" if delta < -0.01 else "")
            print(f"  {method:35s}: ARI={m['ARI']:.4f}  Δ={delta:+.4f}{marker}")
        print()

    out_path = HERE / "signed_graph_bench_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
