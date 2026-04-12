"""QA Cayley graphs — Bateson learning levels as nested Cayley components.

Constructs Cayley-style graphs on the QA state space S_m = {(b,e) : 1<=b,e<=m}
with generator sets stratified by Bateson learning tier (cf. family [191]).

Theorem (Bateson-Cayley equivalence):
    Let Cay_undirected(S_m, Gamma) denote the undirected graph whose edges are
    {(s, g(s)) : s in S_m, g in Gamma} closed under symmetry. Then the connected
    components of Cay_undirected(S_m, Gamma_tier) equal the tier-reachability
    classes of [191]:

        Gamma_1   = {T}                                   ->  T-orbits
        Gamma_2a  = Gamma_1 U (Z/mZ)*-scalars U {swap}    ->  orbit families
        Gamma_2b  = Gamma_2a U zero-divisor scalars U {const_{(m,m)}}
                                                          ->  connected (all of S_m)

    Exhaustive check on S_9 reproduces [191] tier counts exactly:
        sum over s0 of |component(s0)| gives
            Gamma_1  : 1793   = 81 + 1712
            Gamma_2a : 5249   = 1793 + 3456
            Gamma_2b : 6561   = 5249 + 1312

    The non-cumulative differences 1712 / 3456 / 1312 are the Level-I / II-a /
    II-b pair counts from the Tiered Reachability Theorem in [191].

QA axiom compliance:
    - A1 (No-Zero):     state alphabet {1,...,m}, scalar ops use ((k*s-1)%m)+1
    - A2 (Derived):     this module operates on raw (b,e) pairs, not (b,e,d,a);
                        derived-coord invariants belong to feature_map.py
    - T2 (Firewall):    no floats, no observer input -> QA state crossing
    - S1 (No **2):      no squaring at all in this module
    - S2 (No float st): tuples of int only
    - T1 (Path Time):   distances are integer BFS step counts
"""

QA_COMPLIANCE = "observer=graph_topology_analyzer, state_alphabet=qa_state_space_S_m, tier=finite_integer_reachability_classes"

from math import gcd
from typing import Callable, Dict, Iterable, List, Set, Tuple

import networkx as nx  # graph topology only — no float state propagated

State = Tuple[int, int]
Operator = Callable[[State], State]


# -----------------------------------------------------------------------------
# State space enumeration
# -----------------------------------------------------------------------------

def enumerate_state_space(m: int) -> List[State]:
    """S_m = {(b, e) : 1 <= b, e <= m}. A1-compliant — no zero element."""
    if m < 1:
        raise ValueError(f"m must be >= 1, got {m}")
    return [(b, e) for b in range(1, m + 1) for e in range(1, m + 1)]


# -----------------------------------------------------------------------------
# QA primitive operators (all A1-adjusted via ((x-1) % m) + 1)
# -----------------------------------------------------------------------------

def op_T(m: int) -> Operator:
    """T(b,e) = (e, ((b+e-1) % m) + 1). The canonical QA step generator (L_1)."""
    def _T(s: State) -> State:
        b, e = s
        return (e, ((b + e - 1) % m) + 1)
    return _T


def op_scalar(k: int, m: int) -> Operator:
    """scalar_k(b,e) = (((k*b-1) % m) + 1, ((k*e-1) % m) + 1).

    When gcd(k, m) == 1, this is a bijection on S_m (Level-II-a witness).
    When gcd(k, m) > 1, it collapses S_m onto a sub-lattice (Level-II-b witness
    on m=9: scalar_3 lands on {3,6,9}x{3,6,9} = the satellite family).
    """
    def _sc(s: State) -> State:
        b, e = s
        return (((k * b - 1) % m) + 1, ((k * e - 1) % m) + 1)
    return _sc


def op_swap() -> Operator:
    """swap(b,e) = (e,b). Involution; Level-II-a on cosmos (permutes orbits)."""
    return lambda s: (s[1], s[0])


def op_constant(target: State) -> Operator:
    """const_{target}(b,e) = target. Collapses S_m onto a single point."""
    return lambda _s: target


def units_mod(m: int) -> List[int]:
    """(Z/mZ)* — multiplicative units, excluding 1 (which is identity)."""
    return [k for k in range(2, m) if gcd(k, m) == 1]


def zero_divisor_scalars(m: int) -> List[int]:
    """Non-unit non-identity scalars — Level-II-b witnesses."""
    return [k for k in range(2, m) if gcd(k, m) != 1]


# -----------------------------------------------------------------------------
# Bateson-tier generator sets
# -----------------------------------------------------------------------------

def bateson_generators(tier: str, m: int = 9) -> Dict[str, Operator]:
    """Return the generator dict for a Bateson tier on S_m.

    tier in {'L1', 'L2a', 'L2b'}.

    L1  : {T}                                           (orbit-preserving)
    L2a : L1 U {scalar_k : k in (Z/mZ)*} U {swap}       (family-preserving)
    L2b : L2a U {scalar_k : gcd(k,m)>1} U {const_(m,m)} (modulus-preserving)

    Grounding: [191] qa_bateson_learning_levels_cert witnesses L_1 via T,
    L_2a via scalar_2 and swap, L_2b via scalar_3 and constant_9_9.
    """
    if tier not in ("L1", "L2a", "L2b"):
        raise ValueError(f"tier must be one of L1, L2a, L2b; got {tier!r}")

    gens: Dict[str, Operator] = {"T": op_T(m)}

    if tier in ("L2a", "L2b"):
        for k in units_mod(m):
            gens[f"scalar_{k}"] = op_scalar(k, m)
        gens["swap"] = op_swap()

    if tier == "L2b":
        for k in zero_divisor_scalars(m):
            gens[f"scalar_{k}"] = op_scalar(k, m)
        gens["const_singularity"] = op_constant((m, m))

    return gens


# -----------------------------------------------------------------------------
# Cayley graph construction and metrics
# -----------------------------------------------------------------------------

def build_cayley_graph(
    state_space: Iterable[State],
    generators: Dict[str, Operator],
    undirected: bool = True,
) -> nx.Graph:
    """Build the Cayley-style graph Cay(state_space, generators).

    Edges: for each s in state_space and each g in generators, add the edge
    s -- g(s) (with generator name stored under edge attribute 'gens' as a set
    of strings). Self-loops (g(s) == s) are preserved to record identity action
    but do not affect connectivity.

    Parameters
    ----------
    undirected : bool
        If True (default, standard Cayley-graph convention), return an
        undirected Graph. The non-bijective L_2b generators (scalar_3,
        const) are then symmetrized: reach s0 -- g(s0) edges let BFS traverse
        both directions. If False, return a DiGraph with directed edges only.
    """
    G: nx.Graph = nx.Graph() if undirected else nx.DiGraph()
    state_list = list(state_space)
    G.add_nodes_from(state_list)

    for s in state_list:
        for gname, g in generators.items():
            t = g(s)
            if t not in G:
                continue  # image left the state space (shouldn't happen for S_m)
            if G.has_edge(s, t):
                G[s][t].setdefault("gens", set()).add(gname)
            else:
                G.add_edge(s, t, gens={gname})

    return G


def cayley_distance(G: nx.Graph, source: State, target: State) -> int:
    """Integer BFS distance in G. Returns -1 if target not reachable."""
    if source == target:
        return 0
    try:
        return int(nx.shortest_path_length(G, source, target))
    except nx.NetworkXNoPath:
        return -1
    except nx.NodeNotFound:
        return -1


def cayley_ball(G: nx.Graph, source: State, radius: int = -1) -> Set[State]:
    """Set of states within `radius` steps of source.

    radius == -1 (default) means the whole connected component.
    """
    if source not in G:
        return set()
    if radius < 0:
        return set(nx.node_connected_component(G, source)) if not G.is_directed() \
            else (set(nx.descendants(G, source)) | {source})

    # bounded BFS
    seen = {source}
    frontier: List[Tuple[State, int]] = [(source, 0)]
    while frontier:
        s, d = frontier.pop(0)
        if d >= radius:
            continue
        neighbors = G.neighbors(s) if not G.is_directed() else G.successors(s)
        for t in neighbors:
            if t not in seen:
                seen.add(t)
                frontier.append((t, d + 1))
    return seen


def component_sizes(G: nx.Graph) -> List[int]:
    """Sorted descending list of connected-component sizes."""
    if G.is_directed():
        comps = nx.weakly_connected_components(G)
    else:
        comps = nx.connected_components(G)
    return sorted((len(c) for c in comps), reverse=True)


# -----------------------------------------------------------------------------
# Bateson-Cayley equivalence verification (matches [191] EXPECTED_TIER_COUNTS_S9)
# -----------------------------------------------------------------------------

# [191] tier counts on S_9 — theorem constants, not empirical measurements.
# Sum over all ordered pairs (s0, s*) of the tier needed to reach s* from s0.
BATESON_191_S9_COUNTS: Dict[str, int] = {
    "0": 81,     # identity
    "1": 1712,   # orbit
    "2a": 3456,  # family, different orbit
    "2b": 1312,  # different family, same modulus
}

# Cumulative: number of pairs reachable using tiers up to and including the key.
BATESON_191_S9_CUMULATIVE: Dict[str, int] = {
    "L1":  BATESON_191_S9_COUNTS["0"] + BATESON_191_S9_COUNTS["1"],            # 1793
    "L2a": sum(BATESON_191_S9_COUNTS[k] for k in ("0", "1", "2a")),            # 5249
    "L2b": sum(BATESON_191_S9_COUNTS[k] for k in ("0", "1", "2a", "2b")),      # 6561
}


def verify_bateson_cayley_equivalence(m: int = 9) -> Dict:
    """Exhaustively verify: cumulative component-sum matches [191] tier counts.

    For each tier in {L1, L2a, L2b}:
        1. Build Cay_undirected(S_m, Gamma_tier).
        2. For each s0 in S_m, count |component(s0)|. Sum across all s0.
        3. Compare to cumulative [191] tier count.

    Returns a dict with per-tier 'expected', 'actual', 'components', 'match'.
    On m=9 every tier must match exactly or the theorem is false.
    """
    space = enumerate_state_space(m)
    results: Dict = {"m": m, "tiers": {}}

    for tier in ("L1", "L2a", "L2b"):
        gens = bateson_generators(tier, m)
        G = build_cayley_graph(space, gens, undirected=True)
        sizes = component_sizes(G)

        cumulative_pair_count = sum(sz * sz for sz in sizes)

        tier_result: Dict = {
            "generators": sorted(gens.keys()),
            "num_components": len(sizes),
            "component_sizes": sizes,
            "cumulative_pair_count": cumulative_pair_count,
            "components_sum_of_squares_formula": "sum |C|^2 over components C",
        }

        if m == 9:
            expected = BATESON_191_S9_CUMULATIVE[tier]
            tier_result["expected_cumulative_S9"] = expected
            tier_result["match"] = (cumulative_pair_count == expected)

        results["tiers"][tier] = tier_result

    # non-cumulative diffs (should match BATESON_191_S9_COUNTS for m=9)
    if m == 9:
        diffs = {
            "1":  results["tiers"]["L1"]["cumulative_pair_count"] - 81,
            "2a": results["tiers"]["L2a"]["cumulative_pair_count"]
                  - results["tiers"]["L1"]["cumulative_pair_count"],
            "2b": results["tiers"]["L2b"]["cumulative_pair_count"]
                  - results["tiers"]["L2a"]["cumulative_pair_count"],
        }
        results["tier_differences"] = diffs
        results["matches_191_counts"] = all(
            diffs[k] == BATESON_191_S9_COUNTS[k] for k in ("1", "2a", "2b")
        )

    return results


__all__ = [
    "State",
    "Operator",
    "enumerate_state_space",
    "op_T",
    "op_scalar",
    "op_swap",
    "op_constant",
    "units_mod",
    "zero_divisor_scalars",
    "bateson_generators",
    "build_cayley_graph",
    "cayley_distance",
    "cayley_ball",
    "component_sizes",
    "verify_bateson_cayley_equivalence",
    "BATESON_191_S9_COUNTS",
    "BATESON_191_S9_CUMULATIVE",
]
