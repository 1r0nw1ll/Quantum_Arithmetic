"""
Hub-distance QA descriptor — generalization benchmark.

Tests the hypothesis from the karate map-back result: for hub-dominated graphs,
the QA-native community descriptor is the integer tuple of shortest-path distances
to the top-k hubs, not centrality-based invariants.

Benchmark suite:
    1. karate_club        — real, 2 comms, classic hub-dominated
    2. barbell(10, 3)     — deterministic, 2 K_10 cliques + length-3 path
    3. caveman(4, 5)      — deterministic, 4 cliques of 5 nodes
    4. florentine         — real, historical, moderate structure
    5. football           — real, 12 comms, LOW hub dominance (sanity check —
                            hub-distance should NOT help here)

For each graph we compare 5 methods:
    baseline_spectral     — standard spectral clustering on adjacency
    louvain               — modularity-based community detection
    qa_centrality_kernel  — original QA kernel with (b=deg, e=core)
    hub_distance_k_means  — k-means on (b, e) = (dist-hub1, dist-hub2, ...)
    hub_distance_rule     — argmin(distance to hub_i) direct assignment

Degree coefficient of variation (CV) is reported as the hub-dominance proxy.
HYPOTHESIS: hub-distance methods win on graphs where CV > 0.5, lose on low-CV graphs.

Theorem NT compliance: all descriptors are integer shortest-path distances
(discrete, A1-compliant). Synthetic graphs are deterministic constructions
(barbell, caveman) — no stochastic generators.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
from sklearn.cluster import KMeans, SpectralClustering
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


# ── Dataset loaders (all produce (G, nodes, gt_labels, k)) ────────────────────


def load_karate():
    G = nx.karate_club_graph()
    nodes = list(G.nodes())
    gt = np.array([0 if G.nodes[v]["club"] == "Mr. Hi" else 1 for v in nodes])
    return G, nodes, gt, 2


def load_barbell():
    """Two K_10 cliques connected by a 3-node path. 2 communities by clique."""
    G = nx.barbell_graph(10, 3)
    nodes = list(G.nodes())
    # Nodes 0..9 = clique A, nodes 13..22 = clique B, 10..12 = bridge path
    # Assign bridge nodes to nearest clique: 10->A, 11->?, 12->B
    gt = np.array([0 if v < 11 else 1 for v in nodes])
    return G, nodes, gt, 2


def load_caveman():
    """4 cliques of size 5, connected in a cycle by replacing one edge per clique."""
    G = nx.connected_caveman_graph(4, 5)
    nodes = list(G.nodes())
    # Clique i contains nodes [5i, 5i+5)
    gt = np.array([v // 5 for v in nodes])
    return G, nodes, gt, 4


def load_florentine():
    """Florentine families marriage network. 2 communities: Medici vs Strozzi faction."""
    G = nx.florentine_families_graph()
    # Medici-aligned vs Strozzi-aligned (classic historical reading; Peruzzi not
    # assigned here because its alliance is disputed — drop Pucci isolate).
    medici_side = {"Medici", "Barbadori", "Albizzi", "Ridolfi", "Tornabuoni",
                   "Ginori", "Acciaiuoli", "Salviati", "Pazzi"}
    strozzi_side = {"Strozzi", "Castellani", "Peruzzi", "Bischeri", "Lamberteschi",
                    "Guadagni"}
    # Drop any isolate (Pucci has no edges)
    G = G.subgraph([v for v in G.nodes() if G.degree(v) > 0]).copy()
    nodes = list(G.nodes())
    gt = np.array([0 if v in medici_side else 1 for v in nodes])
    return G, nodes, gt, 2


def load_football():
    path = Path(__file__).parent / "data" / "football.graphml"
    G = nx.read_graphml(str(path)).to_undirected()
    nodes = list(G.nodes())
    gt = np.array([int(G.nodes[v].get("value", 0)) for v in nodes])
    k = int(max(gt)) + 1
    return G, nodes, gt, k


# ── Metrics ───────────────────────────────────────────────────────────────────


def degree_cv(G: nx.Graph) -> float:
    """Coefficient of variation of the degree sequence. >0.5 ≈ hub-dominated."""
    degrees = np.array([d for _, d in G.degree()], dtype=float)
    if degrees.mean() == 0:
        return 0.0
    return float(degrees.std() / degrees.mean())


def eval_partition(pred, gt) -> Dict[str, float]:
    return {
        "ARI": round(float(adjusted_rand_score(gt, pred)), 4),
        "NMI": round(float(normalized_mutual_info_score(gt, pred)), 4),
    }


# ── Methods ───────────────────────────────────────────────────────────────────


def top_k_hubs(G: nx.Graph, k: int) -> List:
    return sorted(G.nodes(), key=lambda v: G.degree(v), reverse=True)[:k]


def hub_distance_tuple(G: nx.Graph, nodes: List, hubs: List) -> np.ndarray:
    """For each node, return integer shortest-path distance to every hub.
    Shape (N, len(hubs)). Distance offset by 1 for A1 compliance.
    """
    cols = []
    for h in hubs:
        sp = nx.shortest_path_length(G, source=h)
        cols.append([sp.get(v, 99) + 1 for v in nodes])
    return np.array(cols).T.astype(int)


def baseline_spectral(G, nodes, k):
    A = nx.to_numpy_array(G, nodelist=nodes)
    sc = SpectralClustering(n_clusters=k, affinity="precomputed", random_state=42)
    return sc.fit_predict(A)


def louvain_partition(G, nodes):
    try:
        from networkx.algorithms.community import louvain_communities
    except Exception:
        return None
    comms = louvain_communities(G, seed=42)
    label = {}
    for cid, comm in enumerate(comms):
        for v in comm:
            label[v] = cid
    return np.array([label[v] for v in nodes])


def qa_centrality_kernel(G, nodes, k):
    """Original qa_graph approach: (b=degree, e=core_number) → qa21 features → RBF → spectral."""
    from qa_graph.feature_map import qa_feature_vector
    from scipy.spatial.distance import pdist, squareform

    core = nx.core_number(G)
    feats = []
    for v in nodes:
        b = max(1, G.degree(v))
        e = max(1, core.get(v, 1))
        vec = qa_feature_vector(b, e, mode="qa21")[0]
        feats.append(vec)
    feats = np.array(feats)
    mu, sd = feats.mean(0), feats.std(0) + 1e-9
    feats = (feats - mu) / sd
    D2 = squareform(pdist(feats, "sqeuclidean"))
    tau2 = np.median(D2[D2 > 0]) if (D2 > 0).any() else 1.0
    K = np.exp(-D2 / (2 * tau2))
    A = nx.to_numpy_array(G, nodelist=nodes)
    W = A * K
    sc = SpectralClustering(n_clusters=k, affinity="precomputed", random_state=42)
    return sc.fit_predict(W)


def hub_distance_kmeans(G, nodes, k):
    """Pure hub-distance descriptor: k-means on integer distances to top-k hubs."""
    hubs = top_k_hubs(G, k)
    X = hub_distance_tuple(G, nodes, hubs).astype(float)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    return km.fit_predict(X)


def hub_distance_argmin(G, nodes, k):
    """Direct rule: assign node to the hub it's closest to. No clustering needed."""
    hubs = top_k_hubs(G, k)
    X = hub_distance_tuple(G, nodes, hubs)
    return X.argmin(axis=1)


def hub_distance_single_axis(G, nodes, k):
    """Single-axis hub descriptor: pick the hub whose distance partition best
    separates the graph (by modularity), then threshold.

    This refines the karate insight: on karate, using e=dist-to-hub-1 alone
    (ARI 0.77) beats k-means on (b, e) (ARI 0.67) because the primary hub
    is shared between both communities. Picking the discriminative hub first
    and thresholding on a single integer coord is the right move.

    For k>2, we return k-means on the single-axis tuple (falls back to 1D).
    """
    candidate_hubs = top_k_hubs(G, max(5, k * 2))
    best_pred = None
    best_score = -np.inf
    A = nx.to_numpy_array(G, nodelist=nodes)

    for h in candidate_hubs:
        sp = nx.shortest_path_length(G, source=h)
        dist = np.array([sp.get(v, 99) + 1 for v in nodes])

        if k == 2:
            # Try every threshold
            for thresh in np.unique(dist):
                pred = (dist > thresh).astype(int)
                if len(set(pred)) != 2:
                    continue
                score = _modularity(A, pred)
                if score > best_score:
                    best_score = score
                    best_pred = pred
        else:
            # k-means on 1D distances
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            pred = km.fit_predict(dist.reshape(-1, 1))
            score = _modularity(A, pred)
            if score > best_score:
                best_score = score
                best_pred = pred

    return best_pred if best_pred is not None else np.zeros(len(nodes), dtype=int)


def _modularity(A: np.ndarray, labels: np.ndarray) -> float:
    """Newman modularity Q = (1/2m) Σ (A_ij - k_i k_j / 2m) δ(c_i, c_j)."""
    m2 = A.sum()
    if m2 == 0:
        return 0.0
    k = A.sum(axis=1)
    expected = np.outer(k, k) / m2
    same = labels[:, None] == labels[None, :]
    return float(((A - expected) * same).sum() / m2)


# ── Main ──────────────────────────────────────────────────────────────────────


DATASETS = [
    ("karate",     load_karate),
    ("barbell",    load_barbell),
    ("caveman",    load_caveman),
    ("florentine", load_florentine),
    ("football",   load_football),
]


def run():
    all_results = {}
    print("=" * 78)
    print("HUB-DISTANCE QA DESCRIPTOR — GENERALIZATION BENCHMARK")
    print("=" * 78)
    print()

    for name, loader in DATASETS:
        try:
            G, nodes, gt, k = loader()
        except Exception as exc:
            print(f"{name}: LOAD ERROR: {exc}")
            continue

        cv = degree_cv(G)
        hub_dom = "HIGH" if cv > 0.5 else "low"
        print(f"--- {name.upper()} ---")
        print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, k={k}")
        print(f"  degree CV = {cv:.3f}  ({hub_dom} hub dominance)")
        print()

        results = {
            "n_nodes": G.number_of_nodes(),
            "n_edges": G.number_of_edges(),
            "k": k,
            "degree_cv": round(cv, 4),
            "hub_dominated": cv > 0.5,
            "methods": {},
        }

        methods = [
            ("baseline_spectral",     lambda: baseline_spectral(G, nodes, k)),
            ("louvain",               lambda: louvain_partition(G, nodes)),
            ("qa_centrality_kernel",  lambda: qa_centrality_kernel(G, nodes, k)),
            ("hub_distance_kmeans",   lambda: hub_distance_kmeans(G, nodes, k)),
            ("hub_distance_argmin",   lambda: hub_distance_argmin(G, nodes, k)),
            ("hub_distance_1axis",    lambda: hub_distance_single_axis(G, nodes, k)),
        ]

        header = f"  {'Method':<24} {'ARI':>8} {'NMI':>8}"
        print(header)
        print("  " + "-" * 42)
        for mname, mfn in methods:
            try:
                pred = mfn()
                if pred is None:
                    continue
                m = eval_partition(pred, gt)
                results["methods"][mname] = m
                print(f"  {mname:<24} {m['ARI']:>8.4f} {m['NMI']:>8.4f}")
            except Exception as exc:
                print(f"  {mname:<24} ERROR: {exc}")
                results["methods"][mname] = {"error": str(exc)}

        # Identify winners
        scored = [(mn, r["ARI"]) for mn, r in results["methods"].items() if "ARI" in r]
        if scored:
            scored.sort(key=lambda x: x[1], reverse=True)
            results["best_method"] = scored[0][0]
            results["best_ari"] = scored[0][1]
            hd_ari = max(
                results["methods"].get("hub_distance_kmeans", {}).get("ARI", -1),
                results["methods"].get("hub_distance_argmin", {}).get("ARI", -1),
                results["methods"].get("hub_distance_1axis", {}).get("ARI", -1),
            )
            bl_ari = results["methods"].get("baseline_spectral", {}).get("ARI", -1)
            hd_beats_baseline = hd_ari > bl_ari
            hd_ties_baseline = abs(hd_ari - bl_ari) < 0.02
            results["hub_distance_wins"] = bool(hd_beats_baseline)
            results["hub_distance_ties"] = bool(hd_ties_baseline)
            print(f"  → best: {scored[0][0]} (ARI={scored[0][1]:.4f})")
            if hd_beats_baseline:
                print(f"  ✓ hub-distance BEATS baseline (+{hd_ari - bl_ari:.4f} ARI)")
            elif hd_ties_baseline:
                print(f"  ≈ hub-distance TIES baseline")
            else:
                print(f"  ✗ hub-distance < baseline ({hd_ari - bl_ari:+.4f} ARI)")

        print()
        all_results[name] = results

    # Hypothesis test: hub-distance should win iff CV > 0.5
    print("=" * 78)
    print("HYPOTHESIS EVALUATION")
    print("=" * 78)
    print("Claim: hub-distance methods win or tie on hub-dominated graphs (CV > 0.5)")
    print()
    print(f"  {'Graph':<14} {'CV':>7} {'hub-dom':>8} {'hd wins':>8} {'hd ties':>8}")
    print("  " + "-" * 52)
    hypothesis_hits = 0
    hypothesis_tests = 0
    for name, r in all_results.items():
        cv = r["degree_cv"]
        hd = r["hub_dominated"]
        wins = r.get("hub_distance_wins", False)
        ties = r.get("hub_distance_ties", False)
        expected = hd
        actual = wins or ties
        match = "✓" if expected == actual else "✗"
        print(f"  {name:<14} {cv:>7.3f} {str(hd):>8} {str(wins):>8} {str(ties):>8}  {match}")
        if expected == actual:
            hypothesis_hits += 1
        hypothesis_tests += 1
    print()
    print(f"Hypothesis agreement: {hypothesis_hits}/{hypothesis_tests} graphs")

    out = Path(__file__).parent / "hub_distance_descriptor_benchmark_results.json"
    out.write_text(json.dumps({
        "hypothesis": "hub-distance wins/ties on graphs with degree CV > 0.5",
        "hypothesis_hits": hypothesis_hits,
        "hypothesis_tests": hypothesis_tests,
        "per_graph": all_results,
    }, indent=2, default=str))
    print(f"\nResults written to: {out}")


if __name__ == "__main__":
    run()
