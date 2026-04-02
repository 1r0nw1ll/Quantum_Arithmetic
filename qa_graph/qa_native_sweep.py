#!/usr/bin/env python3
"""QA-native prime-sector hypothesis test.

Generates graphs entirely from QA dynamics — no randomness, no continuous
functions, no stochastic models. 100% Theorem NT compliant.

For each modulus m:
  1. Generate all QA states (b,e) in {1,...,m}^2
  2. Build edges from T-operator: (b,e) → (e, qa_mod(b+e, m))
     [Fibonacci shift: next_b=e, next_e=d=b+e, A1 compliant]
  3. Ground truth = orbit membership (cosmos/satellite/singularity)
  4. Extract qa21 features from each node's (b,e)
  5. Run baseline vs QA-weighted spectral clustering
  6. Measure ΔARI, correlate with prime-sector fraction

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/qa_native_sweep.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=qa_native_sweep, state_alphabet=pisano_orbit"

import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from qa_graph.feature_map import qa_feature_vector
from qa_observer.core import qa_mod

HERE = Path(__file__).resolve().parent
PRIME_SECTORS_24 = {1, 5, 7, 11, 13, 17, 19, 23}


# ── Compact metrics ────────────────────────────────────────────────────

def _c2(x): return 0.0 if x < 2 else x*(x-1)/2.0

def ari_score(pred, gt):
    n = len(pred)
    if n < 2: return 0.0
    k, t = max(pred)+1, max(gt)+1
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
    return 0.0 if d <= 0 else mi/d

def spectral_cluster(W, k, seed=42):
    n = W.shape[0]
    if n < k or k < 2: return np.zeros(n, dtype=int)
    d = W.sum(axis=1)
    di = np.where(d > 0, 1.0/np.sqrt(d), 0.0)
    L = np.eye(n) - np.diag(di) @ W @ np.diag(di)
    _, V = np.linalg.eigh(L)
    Z = V[:, :k]
    rn = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(rn > 1e-10, Z / rn, 0.0)
    rng = np.random.RandomState(seed)  # noqa: T2-D-5 — k-means init only, not QA state
    C = Z[rng.choice(n, min(k, n), replace=False)]
    for _ in range(100):
        lab = np.argmin(np.linalg.norm(Z[:, None, :] - C[None, :, :], axis=2), axis=1)
        nC = np.zeros_like(C)
        for c in range(k):
            m = lab == c
            nC[c] = Z[m].mean(axis=0) if m.any() else C[c]
        if np.allclose(nC, C): break
        C = nC
    return lab


# ── QA-native graph generation ─────────────────────────────────────────

def qa_step(b, e, m):
    """Single T-operator step: Fibonacci shift, A1 compliant.

    (b, e) → (e, qa_mod(b + e, m))
    """
    return e, qa_mod(b + e, m)


def compute_orbit(b, e, m, max_steps=1000):
    """Trace orbit of (b,e) under T-operator, return period."""
    seen = {}
    state = (b, e)
    for step in range(max_steps):
        if state in seen:
            return step - seen[state]
        seen[state] = step
        state = qa_step(state[0], state[1], m)
    return max_steps  # non-periodic (shouldn't happen for finite m)


def classify_orbit_by_period(period, m):
    """Classify orbit by period relative to Pisano period pi(m)."""
    # For mod-9: pi(9)=24 (cosmos), 8 (satellite), 1 (singularity)
    # For mod-m: use period directly as label
    if period == 1:
        return 0  # singularity
    elif period <= m:
        return 1  # short orbit (satellite-like)
    else:
        return 2  # long orbit (cosmos-like)


def build_qa_graph(m):
    """Build QA transition graph for modulus m.

    Nodes: all (b,e) in {1,...,m}^2
    Edges: T-operator transitions (b,e) → (e, qa_mod(b+e, m))
    Ground truth: orbit period classification
    """
    nodes = []
    node_map = {}
    b_vals = []
    e_vals = []

    # Generate all states
    idx = 0
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            node_map[(b, e)] = idx
            nodes.append((b, e))
            b_vals.append(b)
            e_vals.append(e)
            idx += 1

    n = len(nodes)

    # Build edges from T-operator
    edges = []
    for i, (b, e) in enumerate(nodes):
        nb, ne = qa_step(b, e, m)
        j = node_map.get((nb, ne))
        if j is not None:
            edges.append((i, j))

    # Also add reverse edges for undirected clustering
    edge_set = set()
    for u, v in edges:
        edge_set.add((u, v))
        edge_set.add((v, u))

    # Build adjacency matrix
    W = np.zeros((n, n))
    for u, v in edge_set:
        W[u, v] = 1.0

    # Ground truth: orbit classification
    orbits = []
    for b, e in nodes:
        period = compute_orbit(b, e, m)
        orbits.append(classify_orbit_by_period(period, m))

    k = len(set(orbits))

    return {
        "nodes": nodes,
        "b_vals": b_vals,
        "e_vals": e_vals,
        "W": W,
        "orbits": orbits,
        "k": k,
        "n": n,
        "n_edges": len(edge_set) // 2,
        "m": m,
    }


# ── Single modulus trial ───────────────────────────────────────────────

def run_modulus(m):
    """Run full pipeline for one modulus."""
    data = build_qa_graph(m)
    nodes = data["nodes"]
    b_vals = data["b_vals"]
    e_vals = data["e_vals"]
    W_base = data["W"]
    gt = data["orbits"]
    k = data["k"]
    n = data["n"]

    if k < 2:
        return None  # can't cluster with <2 classes

    # Sector analysis
    d_vals = [b + e for b, e in zip(b_vals, e_vals)]
    sectors_24 = [qa_mod(d, 24) for d in d_vals]
    prime_frac = sum(1 for s in sectors_24 if s in PRIME_SECTORS_24) / n

    # Also compute prime fraction relative to m itself
    from math import gcd
    prime_sectors_m = {s for s in range(1, m + 1) if gcd(s, m) == 1}
    sectors_m = [qa_mod(d, m) for d in d_vals]
    prime_frac_m = sum(1 for s in sectors_m if s in prime_sectors_m) / n

    # Baseline spectral
    pred_base = list(spectral_cluster(W_base, k))
    base_ari = ari_score(pred_base, gt)
    base_nmi = nmi_score(pred_base, gt)

    # QA full-21 kernel
    features = []
    for b, e in nodes:
        vec, _ = qa_feature_vector(float(b), float(e), mode="qa21")
        features.append(vec)

    F_mat = np.array(features)
    mu = F_mat.mean(axis=0, keepdims=True)
    sig = F_mat.std(axis=0, keepdims=True) + 1e-8
    Fn = (F_mat - mu) / sig
    sq = np.sum((Fn[:, None, :] - Fn[None, :, :]) ** 2, axis=2)
    A = W_base.copy()
    ed = sq[A > 0]
    tau = np.median(ed) + 1e-8 if len(ed) > 0 else 1.0
    W_qa = A * np.exp(-sq / (2 * tau))
    pred_qa = list(spectral_cluster(W_qa, k))
    qa_ari = ari_score(pred_qa, gt)
    qa_nmi = nmi_score(pred_qa, gt)

    # Orbit distribution
    orbit_counts = Counter(gt)

    return {
        "m": m,
        "n": n,
        "n_edges": data["n_edges"],
        "k": k,
        "orbit_distribution": dict(orbit_counts),
        "prime_frac_mod24": round(prime_frac, 4),
        "prime_frac_mod_m": round(prime_frac_m, 4),
        "euler_phi_m": len(prime_sectors_m),
        "phi_over_m": round(len(prime_sectors_m) / m, 4),
        "baseline_ARI": round(base_ari, 4),
        "baseline_NMI": round(base_nmi, 4),
        "qa_ARI": round(qa_ari, 4),
        "qa_NMI": round(qa_nmi, 4),
        "delta_ARI": round(qa_ari - base_ari, 4),
        "delta_NMI": round(qa_nmi - base_nmi, 4),
    }


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 74)
    print("QA-NATIVE SWEEP — PRIME-SECTOR HYPOTHESIS ON T-OPERATOR GRAPHS")
    print("100% QA-native: graphs from T-operator, communities from orbits")
    print("=" * 74)

    # Sweep moduli — each gives a different graph with different properties
    moduli = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 21, 24, 25]

    results = []
    for m in moduli:
        print(f"  m={m:>2} (n={m*m:>4})...", end=" ", flush=True)
        t0 = time.perf_counter()
        r = run_modulus(m)
        elapsed = time.perf_counter() - t0
        if r is None:
            print("SKIPPED (< 2 orbit classes)")
            continue
        r["time_s"] = round(elapsed, 3)
        results.append(r)
        print(f"k={r['k']} φ/m={r['phi_over_m']:.3f} "
              f"PrFr24={r['prime_frac_mod24']:.3f} "
              f"ΔARI={r['delta_ARI']:+.4f} ({elapsed:.2f}s)")

    # Summary
    print("\n" + "=" * 74)
    print("RESULTS")
    print("=" * 74)
    print(f"\n  {'m':>3} {'N':>5} {'K':>2} {'φ/m':>5} {'Pr24':>6} {'PrM':>6} "
          f"{'BseARI':>7} {'QA_ARI':>7} {'ΔARI':>8} {'ΔNMI':>8}")
    print(f"  {'-'*3} {'-'*5} {'-'*2} {'-'*5} {'-'*6} {'-'*6} "
          f"{'-'*7} {'-'*7} {'-'*8} {'-'*8}")

    for r in results:
        flag = " *" if r["delta_ARI"] > 0.005 else ""
        print(f"  {r['m']:>3} {r['n']:>5} {r['k']:>2} {r['phi_over_m']:>5.3f} "
              f"{r['prime_frac_mod24']:>6.3f} {r['prime_frac_mod_m']:>6.3f} "
              f"{r['baseline_ARI']:>7.4f} {r['qa_ARI']:>7.4f} "
              f"{r['delta_ARI']:>+8.4f} {r['delta_NMI']:>+8.4f}{flag}")

    # Correlations
    if len(results) >= 5:
        def pearson(x, y):
            n = len(x)
            mx, my = sum(x)/n, sum(y)/n
            num = sum((a-mx)*(b-my) for a, b in zip(x, y))
            dx = math.sqrt(sum((a-mx)**2 for a in x))
            dy = math.sqrt(sum((b-my)**2 for b in y))
            return num/(dx*dy) if dx*dy > 0 else 0.0

        def p_approx(r, n):
            if abs(r) >= 1.0 or n <= 2: return 0.0
            t = r * math.sqrt((n-2)/(1-r*r))
            return 2 * (1 - 0.5*(1 + math.erf(abs(t)/math.sqrt(2))))

        pf24 = [r["prime_frac_mod24"] for r in results]
        pfm  = [r["prime_frac_mod_m"] for r in results]
        phi  = [r["phi_over_m"] for r in results]
        da   = [r["delta_ARI"] for r in results]
        dn   = [r["delta_NMI"] for r in results]
        n_r  = len(results)

        print(f"\n  CORRELATIONS (n={n_r} moduli, QA-native graphs):")
        r1 = pearson(pf24, da)
        print(f"    r(prime_frac_mod24, ΔARI) = {r1:+.4f}  p ≈ {p_approx(r1, n_r):.4f}")
        r2 = pearson(pfm, da)
        print(f"    r(prime_frac_mod_m, ΔARI) = {r2:+.4f}  p ≈ {p_approx(r2, n_r):.4f}")
        r3 = pearson(phi, da)
        print(f"    r(φ(m)/m, ΔARI)           = {r3:+.4f}  p ≈ {p_approx(r3, n_r):.4f}")
        r4 = pearson(pf24, dn)
        print(f"    r(prime_frac_mod24, ΔNMI) = {r4:+.4f}  p ≈ {p_approx(r4, n_r):.4f}")
        r5 = pearson(phi, dn)
        print(f"    r(φ(m)/m, ΔNMI)           = {r5:+.4f}  p ≈ {p_approx(r5, n_r):.4f}")

    # Save
    out_path = HERE / "qa_native_sweep_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: {out_path}")


if __name__ == "__main__":
    main()
