#!/usr/bin/env python3
"""Sector concentration analysis — testing the prime-sector hypothesis.

For each graph, computes:
1. Sector distribution via qa_mod(d, 24) where d = b + e
2. Prime-sector fraction (nodes in sectors coprime to 24)
3. Sector entropy (how spread vs concentrated the distribution is)
4. QA kernel lift (ARI/NMI delta) where ground truth available
5. Correlation between prime fraction and QA lift

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/sector_analysis.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=sector_analysis, state_alphabet=sector_domain_signature"

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

from qa_graph.feature_map import qa_feature_vector
from qa_observer.core import qa_mod
from qa_pim.kernels import RESIDUE_SELECT

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MODULUS = 24

# Prime sectors: coprime to 24 (in 1-indexed QA space)
PRIME_SECTORS = {1, 5, 7, 11, 13, 17, 19, 23}


# ── Metrics ────────────────────────────────────────────────────────────

def _comb2(x):
    return 0.0 if x < 2 else x * (x - 1) / 2.0

def purity(pred, gt):
    n = len(pred)
    if n == 0: return 0.0
    clusters = {}
    for p, g in zip(pred, gt):
        clusters.setdefault(p, []).append(g)
    return sum(Counter(v).most_common(1)[0][1] for v in clusters.values()) / n

def ari_score(pred, gt):
    n = len(pred)
    if n < 2: return 0.0
    k, t = max(pred) + 1, max(gt) + 1
    cm = [[0] * t for _ in range(k)]
    for p, g in zip(pred, gt): cm[p][g] += 1
    sum_comb = a_sum = 0.0
    b_sums = [0] * t
    for i in range(k):
        rs = sum(cm[i]); a_sum += _comb2(rs)
        for j in range(t): sum_comb += _comb2(cm[i][j]); b_sums[j] += cm[i][j]
    b_sum = sum(_comb2(x) for x in b_sums)
    total = _comb2(n)
    exp = (a_sum * b_sum) / total if total else 0.0
    den = 0.5 * (a_sum + b_sum) - exp
    return 0.0 if abs(den) < 1e-12 else (sum_comb - exp) / den

def nmi_score(pred, gt):
    n = len(pred)
    if n == 0: return 0.0
    k, t = max(pred) + 1, max(gt) + 1
    cm = [[0] * t for _ in range(k)]
    for p, g in zip(pred, gt): cm[p][g] += 1
    row_s = [sum(cm[i]) for i in range(k)]
    col_s = [sum(cm[i][j] for i in range(k)) for j in range(t)]
    nf = float(n); mi = 0.0
    for i in range(k):
        for j in range(t):
            nij = cm[i][j]
            if nij == 0: continue
            mi += (nij / nf) * math.log((nij / nf) / ((row_s[i] / nf) * (col_s[j] / nf)))
    h_u = -sum((x / nf) * math.log(x / nf) for x in row_s if x > 0)
    h_v = -sum((x / nf) * math.log(x / nf) for x in col_s if x > 0)
    den = math.sqrt(h_u * h_v)
    return 0.0 if den <= 0 else mi / den

def spectral_cluster(W, k, seed=42):
    n = W.shape[0]
    d = W.sum(axis=1)
    di = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    L = np.eye(n) - np.diag(di) @ W @ np.diag(di)
    _, V = np.linalg.eigh(L)
    Z = V[:, :k]
    rn = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(rn > 1e-10, Z / rn, 0.0)
    rng = np.random.RandomState(seed)
    C = Z[rng.choice(n, k, replace=False)]
    for _ in range(100):
        labels = np.argmin(np.linalg.norm(Z[:, None, :] - C[None, :, :], axis=2), axis=1)
        nC = np.zeros_like(C)
        for c in range(k):
            m = labels == c
            nC[c] = Z[m].mean(axis=0) if m.any() else C[c]
        if np.allclose(nC, C): break
        C = nC
    return labels


# ── Sector entropy ─────────────────────────────────────────────────────

def sector_entropy(sectors, m=MODULUS):
    """Shannon entropy of sector distribution, normalized to [0, 1]."""
    counts = Counter(sectors)
    n = len(sectors)
    if n == 0:
        return 0.0
    probs = [c / n for c in counts.values()]
    H = -sum(p * math.log2(p) for p in probs if p > 0)
    H_max = math.log2(m)
    return H / H_max if H_max > 0 else 0.0


# ── Analyze one graph ──────────────────────────────────────────────────

def analyze_graph(graph_path, name):
    G = nx.read_graphml(str(graph_path)).to_undirected()
    nodes = list(G.nodes())
    n = len(nodes)

    # Ground truth
    gt_map = {v: int(d["value"]) for v, d in G.nodes(data=True) if "value" in d}
    has_gt = len(gt_map) == n

    # Extract (b, e)
    has_qa = all("d1" in G.nodes[v] and "d2" in G.nodes[v] for v in nodes[:5])
    if has_qa:
        b_vals = [max(1, int(round(abs(float(G.nodes[v].get("d1", 1)))))) for v in nodes]
        e_vals = [max(1, int(round(abs(float(G.nodes[v].get("d2", 1)))))) for v in nodes]
        source = "embedded"
    else:
        deg = dict(G.degree())
        core = nx.core_number(G)
        b_vals = [max(1, int(deg[v])) for v in nodes]
        e_vals = [max(1, int(core[v])) for v in nodes]
        source = "topology"

    # Sectors
    d_vals = [b + e for b, e in zip(b_vals, e_vals)]
    sectors = [qa_mod(d, MODULUS) for d in d_vals]

    # Sector stats
    sector_counts = Counter(sectors)
    peak_sector = sector_counts.most_common(1)[0][0]
    peak_frac = sector_counts[peak_sector] / n
    prime_count = sum(1 for s in sectors if s in PRIME_SECTORS)
    prime_frac = prime_count / n
    entropy = sector_entropy(sectors)
    n_occupied = len(sector_counts)

    result = {
        "graph": name,
        "nodes": n,
        "edges": G.number_of_edges(),
        "source": source,
        "peak_sector": peak_sector,
        "peak_fraction": round(peak_frac, 4),
        "prime_fraction": round(prime_frac, 4),
        "sector_entropy": round(entropy, 4),
        "sectors_occupied": n_occupied,
        "has_ground_truth": has_gt,
    }

    # QA lift if ground truth available
    if has_gt:
        gt_labels = [gt_map[v] for v in nodes]
        k = max(gt_labels) + 1

        # Features
        features = {}
        for i, v in enumerate(nodes):
            vec, _ = qa_feature_vector(float(b_vals[i]), float(e_vals[i]), mode="qa21")
            features[v] = vec

        # Baseline
        W_base = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
        pred_base = list(spectral_cluster(W_base, k))

        # QA full kernel
        F_mat = np.array([features[v] for v in nodes])
        mu = F_mat.mean(axis=0, keepdims=True)
        sigma = F_mat.std(axis=0, keepdims=True) + 1e-8
        F_norm = (F_mat - mu) / sigma
        sq = np.sum((F_norm[:, None, :] - F_norm[None, :, :]) ** 2, axis=2)
        A = W_base.copy()
        tau = np.median(sq[A > 0]) + 1e-8
        W_qa = A * np.exp(-sq / (2 * tau))
        pred_qa = list(spectral_cluster(W_qa, k))

        result["baseline_ARI"] = round(ari_score(pred_base, gt_labels), 4)
        result["baseline_NMI"] = round(nmi_score(pred_base, gt_labels), 4)
        result["qa_ARI"] = round(ari_score(pred_qa, gt_labels), 4)
        result["qa_NMI"] = round(nmi_score(pred_qa, gt_labels), 4)
        result["delta_ARI"] = round(result["qa_ARI"] - result["baseline_ARI"], 4)
        result["delta_NMI"] = round(result["qa_NMI"] - result["baseline_NMI"], 4)

    return result


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("SECTOR CONCENTRATION ANALYSIS — PRIME-SECTOR HYPOTHESIS")
    print("=" * 70)

    graphs = []
    for f in sorted(DATA.glob("*.graphml")):
        graphs.append((f.stem, f))

    results = []
    for name, path in graphs:
        print(f"\n  Analyzing {name}...", end=" ", flush=True)
        t0 = time.perf_counter()
        r = analyze_graph(path, name)
        elapsed = time.perf_counter() - t0
        r["time_s"] = round(elapsed, 3)
        results.append(r)
        print(f"done ({elapsed:.1f}s)")

    # Summary table
    print("\n" + "=" * 70)
    print("SECTOR CONCENTRATION SUMMARY")
    print("=" * 70)
    print(f"\n  {'Graph':<28} {'N':>5} {'Peak':>5} {'PkFr':>6} {'PrFr':>6} {'Ent':>6} {'Occ':>4} {'ΔARI':>7} {'ΔNMI':>7}")
    print(f"  {'-'*28} {'-'*5} {'-'*5} {'-'*6} {'-'*6} {'-'*6} {'-'*4} {'-'*7} {'-'*7}")

    for r in results:
        dARI = f"{r['delta_ARI']:+.4f}" if "delta_ARI" in r else "   n/a"
        dNMI = f"{r['delta_NMI']:+.4f}" if "delta_NMI" in r else "   n/a"
        print(f"  {r['graph']:<28} {r['nodes']:>5} {r['peak_sector']:>5} "
              f"{r['peak_fraction']:>6.3f} {r['prime_fraction']:>6.3f} "
              f"{r['sector_entropy']:>6.3f} {r['sectors_occupied']:>4} "
              f"{dARI:>7} {dNMI:>7}")

    # Correlation analysis (only for graphs with ground truth)
    gt_results = [r for r in results if "delta_ARI" in r]
    if len(gt_results) >= 3:
        primes = [r["prime_fraction"] for r in gt_results]
        d_ari = [r["delta_ARI"] for r in gt_results]
        d_nmi = [r["delta_NMI"] for r in gt_results]
        entropies = [r["sector_entropy"] for r in gt_results]

        # Simple Pearson correlation
        def pearson(x, y):
            n = len(x)
            if n < 3: return 0.0
            mx, my = sum(x)/n, sum(y)/n
            num = sum((xi-mx)*(yi-my) for xi, yi in zip(x, y))
            dx = math.sqrt(sum((xi-mx)**2 for xi in x))
            dy = math.sqrt(sum((yi-my)**2 for yi in y))
            return num / (dx * dy) if dx * dy > 0 else 0.0

        print(f"\n  CORRELATIONS (n={len(gt_results)} graphs with ground truth):")
        print(f"    r(prime_fraction, ΔARI) = {pearson(primes, d_ari):+.3f}")
        print(f"    r(prime_fraction, ΔNMI) = {pearson(primes, d_nmi):+.3f}")
        print(f"    r(sector_entropy, ΔARI) = {pearson(entropies, d_ari):+.3f}")
        print(f"    r(sector_entropy, ΔNMI) = {pearson(entropies, d_nmi):+.3f}")

    # Save
    out_path = HERE / "sector_analysis_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: {out_path}")


if __name__ == "__main__":
    main()
