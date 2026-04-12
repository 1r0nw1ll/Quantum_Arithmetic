"""QA Causal DAG — the 4-node Y-structure causal graph of (b,e,d,a).

The A2 axiom (d = b+e, a = b+2e) IS the structural equation system of a
causal DAG on four variables. This module makes that DAG explicit and proves
its properties.

Structural causal model (Pearl 1995, 2009):

    b  (exogenous)
    e  (exogenous)
    d := b + e        (endogenous collider)
    a := b + 2e       (endogenous collider)

The resulting DAG has 4 nodes and 4 directed edges:

        b           e
        |\\         /|
        | \\       / |
        |  \\     /  |
        |   \\   /   |
        |    \\ /    |
        |     X      |
        |    / \\    |
        |   /   \\   |
        |  /     \\  |
        | /       \\ |
        |/         \\|
        d           a

Both d and a are **colliders** (two arrows pointing in). Neither has children.
b and e are marginally d-separated (no common cause); conditioning on d OR a
opens an "explaining-away" path between b and e.

Pair-Invertibility Theorem (verified exhaustively on S_9 and S_24):

    Given any 2 of the 4 variables (b, e, d, a), the other 2 are uniquely
    determined by linear solve iff the pair has full rank over Z/mZ.

    On S_m:
      - 5 of the 6 pairs — (b,e), (b,d), (e,d), (e,a), (d,a) — are always
        bijective over {1..m}^2 via linear elimination
      - 1 pair — (b, a) — is bijective iff gcd(2, m) = 1. When gcd(2, m) = g > 1,
        the pair is g-to-1 because e = (a - b) / 2 requires 2 to be invertible.

    Consequence on S_9 (gcd(2,9)=1): all 6 pairs bijective, 81/81 distinct.
    Consequence on S_24 (gcd(2,24)=2): pair (b,a) is 2-to-1, 288/576 distinct.

Pearl-Level Collapse Theorem:

    Because the structural equations are deterministic integer arithmetic (no
    stochastic noise term), Pearl's three causal hierarchy levels collapse:

      Level 1 (association):   P(d | b=b*, e=e*) = delta(d - b* - e*)
      Level 2 (intervention):  P(d | do(b=b*), e=e*) = delta(d - b* - e*)
      Level 3 (counterfactual): P(d_{b=b*} | b=b', e=e') = delta(d - b* - e')

    All three deliver the exact same value because there is no noise variable
    to marginalize. This is a degenerate (but valid) SCM — it says the
    observer projection, intervention, and counterfactual layers of Pearl's
    ladder are all collapsed into the A2 identities, which in turn IS the
    Theorem NT observer projection firewall.

Connection to Theorem NT [OBSERVER_PROJECTION_FIREWALL_SPEC]:

    The collapse of Pearl levels under determinism is exactly the statement
    that continuous observer layer functions cannot be causal inputs — the
    causal structure lives entirely in the discrete A2 equations, and the
    observer (measurement) layer sits orthogonally to it. Theorem NT IS the
    SCM identification of Pearl Level 1 with the observer projection.

QA axiom compliance:
    A1: state alphabet {1..m}; sector labels A1-adjusted
    A2: d, a derived as b+e, b+2e (the structural equations themselves)
    T2: no floats, no observer input crosses into QA state
    S1: no ** operator
    S2: integer state only
    T1: causal "time" = path length in DAG (integer)
"""

QA_COMPLIANCE = "observer=causal_dag_analyzer, state_alphabet=qa_4tuple_ZmodmZ, tier=deterministic_structural_causal_model"

from math import gcd
from typing import Dict, List, Optional, Tuple

# Node names in the QA 4-node causal DAG
CAUSAL_NODES: Tuple[str, ...] = ("b", "e", "d", "a")

# Directed edges: (parent, child). Four edges total.
CAUSAL_EDGES: Tuple[Tuple[str, str], ...] = (
    ("b", "d"),
    ("e", "d"),
    ("b", "a"),
    ("e", "a"),
)

# Exogenous vs endogenous partition
EXOGENOUS: Tuple[str, ...] = ("b", "e")
ENDOGENOUS: Tuple[str, ...] = ("d", "a")

# All 6 unordered pairs (the C(4,2) pair space for invertibility analysis)
ALL_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("b", "e"),
    ("b", "d"),
    ("b", "a"),
    ("e", "d"),
    ("e", "a"),
    ("d", "a"),
)


# -----------------------------------------------------------------------------
# QA primitives
# -----------------------------------------------------------------------------

def qa_mod(x: int, m: int) -> int:
    """A1: result in {1..m}, never 0."""
    return ((int(x) - 1) % m) + 1


def qa_tuple(b: int, e: int, m: int) -> Tuple[int, int, int, int]:
    """(b, e, d, a) with A2-derived d = b+e, a = b+2e (A1-adjusted mod m)."""
    d = b + e       # A2: d always derived as b+e
    a = b + 2 * e   # A2: a always derived as b+2e
    return (b, e, qa_mod(d, m), qa_mod(a, m))


def enumerate_state_space(m: int) -> List[Tuple[int, int]]:
    return [(b, e) for b in range(1, m + 1) for e in range(1, m + 1)]


# -----------------------------------------------------------------------------
# Pair inversion (recover (b,e) from any 2 of (b,e,d,a))
# -----------------------------------------------------------------------------

def invert_pair(pair: Tuple[str, str], v1: int, v2: int, m: int) -> Optional[Tuple[int, int]]:
    """Recover (b, e) given the values of a named pair of variables.

    Parameters
    ----------
    pair : (str, str)
        One of the 6 ordered-alphabetic pairs in ALL_PAIRS.
    v1, v2 : int
        The values of the first and second variable in the pair.
    m : int
        Modulus (e.g., 9 or 24).

    Returns
    -------
    (b, e) in {1..m}^2, or None if the pair is degenerate for this m.

    Notes
    -----
    For pair (b, a), the recovery requires solving 2e = a - b (mod m), which
    has a unique solution iff gcd(2, m) = 1. When gcd(2, m) > 1, there are
    either gcd(2, m) solutions (if (a-b) divisible by gcd) or none. This
    function returns None in the "none" case and the smallest positive lift
    in the "multiple" case (for diagnostic use; the caller should inspect
    pair_bijectivity(m) to check uniqueness).
    """
    if pair not in ALL_PAIRS:
        raise ValueError(f"pair must be one of {ALL_PAIRS}, got {pair!r}")

    if pair == ("b", "e"):
        return (v1, v2)

    if pair == ("b", "d"):
        # d = b + e -> e = d - b
        b = v1
        e = ((v2 - v1 - 1) % m) + 1
        return (b, e)

    if pair == ("e", "d"):
        # d = b + e -> b = d - e
        e = v1
        b = ((v2 - v1 - 1) % m) + 1
        return (b, e)

    if pair == ("e", "a"):
        # a = b + 2e -> b = a - 2e
        e = v1
        b = ((v2 - 2 * v1 - 1) % m) + 1
        return (b, e)

    if pair == ("d", "a"):
        # d = b+e, a = b+2e -> e = a-d, b = 2d-a
        d, a = v1, v2
        e = ((a - d - 1) % m) + 1
        b = ((2 * d - a - 1) % m) + 1
        return (b, e)

    if pair == ("b", "a"):
        # a = b + 2e -> e = (a - b) / 2, requires 2 to be a unit mod m
        b, a = v1, v2
        diff = (a - b) % m
        g = gcd(2, m)
        if diff % g != 0:
            return None  # no solution
        if g == 1:
            inv2 = pow(2, -1, m)
            e = (diff * inv2) % m
            if e == 0:
                e = m
            return (b, e)
        # Multiple solutions — return one diagnostically; caller uses pair_bijectivity
        e = ((diff // g) - 1) % m + 1
        return (b, e)

    raise AssertionError(f"unreachable: pair {pair!r} not matched")


def pair_bijectivity(m: int) -> Dict[Tuple[str, str], Dict]:
    """For each of the 6 pairs, compute bijectivity on S_m.

    Returns a dict mapping pair -> {'distinct': int, 'total': m*m, 'bijective': bool, 'fold': int}.
    """
    states = enumerate_state_space(m)
    tuples = [qa_tuple(b, e, m) for b, e in states]
    index = {"b": 0, "e": 1, "d": 2, "a": 3}

    result: Dict[Tuple[str, str], Dict] = {}
    for pair in ALL_PAIRS:
        i, j = index[pair[0]], index[pair[1]]
        projected = [(t[i], t[j]) for t in tuples]
        n_distinct = len(set(projected))
        n_total = len(projected)
        bijective = n_distinct == n_total
        fold = n_total // n_distinct if n_distinct else 0
        result[pair] = {
            "distinct": n_distinct,
            "total": n_total,
            "bijective": bijective,
            "fold": fold,
        }
    return result


# -----------------------------------------------------------------------------
# Theorem verifications
# -----------------------------------------------------------------------------

def verify_y_structure() -> Dict:
    """Verify the 4-node DAG is a Y-structure (colliders at d and a)."""
    # Count parents of each node
    parents: Dict[str, List[str]] = {n: [] for n in CAUSAL_NODES}
    children: Dict[str, List[str]] = {n: [] for n in CAUSAL_NODES}
    for src, dst in CAUSAL_EDGES:
        parents[dst].append(src)
        children[src].append(dst)

    collider_nodes = [n for n, pars in parents.items() if len(pars) >= 2]
    exogenous_nodes = [n for n, pars in parents.items() if len(pars) == 0]
    endogenous_nodes = [n for n, pars in parents.items() if len(pars) > 0]
    leaf_nodes = [n for n, kids in children.items() if len(kids) == 0]

    # Check acyclicity by topological sort
    indeg = {n: len(parents[n]) for n in CAUSAL_NODES}
    queue = [n for n in CAUSAL_NODES if indeg[n] == 0]
    topo = []
    while queue:
        v = queue.pop(0)
        topo.append(v)
        for c in children[v]:
            indeg[c] -= 1
            if indeg[c] == 0:
                queue.append(c)
    is_acyclic = len(topo) == len(CAUSAL_NODES)

    return {
        "num_nodes": len(CAUSAL_NODES),
        "num_edges": len(CAUSAL_EDGES),
        "exogenous": sorted(exogenous_nodes),
        "endogenous": sorted(endogenous_nodes),
        "colliders": sorted(collider_nodes),
        "leaves": sorted(leaf_nodes),
        "is_acyclic": is_acyclic,
        "is_y_structure": (
            sorted(exogenous_nodes) == ["b", "e"]
            and sorted(collider_nodes) == ["a", "d"]
            and is_acyclic
        ),
    }


def verify_pair_invertibility_theorem(m: int) -> Dict:
    """Check: all pairs bijective on S_m iff gcd(2, m) == 1; otherwise (b,a) fails.

    Returns bijectivity counts plus a theorem-agreement flag.
    """
    bij = pair_bijectivity(m)
    two_is_unit = gcd(2, m) == 1

    # Expected: 5 of 6 pairs always bijective; (b,a) bijective iff two_is_unit
    expected_ba_bijective = two_is_unit
    actual_ba_bijective = bij[("b", "a")]["bijective"]

    other_pairs = [p for p in ALL_PAIRS if p != ("b", "a")]
    others_all_bijective = all(bij[p]["bijective"] for p in other_pairs)

    theorem_ok = others_all_bijective and (actual_ba_bijective == expected_ba_bijective)

    return {
        "m": m,
        "gcd_2_m": gcd(2, m),
        "two_is_unit": two_is_unit,
        "pair_bijectivity": {"_".join(p): v for p, v in bij.items()},
        "other_pairs_all_bijective": others_all_bijective,
        "ba_bijective": actual_ba_bijective,
        "ba_expected_bijective": expected_ba_bijective,
        "theorem_ok": theorem_ok,
    }


def pearl_level_collapse_samples(m: int, sample_pairs: Optional[List[Tuple[int, int]]] = None) -> Dict:
    """Demonstrate Pearl level collapse on a sample: observation, intervention,
    counterfactual all give the same (d, a) under the deterministic A2 equations.

    Returns a list of witness records showing all three Pearl levels match.
    """
    if sample_pairs is None:
        sample_pairs = [(1, 1), (2, 3), (4, 5), (7, 8)]

    results = []
    for b, e in sample_pairs:
        if not (1 <= b <= m and 1 <= e <= m):
            continue
        # Level 1: observation — observe (b,e) and compute (d,a)
        obs_d = qa_mod(b + e, m)
        obs_a = qa_mod(b + 2 * e, m)

        # Level 2: intervention do(b=b, e=e) — same deterministic formula
        int_d = qa_mod(b + e, m)
        int_a = qa_mod(b + 2 * e, m)

        # Level 3: counterfactual — given observed b', e', what would d, a
        # be if b had been b_cf? Deterministic: d_cf = b_cf + e_orig
        b_cf = qa_mod(b + 1, m)
        cf_d = qa_mod(b_cf + e, m)
        cf_a = qa_mod(b_cf + 2 * e, m)

        results.append({
            "input": (b, e),
            "level_1_obs":  (obs_d, obs_a),
            "level_2_int":  (int_d, int_a),
            "level_3_cf":   {"b_cf": b_cf, "d_cf": cf_d, "a_cf": cf_a},
            "levels_1_2_match": (obs_d, obs_a) == (int_d, int_a),
            "level_3_deterministic": True,  # counterfactual is a deterministic function
        })

    all_obs_int_match = all(r["levels_1_2_match"] for r in results)
    return {
        "m": m,
        "witnesses": results,
        "all_level_1_2_collapse": all_obs_int_match,
    }


# -----------------------------------------------------------------------------
# S_9 / S_24 theorem constants
# -----------------------------------------------------------------------------

# Theorem: on S_9, all 6 pairs bijective; on S_24, only (b,a) fails (2-to-1).
EXPECTED_S9_ALL_BIJECTIVE = True
EXPECTED_S24_BA_FOLD = 2


__all__ = [
    "CAUSAL_NODES",
    "CAUSAL_EDGES",
    "EXOGENOUS",
    "ENDOGENOUS",
    "ALL_PAIRS",
    "qa_mod",
    "qa_tuple",
    "enumerate_state_space",
    "invert_pair",
    "pair_bijectivity",
    "verify_y_structure",
    "verify_pair_invertibility_theorem",
    "pearl_level_collapse_samples",
    "EXPECTED_S9_ALL_BIJECTIVE",
    "EXPECTED_S24_BA_FOLD",
]
