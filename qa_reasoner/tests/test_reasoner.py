"""Tests for qa_reasoner — exact discrete reasoning."""

from qa_reasoner import QAReasoner, compute_16_identities, chromogeometric_quadrances
from qa_reasoner.identities import verify_identities
from qa_reasoner.patterns import PatternMatcher


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def test_classify_singularity_mod_9():
    r = QAReasoner(9)
    res = r.classify(9, 9)
    assert res.family == "singularity"
    assert res.orbit_length_ == 1
    assert res.tuple4 == (9, 9, 9, 9)


def test_classify_cosmos_mod_9():
    r = QAReasoner(9)
    res = r.classify(1, 1)
    assert res.family == "cosmos"
    assert res.orbit_length_ == 24
    assert res.tuple4 == (1, 1, 2, 3)


def test_classify_satellite_mod_9():
    r = QAReasoner(9)
    res = r.classify(3, 3)
    assert res.family == "satellite"
    assert res.orbit_length_ == 8


def test_canonicalize_wraps_to_a1():
    r = QAReasoner(9)
    # 10 → 1, 18 → 9 under qa_mod
    assert r.canonicalize(10, 18) == (1, 9)


def test_orbit_statistics_mod_9():
    r = QAReasoner(9)
    stats = r.orbit_statistics()
    # 9² = 81 total pairs: 72 cosmos, 8 satellite, 1 singularity
    assert stats["cosmos"] == 72
    assert stats["satellite"] == 8
    assert stats["singularity"] == 1
    assert sum(stats.values()) == 81


def test_orbit_statistics_mod_24():
    r = QAReasoner(24)
    stats = r.orbit_statistics()
    # 24² = 576 total
    assert sum(stats.values()) == 576
    assert stats["singularity"] == 1


# ---------------------------------------------------------------------------
# Identities — exact integer algebra
# ---------------------------------------------------------------------------

def test_identities_fibonacci_seed():
    ids = compute_16_identities(1, 1)
    # d = 2, a = 3
    assert ids["A"] == 9   # a*a = 3*3
    assert ids["B"] == 1   # b*b
    assert ids["C"] == 4   # 2*d*e = 2*2*1
    assert ids["D"] == 4   # d*d
    assert ids["E"] == 1   # e*e
    assert ids["F"] == 3   # a*b = 3*1
    assert ids["G"] == 5   # d²+e² = 4+1
    assert ids["H"] == 7   # C+F = 4+3
    assert ids["I"] == 1   # C-F = 4-3
    assert ids["J"] == 2   # b*d = 1*2
    assert ids["K"] == 6   # a*d = 3*2


def test_identities_verified_for_all_fibonacci_pairs():
    # All (F_n, F_{n+1}) pairs should satisfy all identity relations
    fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    for i in range(len(fib) - 1):
        v = verify_identities(fib[i], fib[i + 1])
        assert all(v.values()), f"identity failure at ({fib[i]}, {fib[i+1]}): {v}"


def test_chromogeometry_theorem_exact():
    # Qr² + Qg² = Qb² for any integer direction (d, e)
    for d in range(1, 20):
        for e in range(1, 20):
            q = chromogeometric_quadrances(d, e)
            assert q["Qr"] * q["Qr"] + q["Qg"] * q["Qg"] == q["Qb"] * q["Qb"]


def test_G_plus_C_equals_A():
    # Relation certified [133]: G + C = A
    for b in range(1, 10):
        for e in range(1, 10):
            ids = compute_16_identities(b, e)
            assert ids["G"] + ids["C"] == ids["A"]


# ---------------------------------------------------------------------------
# Reasoner full queries
# ---------------------------------------------------------------------------

def test_invariants_all_verified():
    r = QAReasoner(9)
    res = r.invariants(1, 1)
    assert res["all_verified"] is True
    assert res["identities"]["G"] == 5


def test_witness_fibonacci_path_mod_24():
    r = QAReasoner(24)
    # (1,1) → Q → (1,2) → Q → (2,3) → Q → (3,5)
    w = r.witness((1, 1), (3, 5))
    assert w.reachable is True
    assert w.steps == 3
    assert w.generator_trace == ["Q", "Q", "Q"]
    assert w.witness_states == [(1, 1), (1, 2), (2, 3), (3, 5)]


def test_witness_cross_orbit_unreachable():
    r = QAReasoner(9)
    # (1,1) is in cosmos, (9,9) is singularity
    w = r.witness((1, 1), (9, 9))
    assert w.reachable is False
    assert "cross-orbit" in (w.reason_if_unreachable or "")


def test_explain_produces_structured_trace():
    r = QAReasoner(9)
    trace = r.explain(1, 1)
    assert "step_1_canonicalize" in trace
    assert "step_3_classify" in trace
    assert trace["step_3_classify"]["family"] == "cosmos"
    assert trace["all_verified"] is True


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def test_pattern_matcher_fibonacci_seeds():
    pm = PatternMatcher(m=9)
    # All Fibonacci-seed pairs live in cosmos
    res = pm.match([(1, 1), (1, 2), (2, 3), (3, 5)])
    assert res["patterns"]["common_family"] == "cosmos"
    assert res["patterns"]["all_in_same_orbit"] is True


def test_pattern_matcher_mixed_families():
    pm = PatternMatcher(m=9)
    # (1,1) cosmos, (3,3) satellite → no common family
    res = pm.match([(1, 1), (3, 3)])
    assert res["patterns"]["common_family"] is None
    assert sorted(res["patterns"]["all_families_seen"]) == ["cosmos", "satellite"]


def test_pattern_matcher_filter():
    pm = PatternMatcher(m=9)
    # All singularity pairs in mod 9 = {(9, 9)}
    sings = pm.filter(lambda b, e: b == 9 and e == 9)
    assert sings == [(9, 9)]
