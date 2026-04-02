#!/usr/bin/env python3
"""PIM + Graph full-stack integration: sector-partitioned QA graph analysis.

Demonstrates the complete qa_pim + qa_graph + qa_observer pipeline:
1. Load graph with QA tuple attributes (b,e,d,a per node)
2. Map nodes to PIM sectors via qa_mod (A1 compliant)
3. Use RESIDUE_SELECT for sector-based filtering
4. Compute qa21 feature vectors per node
5. Build sector-partitioned CSR via qa_pim.graph
6. Run spectral clustering with QA kernel weighting
7. Evaluate community detection quality

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/pim_graph_integration.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=pim_graph_integration, state_alphabet=sector_community"

import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import networkx as nx
except ImportError:
    raise SystemExit("networkx required")

# Import from all three new packages
from qa_pim.kernels import RESIDUE_SELECT, RADD_m, ROLLING_SUM_PHASE
from qa_pim.graph import build_sector_csr, neighbor_expand
from qa_pim.schema import QAParams
from qa_graph.feature_map import qa_feature_vector, CANONICAL_21
from qa_observer.core import qa_mod, classify_orbit

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

MODULUS = 24


# ── Evaluation metrics ─────────────────────────────────────────────────

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


def ari_score(pred, gt):
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


def nmi_score(pred, gt):
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


# ── Spectral clustering ───────────────────────────────────────────────

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


# ── Main pipeline ──────────────────────────────────────────────────────

def analyze_graph(graph_path, graph_name):
    """Full PIM + graph analysis pipeline."""
    G = nx.read_graphml(str(graph_path)).to_undirected()
    nodes = list(G.nodes())
    n = len(nodes)
    node_idx = {v: i for i, v in enumerate(nodes)}

    # Ground truth
    gt_map = {}
    for v, data in G.nodes(data=True):
        if "value" in data:
            gt_map[v] = int(data["value"])

    has_gt = len(gt_map) == n
    gt_labels = [gt_map.get(v, 0) for v in nodes] if has_gt else None
    k = (max(gt_labels) + 1) if has_gt else 8

    # ── Step 1: Extract (b, e) from node attributes or topology ────

    has_qa_attrs = all(
        "d1" in G.nodes[v] and "d2" in G.nodes[v]
        for v in nodes[:5]
    )

    if has_qa_attrs:
        # Use embedded QA tuples (Raman graphs)
        b_vals = [max(1, int(round(float(G.nodes[v].get("d1", 1))))) for v in nodes]
        e_vals = [max(1, int(round(float(G.nodes[v].get("d2", 1))))) for v in nodes]
        source = "embedded QA tuples (d1=b, d2=e)"
    else:
        # Derive from topology
        degree = dict(G.degree())
        core = nx.core_number(G)
        b_vals = [max(1, int(degree[v])) for v in nodes]
        e_vals = [max(1, int(core[v])) for v in nodes]
        source = "topology (b=degree, e=core_number)"

    # ── Step 2: PIM sector mapping via qa_mod (A1 compliant) ───────

    # Map each node's 'd' value to a sector via qa_mod
    d_vals = [b + e for b, e in zip(b_vals, e_vals)]
    sectors = np.array([qa_mod(d, MODULUS) for d in d_vals], dtype=np.int32)
    # Shift to 0-indexed for PIM (sectors are 1..24 from qa_mod)
    sectors_0 = sectors - 1  # now 0..23 for PIM

    print(f"  Sector distribution (mod-{MODULUS}):")
    sector_counts = Counter(sectors.tolist())
    for s in sorted(sector_counts.keys()):
        bar = "#" * (sector_counts[s] * 40 // n)
        print(f"    sector {s:>2}: {sector_counts[s]:>4} ({sector_counts[s]*100/n:5.1f}%) {bar}")

    # ── Step 3: PIM RESIDUE_SELECT for sector analysis ─────────────

    # Select prime sectors (coprime to 24): {1,5,7,11,13,17,19,23}
    prime_sectors_0 = {0, 4, 6, 10, 12, 16, 18, 22}  # 0-indexed
    prime_mask = RESIDUE_SELECT(sectors_0, prime_sectors_0)
    n_prime = int(np.sum(prime_mask))
    print(f"\n  Prime-sector nodes (coprime to 24): {n_prime}/{n} ({n_prime*100/n:.1f}%)")

    # ── Step 4: Build sector-partitioned CSR ───────────────────────

    edges_arr = np.array(
        [[node_idx[u], node_idx[v]] for u, v in G.edges()],
        dtype=np.int32,
    )
    # Add reverse edges for undirected
    edges_arr = np.vstack([edges_arr, edges_arr[:, ::-1]])

    sector_csr = build_sector_csr(sectors_0, edges_arr, MODULUS)

    total_csr_edges = sum(
        int(offsets[-1]) for offsets, _ in sector_csr.values()
        if len(offsets) > 0
    )
    print(f"  Sector-partitioned CSR: {total_csr_edges} directed edge entries across {MODULUS} sectors")

    # ── Step 5: Compute QA feature vectors ─────────────────────────

    features = {}
    for i, v in enumerate(nodes):
        vec, names = qa_feature_vector(float(b_vals[i]), float(e_vals[i]), mode="qa21")
        features[v] = vec

    # ── Step 6: Sector-aware phase analysis ────────────────────────

    # Use ROLLING_SUM_PHASE on sector occupancy
    sector_occupancy = np.zeros(MODULUS)
    for s in sectors_0:
        sector_occupancy[s] += 1
    rolling = ROLLING_SUM_PHASE(sector_occupancy, width=3)
    peak_sector = int(np.argmax(rolling)) + 1  # back to 1-indexed
    print(f"  Rolling sector occupancy peak: sector {peak_sector}")

    # ── Step 7: Spectral clustering (baseline vs QA) ───────────────

    results = {
        "graph": graph_name,
        "nodes": n,
        "edges": G.number_of_edges(),
        "k": k,
        "source": source,
        "prime_sector_fraction": round(n_prime / n, 4),
        "csr_edges": total_csr_edges,
        "peak_sector": peak_sector,
    }

    if has_gt:
        # Baseline
        W_base = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
        labels_base = spectral_cluster(W_base, k)
        pred_base = list(labels_base)

        # QA full kernel
        F_mat = np.array([features[v] for v in nodes])
        mu = F_mat.mean(axis=0, keepdims=True)
        sigma = F_mat.std(axis=0, keepdims=True) + 1e-8
        F_norm = (F_mat - mu) / sigma
        sq_dists = np.sum((F_norm[:, None, :] - F_norm[None, :, :]) ** 2, axis=2)
        A = W_base.copy()
        edge_dists = sq_dists[A > 0]
        tau_sq = np.median(edge_dists) + 1e-8
        W_qa = A * np.exp(-sq_dists / (2 * tau_sq))
        labels_qa = spectral_cluster(W_qa, k)
        pred_qa = list(labels_qa)

        results["baseline"] = {
            "purity": round(purity(pred_base, gt_labels), 4),
            "ARI": round(ari_score(pred_base, gt_labels), 4),
            "NMI": round(nmi_score(pred_base, gt_labels), 4),
        }
        results["qa_full"] = {
            "purity": round(purity(pred_qa, gt_labels), 4),
            "ARI": round(ari_score(pred_qa, gt_labels), 4),
            "NMI": round(nmi_score(pred_qa, gt_labels), 4),
        }
        results["delta"] = {
            metric: round(results["qa_full"][metric] - results["baseline"][metric], 4)
            for metric in ["purity", "ARI", "NMI"]
        }

    return results


def main():
    print("=" * 64)
    print("PIM + GRAPH FULL-STACK INTEGRATION")
    print("qa_pim + qa_graph + qa_observer — all three packages")
    print("=" * 64)

    all_results = {}

    graphs = [
        ("football", DATA / "football.graphml"),
        ("karate", DATA / "karate.graphml"),
        ("raman_qa21", DATA / "raman_qa21.graphml"),
    ]

    for name, path in graphs:
        if not path.exists():
            print(f"\n--- {name.upper()} --- SKIPPED (not found)")
            continue

        print(f"\n{'=' * 64}")
        print(f"  {name.upper()}")
        print(f"{'=' * 64}")

        t0 = time.perf_counter()
        result = analyze_graph(path, name)
        elapsed = time.perf_counter() - t0
        result["total_time_s"] = round(elapsed, 3)

        all_results[name] = result

        print(f"\n  Total pipeline time: {elapsed:.3f}s")

        if "baseline" in result and "qa_full" in result:
            print(f"\n  {'Mode':<12} {'Purity':>8} {'ARI':>8} {'NMI':>8}")
            print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
            for mode in ["baseline", "qa_full"]:
                m = result[mode]
                print(f"  {mode:<12} {m['purity']:>8.4f} {m['ARI']:>8.4f} {m['NMI']:>8.4f}")
            d = result["delta"]
            print(f"\n  Delta (QA - baseline): ARI {'+' if d['ARI']>=0 else ''}{d['ARI']:.4f}, "
                  f"NMI {'+' if d['NMI']>=0 else ''}{d['NMI']:.4f}")

    # Save
    out_path = HERE / "pim_integration_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
