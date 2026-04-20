"""
QA Orbit-Resonance Attention — minimum viable prototype.

Demonstrates that attention can be expressed as a deterministic
function of integer orbit structure, with no learned parameters
and no stochastic selection operator.

Design claim (docs/theory/QA_GLM5_ARCHITECTURE_MAPPING.md):
attention is not a learned scoring function followed by a discrete
top-k selection. Attention IS orbit resonance — two tokens attend
iff their (b, e) tuples satisfy a resonance relation defined on
the T-orbit structure of the five classical QA families
(Fibonacci / Lucas / Phibonacci / Tribonacci / Ninbonacci) under
the Eisenstein norm classification of cert [214].

Structural consequences this prototype exhibits:
  - No scoring function and no learned parameters.
  - No top-k operator → the GLM-5 entropy-collapse failure mode
    from non-deterministic torch.topk is structurally impossible.
  - Bitwise-reproducible output across repeated calls (A1 + NT).
  - Integer-only state on the attention path (S2).

Three resonance rules are provided:
  - family_match : same T-orbit family (Eisenstein cert [214])
  - norm_match   : same Eisenstein norm mod m
  - chromogeometry: Pythagorean chromogeometry inner product
                   C_i*C_j + F_i*F_j == G_i*G_j (mod m) — cert [234]

Usage:
  python qa_lab/qa_orbit_resonance_attention.py        # self-test + demo
"""

QA_COMPLIANCE = "integer-only, deterministic, no learned parameters"

from pathlib import Path
from typing import List, Sequence, Tuple

from qa_lab.qa_core.algebra import qa_step
from qa_lab.qa_core.orbits import classify_state


# -----------------------------------------------------------------------------
# Eisenstein family classification (cert [214])
# -----------------------------------------------------------------------------
#
# On S_9 the five T-orbit families are:
#   Fibonacci  (cosmos,      rep (1,1), norm pair {1, 8})
#   Lucas      (cosmos,      rep (1,3), norm pair {4, 5})
#   Phibonacci (cosmos,      rep (1,4), norm pair {2, 7})
#   Tribonacci (satellite,   rep (3,3), norm {0})
#   Ninbonacci (singularity, rep (9,9), norm {0})
#
# See qa_alphageometry_ptolemy/qa_norm_flip_signed_cert_v1/ for the proof
# that f(e, b+e) = -f(b, e) where f(b,e) = b*b + b*e - e*e.

_NORM_PAIR_TO_FAMILY_S9 = {
    frozenset({1, 8}): "fibonacci",
    frozenset({4, 5}): "lucas",
    frozenset({2, 7}): "phibonacci",
}


def eisenstein_norm(b: int, e: int, m: int) -> int:
    """f(b, e) = b*b + b*e - e*e  mod m. S1-compliant (no **)."""
    return (b * b + b * e - e * e) % m


def orbit_family_s9(b: int, e: int) -> str:
    """Classify (b, e) on S_9 into one of the five T-orbit families."""
    m = 9
    coarse = classify_state(b, e, m)
    if coarse == "singularity":
        return "ninbonacci"
    if coarse == "satellite":
        return "tribonacci"
    norm = eisenstein_norm(b, e, m)
    for pair, family in _NORM_PAIR_TO_FAMILY_S9.items():
        if norm in pair:
            return family
    raise ValueError(
        f"cosmos state ({b},{e}) produced norm {norm} not in any known pair"
    )


# -----------------------------------------------------------------------------
# Orbit-resonance attention
# -----------------------------------------------------------------------------

def orbit_resonance_attention(
    tokens: Sequence[Tuple[int, int]],
    m: int = 9,
    rule: str = "family_match",
) -> List[List[int]]:
    """Compute the N x N integer resonance matrix.

    Parameters
    ----------
    tokens : sequence of (b, e) with b, e in {1, ..., m}
    m      : modulus (m=9 required for family_match)
    rule   : 'family_match' | 'norm_match' | 'chromogeometry'

    Returns
    -------
    list[list[int]] — A[i][j] in {0, 1}.
    """
    for (b, e) in tokens:
        if not (1 <= b <= m and 1 <= e <= m):
            raise ValueError(f"A1 violation: ({b},{e}) outside {{1,...,{m}}}")

    if rule == "family_match" and m != 9:
        raise NotImplementedError("family_match currently only for m=9")

    n = len(tokens)
    A = [[0] * n for _ in range(n)]

    if rule == "family_match":
        families = [orbit_family_s9(b, e) for (b, e) in tokens]
        for i in range(n):
            for j in range(n):
                A[i][j] = 1 if families[i] == families[j] else 0
        return A

    if rule == "norm_match":
        norms = [eisenstein_norm(b, e, m) for (b, e) in tokens]
        for i in range(n):
            for j in range(n):
                A[i][j] = 1 if norms[i] == norms[j] else 0
        return A

    if rule == "chromogeometry":
        # Elements (C, F, G) computed RAW per 2026-04-09 rule — no mod reduction
        # in element context. Mod m is only applied to the cross-pair bilinear
        # comparison below, where it is a modular-equivalence check, not an
        # element computation.
        triples = []
        for (b, e) in tokens:
            d = b + e                # RAW
            a = b + 2 * e            # RAW
            C = 2 * d * e            # RAW
            F = b * a                # RAW
            G = e * e + d * d        # RAW
            triples.append((C, F, G))
        for i in range(n):
            Ci, Fi, Gi = triples[i]
            for j in range(n):
                Cj, Fj, Gj = triples[j]
                lhs = (Ci * Cj + Fi * Fj) % m
                rhs = (Gi * Gj) % m
                A[i][j] = 1 if lhs == rhs else 0
        return A

    raise ValueError(f"unknown rule: {rule!r}")


# -----------------------------------------------------------------------------
# Evolution layer — T-operator on integer path time
# -----------------------------------------------------------------------------
#
# T(b, e) = (e, qa_mod(b+e, m)). Each token advances independently under T at
# each integer path-time step. Path-time `t` is an integer index; there is no
# continuous time variable on this layer (T1).
#
# Structural property of QA-native attention:
#
# All three resonance rules defined here are ORBIT-INVARIANT under evolution
# — verified empirically over 24 T-steps on 10 diverse tokens covering all
# five T-orbit families. The reason is structural: each rule is a function
# of T-invariant quantities on (b, e) tuples.
#
#   - family_match: T preserves orbit membership, so family labels are
#     T-invariant pointwise.
#   - norm_match: Eisenstein norm flips sign under T globally across all
#     tokens simultaneously (cert [214]), preserving pairwise equality.
#   - chromogeometry: the bilinear form C_i*C_j + F_i*F_j vs G_i*G_j is
#     empirically T-invariant on S_9 for all tested pairs; this reflects
#     the underlying Pythagorean identity C² + F² = G² (cert [234]) at the
#     cross-pair level.
#
# This is the structural argument for QA-native attention: resonance rules
# built from T-invariant integer forms produce orbit-invariant attention
# patterns, meaning attention is intrinsic to orbit structure rather than
# to the specific path-time sample. Standard-math attention has no such
# invariance — it is learned on whatever activations happen to be present
# at whatever step they are sampled.


def T_step(b: int, e: int, m: int = 9) -> Tuple[int, int]:
    """Single T-step: (b, e) -> (e, qa_mod(b+e, m)). Canonical A1-compliant."""
    return qa_step(b, e, m)


def evolve(
    tokens: Sequence[Tuple[int, int]],
    steps: int,
    m: int = 9,
) -> List[List[Tuple[int, int]]]:
    """Advance all tokens through `steps` integer path-time steps.

    Returns the full trajectory: list of length steps+1, each entry a list
    of N tuples. trajectory[0] == list(tokens); trajectory[k] is the state
    after k T-steps.
    """
    if steps < 0:
        raise ValueError(f"steps must be >= 0, got {steps}")
    state = [tuple(t) for t in tokens]
    trajectory = [list(state)]
    for _ in range(steps):
        state = [T_step(b, e, m) for (b, e) in state]
        trajectory.append(list(state))
    return trajectory


def observer_project_out(
    tokens: Sequence[Tuple[int, int]],
    m: int = 9,
) -> List[Tuple[int, int, int, int]]:
    """Output-boundary observer projection: tuples -> (b, e, d, a).

    Uses RAW d = b+e, a = b+2e (per 2026-04-09 rule — elements use raw
    derived coords; mod reduction is T-operator ONLY). This is the final
    boundary crossing; downstream continuous measurement acts on these.
    """
    # m is unused for RAW projection, but kept in signature for symmetry.
    _ = m
    return [(b, e, b + e, b + 2 * e) for (b, e) in tokens]


# -----------------------------------------------------------------------------
# Generator-pattern training — discrete search on integer path time
# -----------------------------------------------------------------------------
#
# "Training" in the QA-native architecture is identification of the integer
# generator pattern whose T-orbit matches a target trace. There is no float
# policy, no gradient, no optimizer state (Adam m/v). Moves are discrete hops
# in a finite generator space; evaluation is exact orbit-trace match, not a
# scalar loss.
#
# The generator space on S_m is all 81 starting tuples (b, e) in {1..m}^2 (m=9).
# Given a target sequence of observed tuples, the trained generator is the
# starting (b_0, e_0) whose T-orbit best matches under exact-match count.
#
# This is the structural replacement for PPO / IS / trust regions / optimizer
# resets: a finite discrete search produces a deterministic integer pattern.
# No float policy exists to drift; no "staleness" can occur.


def identify_generator(
    target_trace: Sequence[Tuple[int, int]],
    m: int = 9,
) -> Tuple[Tuple[int, int], int]:
    """Discrete-search training: find the starting (b_0, e_0) whose T-orbit
    best matches the target trace under exact tuple-equality count.

    Returns (best_start_tuple, match_count). Ties are broken by lexicographic
    order on (b, e) to guarantee bitwise determinism across invocations.

    Integer-only, no gradients, no optimizer state. Bitwise reproducible.
    """
    if not target_trace:
        raise ValueError("target_trace must be non-empty")
    n = len(target_trace)
    # Coerce to tuple-of-tuples for exact comparison
    target = [tuple(t) for t in target_trace]

    best_start: Tuple[int, int] = (1, 1)
    best_score: int = -1

    # Exhaustive search over 81 starting tuples in {1..m}^2
    for b0 in range(1, m + 1):
        for e0 in range(1, m + 1):
            state = (b0, e0)
            score = 0
            for k in range(n):
                if state == target[k]:
                    score += 1
                state = T_step(state[0], state[1], m)
            if score > best_score:
                best_score = score
                best_start = (b0, e0)
            # else: tie — keep earlier (lexicographic determinism)
    return best_start, best_score


def identify_family(
    target_trace: Sequence[Tuple[int, int]],
    m: int = 9,
) -> Tuple[str, int]:
    """Coarser generator identification: which of the five T-orbit families
    best matches the target trace, by plurality of family classifications.

    Returns (best_family_name, count_in_trace).
    """
    if not target_trace:
        raise ValueError("target_trace must be non-empty")
    if m != 9:
        raise NotImplementedError("identify_family currently only for m=9")

    counts = {
        "fibonacci": 0,
        "lucas": 0,
        "phibonacci": 0,
        "tribonacci": 0,
        "ninbonacci": 0,
    }
    for (b, e) in target_trace:
        counts[orbit_family_s9(b, e)] += 1
    # Deterministic tie-break: ordering of the dict above (stable insertion order)
    best_family = max(counts, key=lambda k: (counts[k], -list(counts).index(k)))
    return best_family, counts[best_family]


# -----------------------------------------------------------------------------
# Self-tests
# -----------------------------------------------------------------------------

def _test_determinism() -> None:
    """Bitwise-identical output across repeated calls — the GLM-5 torch.topk
    non-determinism failure mode is structurally impossible here."""
    tokens = [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9), (2, 5), (7, 2)]
    for rule in ("family_match", "norm_match", "chromogeometry"):
        A1 = orbit_resonance_attention(tokens, rule=rule)
        A2 = orbit_resonance_attention(tokens, rule=rule)
        assert A1 == A2, f"determinism violated under rule={rule}"


def _test_reflexivity() -> None:
    """Every token resonates with itself under family_match."""
    tokens = [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9), (5, 7)]
    A = orbit_resonance_attention(tokens)
    for i in range(len(tokens)):
        assert A[i][i] == 1, f"reflexivity failed at {i}: {tokens[i]}"


def _test_family_partitioning() -> None:
    """Representatives of the 5 families land in distinct classes and
    resonate only within their class under family_match."""
    reps = [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9)]
    expected = ["fibonacci", "lucas", "phibonacci", "tribonacci", "ninbonacci"]
    for (b, e), fam in zip(reps, expected):
        assert orbit_family_s9(b, e) == fam, f"({b},{e}) -> {orbit_family_s9(b, e)}, expected {fam}"

    A = orbit_resonance_attention(reps)
    for i in range(len(reps)):
        for j in range(len(reps)):
            assert A[i][j] == (1 if i == j else 0), (
                f"off-diagonal resonance between distinct families at ({i},{j})"
            )


def _test_cosmos_fibonacci_orbit_all_resonate() -> None:
    """Two states on the Fibonacci cosmos orbit must family-match.
    (1,1) and its T-image (1,2) are both on the Fibonacci orbit."""
    # T(b,e) = (e, b+e mod m). T(1,1) = (1, 2). Norm of (1,2) = 1+2-4 = -1 = 8 mod 9.
    tokens = [(1, 1), (1, 2)]
    assert orbit_family_s9(1, 1) == "fibonacci"
    assert orbit_family_s9(1, 2) == "fibonacci"
    A = orbit_resonance_attention(tokens)
    assert A == [[1, 1], [1, 1]], f"same-orbit states failed to resonate: {A}"


def _test_no_learned_params() -> None:
    """Static check: module declares no imports of learning frameworks
    (torch, jax, tensorflow). Without those, no trainable parameters can
    exist on the attention path by construction."""
    import ast
    tree = ast.parse(Path(__file__).read_text())
    forbidden = {"torch", "jax", "tensorflow", "tf"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in forbidden, f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = node.module.split(".")[0]
            assert root not in forbidden, f"forbidden import-from: {node.module}"


def _test_a1_violation_rejected() -> None:
    """Tokens outside {1,...,m} must be rejected (A1 guard)."""
    try:
        orbit_resonance_attention([(0, 1)])
    except ValueError:
        pass
    else:
        raise AssertionError("A1 violation (0,1) not rejected")


def _test_family_match_invariant_under_evolution() -> None:
    """The family_match attention pattern does not change as tokens
    evolve under T, because family is an invariant of the T-orbit.
    This is the structural reason family_match is the 'right' rule:
    attention is intrinsic to orbit structure, not to sampling time."""
    tokens = [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9), (2, 5), (5, 4), (7, 2)]
    traj = evolve(tokens, steps=12)
    A0 = orbit_resonance_attention(traj[0], rule="family_match")
    for k, state in enumerate(traj):
        Ak = orbit_resonance_attention(state, rule="family_match")
        assert Ak == A0, f"family_match changed at step {k}"


def _test_norm_match_invariant_under_evolution() -> None:
    """Under T every token's Eisenstein norm flips simultaneously
    (cert [214]: f(T(b,e)) = -f(b,e)). Because the flip is global across
    all tokens, pairwise norm-equality is preserved at every step."""
    tokens = [(1, 1), (1, 3), (2, 5), (5, 4), (7, 2), (4, 1)]
    traj = evolve(tokens, steps=8)
    A0 = orbit_resonance_attention(traj[0], rule="norm_match")
    for k, state in enumerate(traj):
        Ak = orbit_resonance_attention(state, rule="norm_match")
        assert Ak == A0, f"norm_match changed at step {k}"


def _test_chromogeometry_orbit_invariant() -> None:
    """chromogeometry is empirically T-invariant on S_9 across all tested tokens.
    Verified over 24 T-steps on 10 diverse tokens covering all five T-orbit
    families. Reflects the cross-pair Pythagorean identity structure
    (cert [234])."""
    tokens = [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9), (2, 5), (5, 4), (7, 2), (8, 8), (6, 1)]
    traj = evolve(tokens, steps=24)
    A0 = orbit_resonance_attention(traj[0], rule="chromogeometry")
    for k, state in enumerate(traj):
        Ak = orbit_resonance_attention(state, rule="chromogeometry")
        assert Ak == A0, f"chromogeometry changed at step {k}"


def _test_family_norm_crosscut() -> None:
    """family_match and norm_match crosscut — neither is a refinement of the
    other:
      - Within cosmos: norm_match is STRICTER (each cosmos family has norm
        pair {k, m-k}; (1,1) and (1,2) are Fibonacci-family but have norms
        1 and 8 respectively, so norm_match excludes them).
      - Across null orbits: norm_match is COARSER (tribonacci (3,3) and
        ninbonacci (9,9) both have norm 0; norm_match merges them while
        family_match keeps them distinct).
    """
    tokens = [(1, 1), (1, 2), (3, 3), (9, 9)]
    A_fam = orbit_resonance_attention(tokens, rule="family_match")
    A_norm = orbit_resonance_attention(tokens, rule="norm_match")

    # (1,1) fib norm 1, (1,2) fib norm 8 — same family, different norms
    assert A_fam[0][1] == 1 and A_norm[0][1] == 0, (
        "family-match without norm-match expected for Fibonacci pair with different norms"
    )
    # (3,3) tribonacci norm 0, (9,9) ninbonacci norm 0 — different families, same norm
    assert A_fam[2][3] == 0 and A_norm[2][3] == 1, (
        "norm-match without family-match expected for tribonacci-ninbonacci pair"
    )


def _test_observer_project_out_raw() -> None:
    """Output observer uses raw d = b+e, a = b+2e — not mod-reduced."""
    out = observer_project_out([(5, 7), (8, 8)])
    # (5,7): d=12, a=19; (8,8): d=16, a=24  — all raw, exceeding m=9
    assert out == [(5, 7, 12, 19), (8, 8, 16, 24)], out


def _test_evolve_preserves_integers() -> None:
    """Evolution produces integer tuples at every step — no float leakage (S2)."""
    traj = evolve([(1, 1), (3, 3), (9, 9), (4, 7)], steps=10)
    for state in traj:
        for (b, e) in state:
            assert isinstance(b, int) and isinstance(e, int), f"non-int state: {(b, e)}"
            assert 1 <= b <= 9 and 1 <= e <= 9, f"A1 violation after evolve: {(b, e)}"


def _test_singularity_is_fixed_under_T() -> None:
    """(9, 9) is the singularity — T fixes it."""
    traj = evolve([(9, 9)], steps=100)
    for state in traj:
        assert state == [(9, 9)], f"singularity drifted: {state}"


def _test_identify_generator_recovers_starting_tuple() -> None:
    """Generate a trace from a known starting tuple, then train to identify it.
    The trained generator should recover the starting tuple exactly (score=len)."""
    for start in [(1, 1), (1, 3), (1, 4), (3, 3), (9, 9), (2, 5), (7, 2)]:
        traj = [start]
        s = start
        for _ in range(24):
            s = T_step(s[0], s[1])
            traj.append(s)
        found, score = identify_generator(traj)
        assert found == start, f"identify_generator recovered {found}, expected {start}"
        assert score == len(traj), f"score={score}, expected {len(traj)} for exact match"


def _test_identify_generator_deterministic() -> None:
    """Repeated training calls on identical trace produce bitwise-identical output.
    No stochastic sampling, no random restarts."""
    traj = [(1, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 4), (4, 3)]
    r1 = identify_generator(traj)
    r2 = identify_generator(traj)
    assert r1 == r2, "identify_generator non-deterministic"


def _test_identify_family_returns_correct_family() -> None:
    """A trace entirely on the Fibonacci cosmos orbit identifies as fibonacci."""
    traj = evolve([(1, 1)], steps=23)
    flat = [state[0] for state in traj]
    found, count = identify_family(flat)
    assert found == "fibonacci", f"expected fibonacci, got {found}"
    assert count == 24, f"expected all 24 steps fibonacci, got {count}"


def _test_identify_generator_no_float_state() -> None:
    """The returned generator is an integer tuple — no Fraction, no float."""
    found, score = identify_generator([(1, 1), (1, 2), (2, 3)])
    b, e = found
    assert isinstance(b, int) and isinstance(e, int), f"non-int result: {found}"
    assert isinstance(score, int), f"non-int score: {score}"


def _run_tests() -> None:
    _test_determinism()
    _test_reflexivity()
    _test_family_partitioning()
    _test_cosmos_fibonacci_orbit_all_resonate()
    _test_no_learned_params()
    _test_a1_violation_rejected()
    _test_family_match_invariant_under_evolution()
    _test_norm_match_invariant_under_evolution()
    _test_chromogeometry_orbit_invariant()
    _test_family_norm_crosscut()
    _test_observer_project_out_raw()
    _test_evolve_preserves_integers()
    _test_singularity_is_fixed_under_T()
    _test_identify_generator_recovers_starting_tuple()
    _test_identify_generator_deterministic()
    _test_identify_family_returns_correct_family()
    _test_identify_generator_no_float_state()


# -----------------------------------------------------------------------------
# Demo
# -----------------------------------------------------------------------------

def _demo() -> None:
    tokens = [(1, 1), (1, 2), (1, 3), (1, 4), (3, 3), (9, 9), (2, 5), (5, 4)]
    print("QA Orbit-Resonance Attention — prototype demo")
    print("=" * 60)
    print(f"Input tokens (b, e): {tokens}")
    families = [orbit_family_s9(b, e) for (b, e) in tokens]
    norms = [eisenstein_norm(b, e, 9) for (b, e) in tokens]
    print(f"Families           : {families}")
    print(f"Eisenstein norms   : {norms}")
    print()

    # --- Attention patterns at t=0 ---
    for rule in ("family_match", "norm_match", "chromogeometry"):
        A = orbit_resonance_attention(tokens, rule=rule)
        print(f"Attention (t=0, rule={rule!r}):")
        print("    " + " ".join(f"{i:2d}" for i in range(len(tokens))))
        for i, row in enumerate(A):
            print(f"{i:2d}  " + " ".join(f"{x:2d}" for x in row))
        print()

    # --- Evolution trajectory ---
    print("-" * 60)
    print("Evolution under T (8 integer path-time steps):")
    traj = evolve(tokens, steps=8)
    for k, state in enumerate(traj):
        print(f"  t={k}: {state}")
    print()

    # --- Invariance / oscillation signature ---
    print("-" * 60)
    print("Structural attention properties under evolution:")
    for rule in ("family_match", "norm_match", "chromogeometry"):
        A_k = [orbit_resonance_attention(s, rule=rule) for s in traj]
        invariant = all(A == A_k[0] for A in A_k)
        print(f"  {rule:14s} A(t=0) == A(t=k) for k=0..8 ? {invariant}")
    print()
    print("All three resonance rules are orbit-invariant under T: attention")
    print("is intrinsic to orbit structure, independent of path-time sample.")
    print()

    # --- Output-boundary observer projection ---
    print("-" * 60)
    print("Output observer projection (t=8) -> (b, e, d, a) with RAW d, a:")
    final = observer_project_out(traj[-1])
    for (bead, src) in zip(final, traj[-1]):
        print(f"  {src} -> {bead}")
    print()
    print("Pipeline: input tuples -> attention (integer) -> evolve (integer) -> output observer.")
    print("No learned parameters, no float state, no stochastic selection.")

    # --- Generator-pattern training demo ---
    print()
    print("-" * 60)
    print("Generator-pattern training (discrete search, no gradients):")
    # Simulate: we observed a partial trace and want to identify its source
    target_start = (2, 5)
    observed = []
    s = target_start
    for _ in range(12):
        observed.append(s)
        s = T_step(s[0], s[1])
    print(f"  Observed trace (12 steps from unknown start): {observed}")
    found, score = identify_generator(observed)
    print(f"  Identified starting tuple: {found}  (match score: {score}/{len(observed)})")
    family, fam_count = identify_family(observed)
    print(f"  Identified family: {family!r}  ({fam_count}/{len(observed)} tokens)")
    print(f"  Ground truth: start={target_start}, family={orbit_family_s9(*target_start)!r}")


if __name__ == "__main__":
    _run_tests()
    print("Tests: PASS\n")
    _demo()
