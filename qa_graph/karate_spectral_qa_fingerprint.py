"""
Karate spectral→QA fingerprint — the true map-back.

Approach: take the method that wins on karate (spectral clustering, ARI 0.88),
compute its partition, then extract the QA-algebraic fingerprint of each cluster.
If there is a clean QA invariant that separates the clusters, we have mapped
the winning method into QA algebra.

This is the core ethos: find what works, extract its generator structure,
certify the mapping. The QA contribution is the MAPPING, not the replacement.
"""
from __future__ import annotations

from pathlib import Path
import json

import networkx as nx
import numpy as np
from sklearn.cluster import SpectralClustering
from sklearn.metrics import adjusted_rand_score

from qa_reasoner import QAReasoner

DATA = Path(__file__).parent / "data"


def load_karate():
    G = nx.read_graphml(str(DATA / "karate.graphml")).to_undirected()
    nodes = list(G.nodes())
    gt = np.array([int(G.nodes[v].get("value", 0)) for v in nodes])
    return G, nodes, gt


def spectral_partition(G, nodes, k=2, seed=42):
    A = nx.to_numpy_array(G, nodelist=nodes)
    sc = SpectralClustering(n_clusters=k, affinity="precomputed", random_state=seed)
    return sc.fit_predict(A)


def qa_fingerprint_of_cluster(G, nodes_in_cluster, hubs, mod=9):
    """Compute QA-algebraic summary of a node set via hub-distance tuples."""
    r = QAReasoner(mod)
    paths0 = nx.shortest_path_length(G, source=hubs[0])
    paths1 = nx.shortest_path_length(G, source=hubs[1])

    tuples = []
    families = {"cosmos": 0, "satellite": 0, "singularity": 0}
    norms = []
    for v in nodes_in_cluster:
        b = paths0.get(v, 99) + 1
        e = paths1.get(v, 99) + 1
        cls = r.classify(b, e)
        tuples.append((b, e, cls.tuple4[2], cls.tuple4[3]))
        families[cls.family] += 1
        norms.append(cls.norm)

    b_vals = [t[0] for t in tuples]
    e_vals = [t[1] for t in tuples]

    return {
        "n": len(nodes_in_cluster),
        "family_distribution": families,
        "b_range": [int(min(b_vals)), int(max(b_vals))],
        "e_range": [int(min(e_vals)), int(max(e_vals))],
        "mean_norm": round(float(np.mean(norms)), 3),
        "norm_range": [int(min(norms)), int(max(norms))],
        "tuples_sample": tuples[:6],
    }


def main():
    G, nodes, gt = load_karate()
    hubs = sorted(G.nodes(), key=lambda v: G.degree(v), reverse=True)[:2]

    # Run the winning method
    labels = spectral_partition(G, nodes, k=2)
    ari = adjusted_rand_score(gt, labels)
    print(f"Spectral baseline ARI = {ari:.4f}")
    print(f"Hubs: {hubs}, degrees {[G.degree(h) for h in hubs]}\n")

    # Partition nodes by spectral labels
    cluster0 = [nodes[i] for i in range(len(nodes)) if labels[i] == 0]
    cluster1 = [nodes[i] for i in range(len(nodes)) if labels[i] == 1]

    fp0 = qa_fingerprint_of_cluster(G, cluster0, hubs)
    fp1 = qa_fingerprint_of_cluster(G, cluster1, hubs)

    print("=" * 60)
    print("CLUSTER 0 (spectral):")
    print("-" * 60)
    print(json.dumps(fp0, indent=2))
    print()
    print("=" * 60)
    print("CLUSTER 1 (spectral):")
    print("-" * 60)
    print(json.dumps(fp1, indent=2))
    print()

    # Key question: does a single QA invariant separate them?
    print("=" * 60)
    print("QA SEPARABILITY CHECK:")
    print("-" * 60)
    paths0 = nx.shortest_path_length(G, source=hubs[0])
    paths1 = nx.shortest_path_length(G, source=hubs[1])

    # Try every candidate invariant as a separator
    candidates = {
        "b (dist hub0)":   [paths0[v] + 1 for v in nodes],
        "e (dist hub1)":   [paths1[v] + 1 for v in nodes],
        "d = b+e":         [paths0[v] + paths1[v] + 2 for v in nodes],
        "a = b+2e":        [paths0[v] + 2 * (paths1[v] + 1) for v in nodes],
        "b - e":           [paths0[v] - paths1[v] for v in nodes],
        "sign(b-e)":       [1 if paths0[v] > paths1[v] else (-1 if paths0[v] < paths1[v] else 0) for v in nodes],
        "norm f(b,e)":     [(paths0[v]+1)**2 + (paths0[v]+1)*(paths1[v]+1) - (paths1[v]+1)**2 for v in nodes],
    }

    print(f"{'Invariant':<20} {'ARI vs spectral':>16} {'ARI vs GT':>12}")
    print("-" * 50)
    for name, vals in candidates.items():
        vals = np.array(vals)
        # Median-threshold partition
        thresh = np.median(vals)
        partition = (vals > thresh).astype(int)
        ari_sp = adjusted_rand_score(labels, partition)
        ari_gt = adjusted_rand_score(gt, partition)
        print(f"{name:<20} {ari_sp:>16.4f} {ari_gt:>12.4f}")

    out = Path(__file__).parent / "karate_spectral_qa_fingerprint.json"
    out.write_text(json.dumps({
        "hubs": hubs,
        "spectral_ari_vs_gt": float(ari),
        "cluster_0_fingerprint": fp0,
        "cluster_1_fingerprint": fp1,
    }, indent=2))
    print(f"\nResults written to: {out}")


if __name__ == "__main__":
    main()
