#!/usr/bin/env python3
"""Sweep over (b,e) extraction methods to test prime-sector hypothesis.

For the football graph (best test case — 115 nodes, strong ground truth),
tests multiple ways to extract (b,e) per node and measures how the
resulting prime-sector fraction correlates with QA kernel lift.

This is a controlled experiment: same graph, same topology, same ground
truth, different (b,e) extraction → different sector distribution →
different QA lift. Isolates the effect of QA encoding quality.

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/extraction_sweep.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=extraction_sweep, state_alphabet=sector_domain_signature"

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

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MODULUS = 24
PRIME_SECTORS = {1, 5, 7, 11, 13, 17, 19, 23}


# ── Metrics (compact) ─────────────────────────────────────────────────

def _c2(x): return 0.0 if x < 2 else x * (x - 1) / 2.0

def ari_score(pred, gt):
    n = len(pred)
    if n < 2: return 0.0
    k, t = max(pred) + 1, max(gt) + 1
    cm = [[0]*t for _ in range(k)]
    for p, g in zip(pred, gt): cm[p][g] += 1
    sc = a = 0.0; bs = [0]*t
    for i in range(k):
        rs = sum(cm[i]); a += _c2(rs)
        for j in range(t): sc += _c2(cm[i][j]); bs[j] += cm[i][j]
    b = sum(_c2(x) for x in bs); tot = _c2(n)
    ex = (a*b)/tot if tot else 0.0; den = 0.5*(a+b)-ex
    return 0.0 if abs(den)<1e-12 else (sc-ex)/den

def nmi_score(pred, gt):
    n = len(pred)
    if n == 0: return 0.0
    k, t = max(pred)+1, max(gt)+1
    cm = [[0]*t for _ in range(k)]
    for p, g in zip(pred, gt): cm[p][g] += 1
    rs = [sum(cm[i]) for i in range(k)]
    cs = [sum(cm[i][j] for i in range(k)) for j in range(t)]
    nf = float(n); mi = 0.0
    for i in range(k):
        for j in range(t):
            nij = cm[i][j]
            if nij == 0: continue
            mi += (nij/nf)*math.log((nij/nf)/((rs[i]/nf)*(cs[j]/nf)))
    hu = -sum((x/nf)*math.log(x/nf) for x in rs if x>0)
    hv = -sum((x/nf)*math.log(x/nf) for x in cs if x>0)
    d = math.sqrt(hu*hv)
    return 0.0 if d<=0 else mi/d

def spectral_cluster(W, k, seed=42):
    n = W.shape[0]; d = W.sum(axis=1)
    di = np.where(d>0, 1.0/np.sqrt(d), 0.0)
    L = np.eye(n) - np.diag(di)@W@np.diag(di)
    _, V = np.linalg.eigh(L); Z = V[:,:k]
    rn = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(rn>1e-10, Z/rn, 0.0)
    rng = np.random.RandomState(seed)
    C = Z[rng.choice(n, k, replace=False)]
    for _ in range(100):
        lab = np.argmin(np.linalg.norm(Z[:,None,:]-C[None,:,:], axis=2), axis=1)
        nC = np.zeros_like(C)
        for c in range(k):
            m = lab==c; nC[c] = Z[m].mean(axis=0) if m.any() else C[c]
        if np.allclose(nC,C): break
        C = nC
    return lab


# ── Extraction methods ─────────────────────────────────────────────────

def extract_degree_core(G, nodes):
    """b=degree, e=core_number (default method)."""
    deg = dict(G.degree()); core = nx.core_number(G)
    return [(max(1, int(deg[v])), max(1, int(core[v]))) for v in nodes]

def extract_degree_clustering(G, nodes):
    """b=degree, e=quantized clustering coefficient (×12)."""
    deg = dict(G.degree()); clust = nx.clustering(G)
    return [(max(1, int(deg[v])), max(1, int(round(clust[v]*12))+1)) for v in nodes]

def extract_degree_triangles(G, nodes):
    """b=degree, e=triangle count."""
    deg = dict(G.degree()); tri = nx.triangles(G)
    return [(max(1, int(deg[v])), max(1, int(tri[v])+1)) for v in nodes]

def extract_core_triangles(G, nodes):
    """b=core_number, e=triangle count."""
    core = nx.core_number(G); tri = nx.triangles(G)
    return [(max(1, int(core[v])), max(1, int(tri[v])+1)) for v in nodes]

def extract_degree_pagerank(G, nodes):
    """b=degree, e=quantized pagerank (×1000)."""
    deg = dict(G.degree()); pr = nx.pagerank(G)
    return [(max(1, int(deg[v])), max(1, int(round(pr[v]*1000)))) for v in nodes]

def extract_betweenness_closeness(G, nodes):
    """b=quantized betweenness(×100), e=quantized closeness(×100)."""
    btw = nx.betweenness_centrality(G); cls = nx.closeness_centrality(G)
    return [(max(1, int(round(btw[v]*100))+1), max(1, int(round(cls[v]*100)))) for v in nodes]

def extract_pagerank_clustering(G, nodes):
    """b=quantized pagerank(×1000), e=quantized clustering(×12)."""
    pr = nx.pagerank(G); cl = nx.clustering(G)
    return [(max(1, int(round(pr[v]*1000))), max(1, int(round(cl[v]*12))+1)) for v in nodes]


METHODS = {
    "degree_core": extract_degree_core,
    "degree_clust": extract_degree_clustering,
    "degree_tri": extract_degree_triangles,
    "core_tri": extract_core_triangles,
    "degree_pr": extract_degree_pagerank,
    "btw_cls": extract_betweenness_closeness,
    "pr_clust": extract_pagerank_clustering,
}


# ── Run sweep ──────────────────────────────────────────────────────────

def run_sweep(graph_path, graph_name):
    G = nx.read_graphml(str(graph_path)).to_undirected()
    nodes = list(G.nodes())
    n = len(nodes)
    gt_map = {v: int(d["value"]) for v, d in G.nodes(data=True) if "value" in d}
    if len(gt_map) != n:
        return []
    gt_labels = [gt_map[v] for v in nodes]
    k = max(gt_labels) + 1

    # Baseline (unweighted)
    W_base = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
    pred_base = list(spectral_cluster(W_base, k))
    base_ari = ari_score(pred_base, gt_labels)
    base_nmi = nmi_score(pred_base, gt_labels)

    results = []
    for method_name, extract_fn in METHODS.items():
        pairs = extract_fn(G, nodes)
        b_vals = [p[0] for p in pairs]
        e_vals = [p[1] for p in pairs]
        d_vals = [b + e for b, e in zip(b_vals, e_vals)]
        sectors = [qa_mod(d, MODULUS) for d in d_vals]

        prime_frac = sum(1 for s in sectors if s in PRIME_SECTORS) / n
        counts = Counter(sectors)
        peak_sec = counts.most_common(1)[0][0]
        peak_frac = counts[peak_sec] / n

        # QA full kernel
        features = {}
        for i, v in enumerate(nodes):
            vec, _ = qa_feature_vector(float(b_vals[i]), float(e_vals[i]), mode="qa21")
            features[v] = vec

        F_mat = np.array([features[v] for v in nodes])
        mu = F_mat.mean(axis=0, keepdims=True)
        sig = F_mat.std(axis=0, keepdims=True) + 1e-8
        Fn = (F_mat - mu) / sig
        sq = np.sum((Fn[:, None, :] - Fn[None, :, :]) ** 2, axis=2)
        A = W_base.copy()
        tau = np.median(sq[A > 0]) + 1e-8
        W_qa = A * np.exp(-sq / (2 * tau))
        pred_qa = list(spectral_cluster(W_qa, k))

        qa_ari = ari_score(pred_qa, gt_labels)
        qa_nmi = nmi_score(pred_qa, gt_labels)

        results.append({
            "method": method_name,
            "prime_fraction": round(prime_frac, 4),
            "peak_sector": peak_sec,
            "peak_fraction": round(peak_frac, 4),
            "baseline_ARI": round(base_ari, 4),
            "qa_ARI": round(qa_ari, 4),
            "delta_ARI": round(qa_ari - base_ari, 4),
            "delta_NMI": round(qa_nmi - base_nmi, 4),
        })

    return results


def main():
    print("=" * 70)
    print("EXTRACTION METHOD SWEEP — CONTROLLED EXPERIMENT")
    print("Same graph, same topology, different (b,e) → different QA lift")
    print("=" * 70)

    for graph_name in ["football", "karate"]:
        path = DATA / f"{graph_name}.graphml"
        if not path.exists():
            continue

        print(f"\n  {graph_name.upper()} ({graph_name}.graphml)")
        print(f"  {'-'*64}")

        results = run_sweep(path, graph_name)
        if not results:
            print("    No ground truth — skipped")
            continue

        print(f"\n  {'Method':<18} {'PrFr':>6} {'Peak':>5} {'ΔARI':>8} {'ΔNMI':>8}")
        print(f"  {'-'*18} {'-'*6} {'-'*5} {'-'*8} {'-'*8}")

        # Sort by prime fraction to show the gradient
        results.sort(key=lambda r: r["prime_fraction"])
        for r in results:
            flag = " ***" if r["delta_ARI"] > 0.01 else ""
            print(f"  {r['method']:<18} {r['prime_fraction']:>6.3f} {r['peak_sector']:>5} "
                  f"{r['delta_ARI']:>+8.4f} {r['delta_NMI']:>+8.4f}{flag}")

        # Correlation
        pf = [r["prime_fraction"] for r in results]
        da = [r["delta_ARI"] for r in results]
        dn = [r["delta_NMI"] for r in results]
        n = len(pf)
        if n >= 3:
            def pearson(x, y):
                mx, my = sum(x)/n, sum(y)/n
                num = sum((a-mx)*(b-my) for a, b in zip(x, y))
                dx = math.sqrt(sum((a-mx)**2 for a in x))
                dy = math.sqrt(sum((b-my)**2 for b in y))
                return num/(dx*dy) if dx*dy>0 else 0.0
            print(f"\n  r(prime_fraction, ΔARI) = {pearson(pf, da):+.3f}  (n={n} methods)")
            print(f"  r(prime_fraction, ΔNMI) = {pearson(pf, dn):+.3f}")

    # Save
    out_path = HERE / "extraction_sweep_results.json"
    all_results = {}
    for graph_name in ["football", "karate"]:
        path = DATA / f"{graph_name}.graphml"
        if path.exists():
            all_results[graph_name] = run_sweep(path, graph_name)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved: {out_path}")


if __name__ == "__main__":
    main()
