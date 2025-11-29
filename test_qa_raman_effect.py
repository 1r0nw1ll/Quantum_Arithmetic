import math

from qa_raman_effect import (
    QATuple,
    to_triangle,
    stokes,
    antistokes,
    relative_shift,
    signatures,
    preset_crystals,
)


def test_closure_and_triangle_diamond():
    # Diamond seed: (b,e) = (1,1) → (1,1,2,3)
    t = QATuple.from_b_e(1.0, 1.0)
    assert t.is_valid()
    assert (t.b, t.e, t.d, t.a) == (1.0, 1.0, 2.0, 3.0)

    tri = to_triangle(t)
    # C = 2ed = 4
    assert tri.C == 4.0
    # F = ba = 3
    assert tri.F == 3.0
    # G = e^2 + d^2 = 1 + 4 = 5
    assert tri.G == 5.0
    # J = b d = 2; X = d e = 2; K = d a = 6
    assert (tri.J, tri.X, tri.K) == (2.0, 2.0, 6.0)


def test_stokes_antistokes_relative_shift():
    # Base: Graphene-like seed (1,2,3,5)
    base = QATuple.from_b_e(1.0, 2.0)
    tri0 = to_triangle(base)
    assert tri0.C == 12.0

    # Stokes +1: (1,3,4,7) → C=2*3*4=24 → relative +1.0
    s1 = stokes(base, 1.0)
    tri_s1 = to_triangle(s1)
    assert tri_s1.C == 24.0
    assert math.isclose(relative_shift(base, s1), 1.0, rel_tol=1e-9)

    # Anti-Stokes −1: (1,1,2,3) → C=4 → relative (4-12)/12 = -2/3
    a1 = antistokes(base, 1.0)
    tri_a1 = to_triangle(a1)
    assert tri_a1.C == 4.0
    assert math.isclose(relative_shift(base, a1), -2.0 / 3.0, rel_tol=1e-9)


def test_signatures_mods():
    t = QATuple.from_b_e(1.0, 1.0)  # (1,1,2,3)
    sig = signatures(t)
    assert sig["mod24_beda"] == (1, 1, 2, 3)
    assert sig["mod9_beda"] == (1, 1, 2, 3)

    # C=4,F=3,G=5 → mod-24 same; mod-9 digital roots equal to the numbers themselves here
    assert sig["mod24_cfg"] == (4, 3, 5)
    assert sig["mod9_cfg"] == (4, 3, 5)
    # torus (m, n) := (C mod 24, F mod 24)
    assert sig["torus_mn"] == (4, 3)


def test_preset_crystals_validity():
    for name, tau in preset_crystals().items():
        assert tau.is_valid(), f"Preset {name} must satisfy QA closure"

