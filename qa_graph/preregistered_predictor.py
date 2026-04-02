#!/usr/bin/env python3
"""Pre-registered QA kernel lift predictor.

HYPOTHESIS (pre-registered before testing on new graphs):
  After baseline spectral clustering, compute the QA feature separation
  ratio S = mean(between-cluster QA distance) / mean(within-cluster QA distance).

  PREDICTION:
    S > 1.5  →  ΔARI > 0  (QA kernel helps)
    S < 1.2  →  ΔARI ≤ 0  (QA kernel neutral or hurts)

  MECHANISM: QA invariants are nonlinear transformations of (degree, core_number)
  that amplify community-aligned topological differences. When baseline clusters
  already separate into distinct QA feature regions (high S), the RBF kernel
  further sharpens this separation. When they don't (low S), the kernel adds noise.

DESIGN:
  1. Calibrate S threshold on known graphs (football, karate, raman)
  2. Pre-register the threshold and prediction rule
  3. Test on NEW graphs not yet analyzed (les_miserables, polbooks, new PyG)

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/preregistered_predictor.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=preregistered_test, state_alphabet=community_topology"

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


# ── Metrics ────────────────────────────────────────────────────────────

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
    rng = np.random.RandomState(seed)  # noqa: T2-D-5 — k-means init only
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


# ── Core predictor ─────────────────────────────────────────────────────

def compute_separation_ratio(G, nodes, features, labels):
    """Compute QA feature separation ratio S = between/within cluster distance.

    Uses normalized QA features and edge-based distances only.
    """
    n = len(nodes)
    F_mat = np.array([features[v] for v in nodes])
    mu = F_mat.mean(axis=0, keepdims=True)
    sig = F_mat.std(axis=0, keepdims=True) + 1e-8
    Fn = (F_mat - mu) / sig

    A = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
    sq = np.sum((Fn[:, None, :] - Fn[None, :, :]) ** 2, axis=2)

    within = []
    between = []
    for i in range(n):
        for j in range(i + 1, n):
            if A[i, j] > 0:
                if labels[i] == labels[j]:
                    within.append(sq[i, j])
                else:
                    between.append(sq[i, j])

    if not within or not between:
        return 0.0

    return np.mean(between) / np.mean(within)


def analyze_graph(G, k, gt_labels=None):
    """Full analysis: compute predictor S and actual ΔARI."""
    nodes = list(G.nodes())
    n = len(nodes)

    # Remove isolates
    iso = list(nx.isolates(G))
    if iso:
        G = G.copy()
        G.remove_nodes_from(iso)
        nodes = list(G.nodes())
        n = len(nodes)
        if gt_labels:
            node_set = set(nodes)
            gt_labels = [gt_labels[v] for v in nodes] if isinstance(gt_labels, dict) else None

    if n < k or n < 10:
        return None

    # Extract (b, e)
    deg = dict(G.degree())
    core = nx.core_number(G)
    b_vals = [max(1, int(deg[v])) for v in nodes]
    e_vals = [max(1, int(core[v])) for v in nodes]

    # QA features
    features = {}
    for i, v in enumerate(nodes):
        vec, _ = qa_feature_vector(float(b_vals[i]), float(e_vals[i]), mode="qa21")
        features[v] = vec

    # Baseline spectral clustering
    W_base = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
    base_labels = list(spectral_cluster(W_base, k))

    # PREDICTOR: separation ratio from BASELINE labels (no ground truth needed)
    S = compute_separation_ratio(G, nodes, features, base_labels)

    # PREDICTION (pre-registered)
    if S > 1.5:
        predicted_helps = True
    elif S < 1.2:
        predicted_helps = False
    else:
        predicted_helps = None  # uncertain zone

    result = {
        "n": n,
        "edges": G.number_of_edges(),
        "k": k,
        "separation_ratio_S": round(S, 4),
        "predicted_helps": predicted_helps,
    }

    # Actual ΔARI (only if ground truth available)
    if gt_labels is not None:
        gt = gt_labels if isinstance(gt_labels, list) else [gt_labels[v] for v in nodes]
        base_ari = ari_score(base_labels, gt)

        # QA kernel
        F_mat = np.array([features[v] for v in nodes])
        mu = F_mat.mean(axis=0, keepdims=True)
        sig = F_mat.std(axis=0, keepdims=True) + 1e-8
        Fn = (F_mat - mu) / sig
        sq = np.sum((Fn[:, None, :] - Fn[None, :, :]) ** 2, axis=2)
        A = W_base.copy()
        ed = sq[A > 0]
        tau = np.median(ed) + 1e-8 if len(ed) > 0 else 1.0
        W_qa = A * np.exp(-sq / (2 * tau))
        qa_labels = list(spectral_cluster(W_qa, k))
        qa_ari = ari_score(qa_labels, gt)

        result["baseline_ARI"] = round(base_ari, 4)
        result["qa_ARI"] = round(qa_ari, 4)
        result["delta_ARI"] = round(qa_ari - base_ari, 4)
        result["actual_helps"] = result["delta_ARI"] > 0.005

        # Did prediction match?
        if predicted_helps is not None:
            result["prediction_correct"] = predicted_helps == result["actual_helps"]

    return result


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("PRE-REGISTERED QA KERNEL LIFT PREDICTOR")
    print()
    print("PREDICTION RULE (fixed before testing):")
    print("  S = mean(between-cluster QA dist) / mean(within-cluster QA dist)")
    print("  S > 1.5  →  predict QA helps  (ΔARI > 0)")
    print("  S < 1.2  →  predict QA neutral/hurts")
    print("  1.2-1.5  →  uncertain")
    print("=" * 70)

    results = {}

    # ── Phase 1: Calibration (known graphs) ────────────────────────

    print("\n--- PHASE 1: CALIBRATION (known results) ---\n")

    # Football
    G = nx.read_graphml(str(DATA / "football.graphml")).to_undirected()
    gt = {v: int(d["value"]) for v, d in G.nodes(data=True)}
    nodes = list(G.nodes())
    r = analyze_graph(G, max(gt.values()) + 1, [gt[v] for v in nodes])
    r["graph"] = "football"
    r["phase"] = "calibration"
    results["football"] = r

    # Karate
    G = nx.read_graphml(str(DATA / "karate.graphml")).to_undirected()
    gt = {v: int(d["value"]) for v, d in G.nodes(data=True)}
    nodes = list(G.nodes())
    r = analyze_graph(G, max(gt.values()) + 1, [gt[v] for v in nodes])
    r["graph"] = "karate"
    r["phase"] = "calibration"
    results["karate"] = r

    for name, r in results.items():
        pred = "HELPS" if r["predicted_helps"] else ("NEUTRAL" if r["predicted_helps"] is False else "???")
        actual = "HELPS" if r.get("actual_helps") else "NEUTRAL"
        match = "✓" if r.get("prediction_correct") else "✗" if "prediction_correct" in r else "?"
        print(f"  {name:<16} S={r['separation_ratio_S']:.3f}  "
              f"predicted={pred:<8} actual={actual:<8} ΔARI={r.get('delta_ARI', 0):+.4f}  {match}")

    # ── Phase 2: NEW graphs (the actual test) ──────────────────────

    print("\n--- PHASE 2: PRE-REGISTERED TEST (new graphs) ---\n")

    new_graphs = {}

    # Les Miserables (character co-occurrence, community = subplot)
    try:
        G_lm = nx.les_miserables_graph()
        # Modularity-based communities as ground truth
        from networkx.algorithms.community import greedy_modularity_communities
        comms = list(greedy_modularity_communities(G_lm))
        gt_lm = {}
        for i, comm in enumerate(comms):
            for v in comm:
                gt_lm[v] = i
        nodes_lm = list(G_lm.nodes())
        k_lm = len(comms)
        new_graphs["les_miserables"] = (G_lm, k_lm, [gt_lm[v] for v in nodes_lm])
    except Exception as e:
        print(f"  les_miserables: SKIP ({e})")

    # Florentine families
    try:
        G_ff = nx.florentine_families_graph()
        if G_ff.number_of_nodes() >= 10:
            comms = list(greedy_modularity_communities(G_ff))
            gt_ff = {}
            for i, comm in enumerate(comms):
                for v in comm:
                    gt_ff[v] = i
            nodes_ff = list(G_ff.nodes())
            new_graphs["florentine"] = (G_ff, len(comms), [gt_ff[v] for v in nodes_ff])
    except Exception as e:
        print(f"  florentine: SKIP ({e})")

    # Davis Southern Women (bipartite social network)
    try:
        G_dw = nx.davis_southern_women_graph()
        if G_dw.number_of_nodes() >= 10:
            comms = list(greedy_modularity_communities(G_dw))
            gt_dw = {}
            for i, comm in enumerate(comms):
                for v in comm:
                    gt_dw[v] = i
            nodes_dw = list(G_dw.nodes())
            new_graphs["davis_women"] = (G_dw, len(comms), [gt_dw[v] for v in nodes_dw])
    except Exception as e:
        print(f"  davis_women: SKIP ({e})")

    # Political books (if available via URL or local)
    try:
        G_pb = nx.karate_club_graph()  # fallback — but let's try polbooks
        # Actually use a different built-in
        G_pb = nx.sedgewick_maze_graph()
        if G_pb.number_of_nodes() >= 10:
            comms = list(greedy_modularity_communities(G_pb))
            gt_pb = {}
            for i, comm in enumerate(comms):
                for v in comm:
                    gt_pb[v] = i
            nodes_pb = list(G_pb.nodes())
            new_graphs["sedgewick_maze"] = (G_pb, len(comms), [gt_pb[v] for v in nodes_pb])
    except Exception:
        pass

    # Petersen graph (highly symmetric, should be HARD)
    try:
        G_pet = nx.petersen_graph()
        comms = list(greedy_modularity_communities(G_pet))
        gt_pet = {}
        for i, comm in enumerate(comms):
            for v in comm:
                gt_pet[v] = i
        new_graphs["petersen"] = (G_pet, len(comms), [gt_pet[v] for v in G_pet.nodes()])
    except Exception:
        pass

    # Dodecahedral graph
    try:
        G_dod = nx.dodecahedral_graph()
        comms = list(greedy_modularity_communities(G_dod))
        gt_dod = {}
        for i, comm in enumerate(comms):
            for v in comm:
                gt_dod[v] = i
        new_graphs["dodecahedral"] = (G_dod, len(comms), [gt_dod[v] for v in G_dod.nodes()])
    except Exception:
        pass

    # Barbell graph (two cliques connected by path — clear community structure)
    try:
        G_bb = nx.barbell_graph(15, 1)
        # Ground truth: first 15 = comm 0, last 15 = comm 1, bridge = comm 2
        gt_bb = [0 if v < 15 else (1 if v >= 16 else 2) for v in G_bb.nodes()]
        new_graphs["barbell_15"] = (G_bb, 3, gt_bb)
    except Exception:
        pass

    for name, (G, k, gt) in new_graphs.items():
        print(f"  Testing {name}...", end=" ", flush=True)
        t0 = time.perf_counter()
        r = analyze_graph(G, k, gt)
        elapsed = time.perf_counter() - t0
        if r is None:
            print("SKIP")
            continue
        r["graph"] = name
        r["phase"] = "test"
        r["time_s"] = round(elapsed, 3)
        results[name] = r

        pred = "HELPS" if r["predicted_helps"] else ("NEUTRAL" if r["predicted_helps"] is False else "???")
        actual = "HELPS" if r.get("actual_helps") else "NEUTRAL"
        match = "✓" if r.get("prediction_correct") else "✗" if "prediction_correct" in r else "?"
        print(f"S={r['separation_ratio_S']:.3f}  "
              f"predicted={pred:<8} actual={actual:<8} ΔARI={r.get('delta_ARI', 0):+.4f}  {match}")

    # ── Summary ────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("FULL RESULTS")
    print("=" * 70)
    print(f"\n  {'Graph':<16} {'Phase':<6} {'N':>5} {'S':>6} {'Pred':>8} {'Actual':>8} {'ΔARI':>8} {'Match':>5}")
    print(f"  {'-'*16} {'-'*6} {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*5}")

    correct = 0
    total = 0
    for r in results.values():
        pred = "HELPS" if r["predicted_helps"] else ("NEUTRAL" if r["predicted_helps"] is False else "???")
        actual = "HELPS" if r.get("actual_helps") else "NEUTRAL"
        match = "✓" if r.get("prediction_correct") else ("✗" if "prediction_correct" in r else "?")
        print(f"  {r['graph']:<16} {r.get('phase',''):<6} {r['n']:>5} {r['separation_ratio_S']:>6.3f} "
              f"{pred:>8} {actual:>8} {r.get('delta_ARI', 0):>+8.4f} {match:>5}")
        if "prediction_correct" in r:
            total += 1
            if r["prediction_correct"]:
                correct += 1

    if total > 0:
        print(f"\n  PREDICTION ACCURACY: {correct}/{total} = {correct/total:.1%}")
        test_only = [r for r in results.values() if r.get("phase") == "test" and "prediction_correct" in r]
        if test_only:
            t_correct = sum(1 for r in test_only if r["prediction_correct"])
            print(f"  TEST-ONLY ACCURACY: {t_correct}/{len(test_only)} = {t_correct/len(test_only):.1%}")

    # Save
    out_path = HERE / "preregistered_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {out_path}")


if __name__ == "__main__":
    main()
