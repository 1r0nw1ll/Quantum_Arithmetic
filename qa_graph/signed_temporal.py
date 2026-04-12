"""QA Signed-Temporal Orbit Graph — Eisenstein norm flip under T.

The Eisenstein quadratic form

    f(b, e) = b*b + b*e - e*e

satisfies the integer identity f(T(b, e)) = -f(b, e), where T is the QA
generator T(b, e) = (e, b+e). This gives the T-orbit graph a natural signed-
temporal structure: at each integer path-time step, the sign of the integer-
lifted Eisenstein norm flips.

Theorems (exhaustively verified on S_9):

    1. NORM FLIP (integer identity):
           f(e, b+e) = -f(b, e)    for all (b, e) in Z^2
       81/81 match on S_9.

    2. T^2 NORM PRESERVATION:
           f(T^2(b,e)) mod m = f(b,e) mod m    for all (b, e) in S_m
       81/81 match on S_9.

    3. FIVE SIGNED ORBIT FAMILIES ON S_9:
           Orbit 0: cosmos rep (1,1), size 24, norm pair {1, 8} mod 9   (Fibonacci)
           Orbit 1: cosmos rep (1,3), size 24, norm pair {4, 5} mod 9   (Lucas)
           Orbit 2: cosmos rep (1,4), size 24, norm pair {2, 7} mod 9   (Phibonacci)
           Orbit 3: satellite rep (3,3), size 8,  norm {0}               (Tribonacci)
           Orbit 4: singularity (9,9), size 1,  norm {0}                 (Ninbonacci)

       The three cosmos orbits have bipartite signed structure (two sign cohorts
       of size 12 each, alternating under T). The satellite and singularity
       orbits are the "null" subgraph where f is identically zero mod 9.

    4. TEMPORAL SIGN FORMULA:
           sign(f(T^t(s_0))) = (-1)^t * sign(f(s_0))
       where sign is taken on the integer lift. On mod-9 orbits this becomes
       a bipartite coloring with period 2.

Connections:
    [133] QA Eisenstein Cert   — the norm identities F^2-FW+W^2=Z^2 that use f
    [155] QA Bearden Phase Conjugate Cert — phase conjugation = QCI sign flip,
                                   structurally parallel to this norm flip
    [191] QA Bateson Learning Levels — cosmos/satellite/singularity stratification
                                   IS the null-vs-signed orbit partition
    [211] QA Cayley Bateson Filtration — same T dynamic, generator graph view
    [212] QA Fibonacci Hypergraph      — same T dynamic, sliding window view
    [213] QA Causal DAG                — same (b,e,d,a), SCM view

QA axiom compliance:
    A1: state alphabet {1..m}; sector via 1 + ((x-1) mod m)
    A2: d, a derived as b+e, b+2e when used; here f uses only b, e (not derived)
    T2: no floats; all computations are integer
    S1: b*b not b**2 throughout
    S2: integer state only
    T1: path time t is a non-negative integer
"""

QA_COMPLIANCE = "observer=signed_orbit_analyzer, state_alphabet=qa_state_space_S_m, tier=integer_eisenstein_norm_signed_temporal_graph"

from typing import Dict, List, Tuple

State = Tuple[int, int]


# -----------------------------------------------------------------------------
# QA primitives (integer-only, S1-compliant: b*b not b**2)
# -----------------------------------------------------------------------------

def qa_mod(x: int, m: int) -> int:
    """A1: result in {1..m}."""
    return ((int(x) - 1) % m) + 1


def qa_step(b: int, e: int, m: int) -> State:
    """T: (b, e) -> (e, (b+e) mod m)."""
    return (e, qa_mod(b + e, m))


def eisenstein_norm(b: int, e: int) -> int:
    """f(b, e) = b*b + b*e - e*e  (integer, NOT mod-reduced).

    This is the Eisenstein-like quadratic form in two integer variables.
    Its unreduced value is an integer in Z. S1-compliant: no ** operator.
    """
    return b * b + b * e - e * e   # S1: b*b, not b**2


def enumerate_state_space(m: int) -> List[State]:
    return [(b, e) for b in range(1, m + 1) for e in range(1, m + 1)]


# -----------------------------------------------------------------------------
# Theorem verifications
# -----------------------------------------------------------------------------

def verify_norm_flip_identity(m: int) -> Dict:
    """Verify f(e, b+e) = -f(b, e) exhaustively on {1..m}^2.

    Notes the identity holds on the Z^2 LIFT (b, b+e) — not after mod-m
    reduction. So the check is the integer identity for the unreduced
    Fibonacci matrix action, evaluated at each lifted (b, e) in {1..m}^2.
    """
    checked = 0
    matched = 0
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            checked += 1
            lhs = eisenstein_norm(e, b + e)      # integer, not mod
            rhs = -eisenstein_norm(b, e)
            if lhs == rhs:
                matched += 1
    return {
        "m": m,
        "checked": checked,
        "matched": matched,
        "identity_ok": matched == checked,
    }


def verify_t2_norm_preservation(m: int) -> Dict:
    """Verify f(T^2(s)) mod m == f(s) mod m exhaustively on S_m."""
    checked = 0
    matched = 0
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            checked += 1
            n0 = eisenstein_norm(b, e) % m
            b2, e2 = qa_step(b, e, m)
            b4, e4 = qa_step(b2, e2, m)
            n2 = eisenstein_norm(b4, e4) % m
            if n0 == n2:
                matched += 1
    return {
        "m": m,
        "checked": checked,
        "matched": matched,
        "t2_preserves_norm_mod_m": matched == checked,
    }


def signed_orbit_classification(m: int) -> List[Dict]:
    """Enumerate T-orbits of S_m and classify each by norm-pair structure.

    For each orbit, reports:
        representative, length, family ('cosmos'/'satellite'/'singularity'),
        distinct_norms_mod_m (sorted), norm_pair_type ('signed' or 'null').

    On S_9 returns 5 orbits:
        cosmos 24 (1,1) {1,8}
        cosmos 24 (1,3) {4,5}
        cosmos 24 (1,4) {2,7}
        satellite 8 (3,3) {0}
        singularity 1 (9,9) {0}
    """
    def family_of(b: int, e: int) -> str:
        if b == m and e == m:
            return "singularity"
        if (b % 3 == 0) and (e % 3 == 0) and m == 9:
            return "satellite"
        return "cosmos"

    seen = set()
    results = []
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            if (b, e) in seen:
                continue
            orbit = []
            cur = (b, e)
            while cur not in seen:
                seen.add(cur)
                orbit.append(cur)
                cur = qa_step(cur[0], cur[1], m)
            norms = sorted(set(eisenstein_norm(bi, ei) % m for bi, ei in orbit))
            if norms == [0]:
                pair_type = "null"
            elif len(norms) == 2 and (norms[0] + norms[1]) % m == 0:
                pair_type = "signed"
            else:
                pair_type = "other"
            results.append({
                "representative": list(orbit[0]),
                "length": len(orbit),
                "family": family_of(*orbit[0]),
                "distinct_norms_mod_m": norms,
                "pair_type": pair_type,
            })
    return results


def temporal_sign_sequence(b: int, e: int, m: int, steps: int) -> List[int]:
    """Return the sequence of signed integer-lift norms along the orbit starting
    at (b, e), for `steps` many T applications.

    Each element is the integer Eisenstein norm f(b_t, e_t), not reduced mod m.
    By the flip theorem on the integer lift, the sign alternates when the
    states are not mod-reduced. When we do reduce at each step (as T does on
    S_m), the mod-9 norm sequence exhibits a bipartite {+,-} coloring with
    period 2.
    """
    seq = [eisenstein_norm(b, e)]
    bi, ei = b, e
    for _ in range(steps):
        bi, ei = qa_step(bi, ei, m)
        seq.append(eisenstein_norm(bi, ei))
    return seq


# -----------------------------------------------------------------------------
# S_9 theorem constants (for cert consumption)
# -----------------------------------------------------------------------------

# Expected orbit classification on S_9. The 5 orbits match the Pythagorean
# Families paper (Fibonacci, Lucas, Phibonacci, Tribonacci, Ninbonacci).
SIGNED_ORBITS_S9 = [
    {"representative": [1, 1], "length": 24, "family": "cosmos",      "distinct_norms_mod_m": [1, 8], "pair_type": "signed", "classical_name": "Fibonacci"},
    {"representative": [1, 3], "length": 24, "family": "cosmos",      "distinct_norms_mod_m": [4, 5], "pair_type": "signed", "classical_name": "Lucas"},
    {"representative": [1, 4], "length": 24, "family": "cosmos",      "distinct_norms_mod_m": [2, 7], "pair_type": "signed", "classical_name": "Phibonacci"},
    {"representative": [3, 3], "length": 8,  "family": "satellite",   "distinct_norms_mod_m": [0],    "pair_type": "null",   "classical_name": "Tribonacci"},
    {"representative": [9, 9], "length": 1,  "family": "singularity", "distinct_norms_mod_m": [0],    "pair_type": "null",   "classical_name": "Ninbonacci"},
]


def verify_all_on_s9() -> Dict:
    """Run all three theorem checks on S_9 and return a single summary dict."""
    flip = verify_norm_flip_identity(9)
    t2 = verify_t2_norm_preservation(9)
    orbits = signed_orbit_classification(9)

    orbits_match = len(orbits) == len(SIGNED_ORBITS_S9)
    if orbits_match:
        actual_sorted = sorted(
            ((o["length"], tuple(o["distinct_norms_mod_m"]), o["pair_type"]) for o in orbits),
            reverse=True,
        )
        expected_sorted = sorted(
            ((o["length"], tuple(o["distinct_norms_mod_m"]), o["pair_type"]) for o in SIGNED_ORBITS_S9),
            reverse=True,
        )
        orbits_match = actual_sorted == expected_sorted

    return {
        "flip_identity": flip,
        "t2_preservation": t2,
        "orbits": orbits,
        "orbits_match_expected": orbits_match,
        "all_ok": flip["identity_ok"] and t2["t2_preserves_norm_mod_m"] and orbits_match,
    }


__all__ = [
    "State",
    "qa_mod",
    "qa_step",
    "eisenstein_norm",
    "enumerate_state_space",
    "verify_norm_flip_identity",
    "verify_t2_norm_preservation",
    "signed_orbit_classification",
    "temporal_sign_sequence",
    "verify_all_on_s9",
    "SIGNED_ORBITS_S9",
]
