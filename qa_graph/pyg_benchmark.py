#!/usr/bin/env python3
"""Benchmark QA kernel on standard PyG graph datasets.

Tests the modal-degree-alignment hypothesis across diverse graph families:
- Planetoid: Cora, CiteSeer, PubMed (citation networks)
- TUDataset: PROTEINS, ENZYMES, MUTAG (molecular graphs)

For each graph, computes sector distribution, prime fraction, and QA lift.

Usage:
    cd qa_lab && PYTHONPATH=. python qa_graph/pyg_benchmark.py
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=pyg_benchmark, state_alphabet=graph_community"

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
MODULUS = 24
PRIME_SECTORS = {1, 5, 7, 11, 13, 17, 19, 23}


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
    n = W.shape[0]
    if n < k: return np.zeros(n, dtype=int)
    d = W.sum(axis=1)
    di = np.where(d>0, 1.0/np.sqrt(d), 0.0)
    L = np.eye(n) - np.diag(di)@W@np.diag(di)
    _, V = np.linalg.eigh(L); Z = V[:,:k]
    rn = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(rn>1e-10, Z/rn, 0.0)
    rng = np.random.RandomState(seed)
    C = Z[rng.choice(n, min(k, n), replace=False)]
    for _ in range(100):
        lab = np.argmin(np.linalg.norm(Z[:,None,:]-C[None,:,:], axis=2), axis=1)
        nC = np.zeros_like(C)
        for c in range(k):
            m = lab==c; nC[c] = Z[m].mean(axis=0) if m.any() else C[c]
        if np.allclose(nC,C): break
        C = nC
    return lab

def sector_entropy(sectors, m=MODULUS):
    counts = Counter(sectors)
    n = len(sectors)
    if n == 0: return 0.0
    probs = [c/n for c in counts.values()]
    H = -sum(p*math.log2(p) for p in probs if p>0)
    return H/math.log2(m) if math.log2(m)>0 else 0.0


# ── PyG graph loader ───────────────────────────────────────────────────

def load_pyg_graph(name):
    """Load a PyG dataset and convert to NetworkX + labels."""
    try:
        if name in ("Cora", "CiteSeer", "PubMed"):
            from torch_geometric.datasets import Planetoid
            dataset = Planetoid(root="/tmp/pyg_data", name=name)
            data = dataset[0]

            # Convert to NetworkX
            edge_index = data.edge_index.numpy()
            G = nx.Graph()
            G.add_nodes_from(range(data.num_nodes))
            for i in range(edge_index.shape[1]):
                u, v = int(edge_index[0, i]), int(edge_index[1, i])
                if u != v:
                    G.add_edge(u, v)

            labels = data.y.numpy().tolist()
            k = len(set(labels))
            return G, labels, k

        elif name in ("PROTEINS", "ENZYMES", "MUTAG"):
            from torch_geometric.datasets import TUDataset
            dataset = TUDataset(root="/tmp/pyg_data", name=name)

            # For TU datasets, we analyze the LARGEST graph
            # Find it
            best_idx = max(range(len(dataset)), key=lambda i: dataset[i].num_nodes)
            data = dataset[best_idx]

            edge_index = data.edge_index.numpy()
            G = nx.Graph()
            G.add_nodes_from(range(data.num_nodes))
            for i in range(edge_index.shape[1]):
                u, v = int(edge_index[0, i]), int(edge_index[1, i])
                if u != v:
                    G.add_edge(u, v)

            # Use node labels if available, else degree-based
            if data.y is not None and data.y.dim() == 0:
                # Graph-level label, not node-level — use node features
                if data.x is not None:
                    labels = data.x.argmax(dim=1).numpy().tolist()
                    k = max(labels) + 1
                else:
                    labels = None
                    k = 4
            elif hasattr(data, 'y') and data.y is not None and data.y.dim() > 0:
                labels = data.y.numpy().tolist()
                k = max(labels) + 1
            else:
                labels = None
                k = 4

            return G, labels, k

    except Exception as e:
        print(f"  Error loading {name}: {e}")
        return None, None, 0


# ── Analyze one graph ──────────────────────────────────────────────────

def analyze(name, G, gt_labels, k):
    nodes = list(G.nodes())
    n = len(nodes)
    if n == 0:
        return None

    # Remove isolated nodes for spectral clustering
    isolated = list(nx.isolates(G))
    if isolated:
        G = G.copy()
        G.remove_nodes_from(isolated)
        nodes = list(G.nodes())
        n = len(nodes)
        if gt_labels:
            gt_labels = [gt_labels[v] for v in nodes]

    if n < k or n < 10:
        return None

    # Extract (b, e) = (degree, core_number)
    deg = dict(G.degree())
    core = nx.core_number(G)
    b_vals = [max(1, int(deg[v])) for v in nodes]
    e_vals = [max(1, int(core[v])) for v in nodes]
    d_vals = [b + e for b, e in zip(b_vals, e_vals)]

    sectors = [qa_mod(d, MODULUS) for d in d_vals]
    prime_frac = sum(1 for s in sectors if s in PRIME_SECTORS) / n
    entropy = sector_entropy(sectors)
    counts = Counter(sectors)
    peak_sec = counts.most_common(1)[0][0]
    peak_frac = counts[peak_sec] / n
    n_occupied = len(counts)

    # Modal degree analysis
    deg_counts = Counter(b_vals)
    modal_deg = deg_counts.most_common(1)[0][0]
    modal_d = modal_deg + max(1, int(np.median(e_vals)))
    modal_sector = qa_mod(modal_d, MODULUS)
    modal_in_prime = modal_sector in PRIME_SECTORS

    result = {
        "graph": name,
        "nodes": n,
        "edges": G.number_of_edges(),
        "k": k,
        "prime_fraction": round(prime_frac, 4),
        "sector_entropy": round(entropy, 4),
        "peak_sector": peak_sec,
        "peak_fraction": round(peak_frac, 4),
        "sectors_occupied": n_occupied,
        "modal_degree": modal_deg,
        "modal_sector": modal_sector,
        "modal_in_prime": modal_in_prime,
    }

    if gt_labels and len(gt_labels) == n:
        # Baseline
        W_base = nx.to_numpy_array(G, nodelist=nodes, weight=None).astype(float)
        pred_base = list(spectral_cluster(W_base, k))

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
        edge_dists = sq[A > 0]
        if len(edge_dists) > 0:
            tau = np.median(edge_dists) + 1e-8
        else:
            tau = 1.0
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
    print("=" * 74)
    print("PyG BENCHMARK — MODAL-DEGREE-ALIGNMENT HYPOTHESIS")
    print("Testing across citation networks, molecular graphs, social networks")
    print("=" * 74)

    datasets = [
        "Cora", "CiteSeer", "PubMed",
    ]

    # Also include our local graphs
    local_graphs = []
    data_dir = HERE / "data"
    for name in ["football", "karate"]:
        path = data_dir / f"{name}.graphml"
        if path.exists():
            G = nx.read_graphml(str(path)).to_undirected()
            gt = {v: int(d["value"]) for v, d in G.nodes(data=True) if "value" in d}
            nodes = list(G.nodes())
            if len(gt) == len(nodes):
                labels = [gt[v] for v in nodes]
                k = max(labels) + 1
                local_graphs.append((name, G, labels, k))

    results = []

    # Local graphs first
    for name, G, labels, k in local_graphs:
        print(f"\n  {name}...", end=" ", flush=True)
        t0 = time.perf_counter()
        r = analyze(name, G, labels, k)
        if r:
            r["time_s"] = round(time.perf_counter() - t0, 3)
            r["source"] = "local"
            results.append(r)
            print(f"done ({r['time_s']}s) n={r['nodes']}")

    # PyG datasets
    for ds_name in datasets:
        print(f"\n  {ds_name}...", end=" ", flush=True)
        t0 = time.perf_counter()
        G, labels, k = load_pyg_graph(ds_name)
        if G is None:
            print("SKIPPED")
            continue
        r = analyze(ds_name, G, labels, k)
        if r:
            r["time_s"] = round(time.perf_counter() - t0, 3)
            r["source"] = "PyG"
            results.append(r)
            print(f"done ({r['time_s']}s) n={r['nodes']}")
        else:
            print("SKIPPED (too small or no labels)")

    # Summary
    print("\n" + "=" * 74)
    print("RESULTS SUMMARY")
    print("=" * 74)
    print(f"\n  {'Graph':<12} {'N':>6} {'K':>3} {'PrFr':>6} {'Ent':>6} {'MdDeg':>6} {'MdSec':>6} {'MdPr':>5} {'ΔARI':>8} {'ΔNMI':>8}")
    print(f"  {'-'*12} {'-'*6} {'-'*3} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*8} {'-'*8}")

    for r in sorted(results, key=lambda x: x.get("delta_ARI", -99), reverse=True):
        dARI = f"{r['delta_ARI']:+.4f}" if "delta_ARI" in r else "     n/a"
        dNMI = f"{r['delta_NMI']:+.4f}" if "delta_NMI" in r else "     n/a"
        mp = "Y" if r["modal_in_prime"] else "N"
        print(f"  {r['graph']:<12} {r['nodes']:>6} {r['k']:>3} {r['prime_fraction']:>6.3f} "
              f"{r['sector_entropy']:>6.3f} {r['modal_degree']:>6} {r['modal_sector']:>6} {mp:>5} "
              f"{dARI:>8} {dNMI:>8}")

    # Correlation
    gt_results = [r for r in results if "delta_ARI" in r]
    if len(gt_results) >= 3:
        def pearson(x, y):
            n = len(x); mx, my = sum(x)/n, sum(y)/n
            num = sum((a-mx)*(b-my) for a,b in zip(x,y))
            dx = math.sqrt(sum((a-mx)**2 for a in x))
            dy = math.sqrt(sum((b-my)**2 for b in y))
            return num/(dx*dy) if dx*dy>0 else 0.0

        pf = [r["prime_fraction"] for r in gt_results]
        da = [r["delta_ARI"] for r in gt_results]
        dn = [r["delta_NMI"] for r in gt_results]
        mp = [float(r["modal_in_prime"]) for r in gt_results]

        print(f"\n  CORRELATIONS (n={len(gt_results)} graphs):")
        print(f"    r(prime_fraction, ΔARI) = {pearson(pf, da):+.3f}")
        print(f"    r(prime_fraction, ΔNMI) = {pearson(pf, dn):+.3f}")
        print(f"    r(modal_in_prime, ΔARI) = {pearson(mp, da):+.3f}")
        print(f"    r(modal_in_prime, ΔNMI) = {pearson(mp, dn):+.3f}")

    out_path = HERE / "pyg_benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: {out_path}")


if __name__ == "__main__":
    main()
