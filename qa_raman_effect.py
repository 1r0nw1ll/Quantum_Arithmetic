"""
qa_raman_effect.py

QA mapping of Raman inelastic scattering (Stokes / Anti-Stokes) using
canonical QA tuples and invariants. Focuses on:

- Tuple closure: d = b + e, a = e + d = b + 2e
- Triangle/invariant set: C, F, G, J, X, K
- Simple Δe transitions for Stokes (+) and Anti-Stokes (−)
- Discrete fingerprints: mod-9 digital roots and mod-24 residues

This module is self-contained and does not assume external datasets.
It may optionally leverage the Rust extension (qa_lab_rs) if available
for mod-9/mod-24 batching, but includes pure-Python fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


# -----------------------------
# Utilities (pure-Python)
# -----------------------------

def _digital_root_mod9(n: int) -> int:
    if n == 0:
        return 9
    n = abs(n)
    r = n % 9
    return r if r != 0 else 9


def _mod24(n: int) -> int:
    r = n % 24
    return r


# -----------------------------
# Core QA structures
# -----------------------------

@dataclass(frozen=True)
class QATuple:
    b: float
    e: float
    d: float
    a: float

    @staticmethod
    def from_b_e(b: float, e: float) -> "QATuple":
        d = b + e
        a = e + d
        return QATuple(b=b, e=e, d=d, a=a)

    def is_valid(self, tol: float = 1e-9) -> bool:
        return abs(self.d - (self.b + self.e)) <= tol and abs(self.a - (self.e + self.d)) <= tol


@dataclass(frozen=True)
class QATriangle:
    C: float  # long leg (frequency gap) = 2ed
    F: float  # short leg (internal energy) = ba
    G: float  # hypotenuse (total vibrational magnitude) = e^2 + d^2
    J: float  # perigee = b d
    X: float  # half foci distance = d e
    K: float  # apogee = d a


def to_triangle(t: QATuple) -> QATriangle:
    C = 2.0 * t.e * t.d
    F = t.b * t.a
    G = t.e * t.e + t.d * t.d
    J = t.b * t.d
    X = t.d * t.e
    K = t.d * t.a
    return QATriangle(C=C, F=F, G=G, J=J, X=X, K=K)


# -----------------------------
# Stokes / Anti-Stokes transitions
# -----------------------------

def stokes(t: QATuple, delta_e: float = 1.0) -> QATuple:
    """Stokes shift: photon loses energy; molecule gains → e → e + Δe."""
    return QATuple.from_b_e(t.b, t.e + delta_e)


def antistokes(t: QATuple, delta_e: float = 1.0) -> QATuple:
    """Anti-Stokes shift: photon gains energy; molecule loses → e → e - Δe."""
    e_new = t.e - delta_e
    if e_new <= 0:
        raise ValueError("Anti-Stokes would drive e <= 0; not allowed in this simple model.")
    return QATuple.from_b_e(t.b, e_new)


def relative_shift(parent: QATuple, child: QATuple) -> float:
    """Relative Raman shift using C as a proxy: (C_child - C_parent) / C_parent."""
    p = to_triangle(parent)
    c = to_triangle(child)
    if abs(p.C) < 1e-12:
        raise ZeroDivisionError("Parent triangle has C=0; cannot compute relative shift.")
    return (c.C - p.C) / p.C


# -----------------------------
# Discrete fingerprints
# -----------------------------

def signatures(t: QATuple) -> Dict[str, Tuple[int, ...]]:
    tri = to_triangle(t)
    # Round to nearest int for discrete bins
    b, e, d, a = int(round(t.b)), int(round(t.e)), int(round(t.d)), int(round(t.a))
    C, F, G = int(round(tri.C)), int(round(tri.F)), int(round(tri.G))

    beda_dr = (
        _digital_root_mod9(b),
        _digital_root_mod9(e),
        _digital_root_mod9(d),
        _digital_root_mod9(a),
    )
    cfg_dr = (
        _digital_root_mod9(C),
        _digital_root_mod9(F),
        _digital_root_mod9(G),
    )
    beda_m24 = (_mod24(b), _mod24(e), _mod24(d), _mod24(a))
    cfg_m24 = (_mod24(C), _mod24(F), _mod24(G))
    torus_mn = (cfg_m24[0], cfg_m24[1])  # (m, n) := (C mod 24, F mod 24)

    return {
        "mod9_beda": beda_dr,
        "mod9_cfg": cfg_dr,
        "mod24_beda": beda_m24,
        "mod24_cfg": cfg_m24,
        "torus_mn": torus_mn,
    }


# -----------------------------
# Convenience presets
# -----------------------------

def preset_crystals() -> Dict[str, QATuple]:
    """Simple QA seeds for a few crystals (geometry seeds, not physical fits)."""
    return {
        "Diamond": QATuple.from_b_e(1.0, 1.0),
        "Graphene": QATuple.from_b_e(1.0, 2.0),
        "Quartz": QATuple.from_b_e(2.0, 3.0),
        "Silicon": QATuple.from_b_e(1.0, 3.0),
    }


def demo() -> None:
    """Lightweight demo printing tuples, triangles, signatures, and sidebands."""
    print("QA Raman mapping demo (relative, C-based)")
    for name, tau in preset_crystals().items():
        tri = to_triangle(tau)
        sig = signatures(tau)
        print("=" * 40)
        print(f"Crystal: {name}")
        print(f"  Tuple (b,e,d,a) = ({tau.b:.3f}, {tau.e:.3f}, {tau.d:.3f}, {tau.a:.3f})")
        print(f"  Triangle: C={tri.C:.3f}, F={tri.F:.3f}, G={tri.G:.3f}; J={tri.J:.3f}, X={tri.X:.3f}, K={tri.K:.3f}")
        print(f"  mod-9 beda={sig['mod9_beda']}, cfg={sig['mod9_cfg']}")
        print(f"  mod-24 beda={sig['mod24_beda']}, cfg={sig['mod24_cfg']}, torus(m,n)={sig['torus_mn']}")

        # Sidebands: Δe = -1, +1, +2
        for de in (-1.0, 1.0, 2.0):
            try:
                child = antistokes(tau, -de) if de < 0 else stokes(tau, de)
                rel = relative_shift(tau, child)
                tag = "Anti-Stokes" if de < 0 else "Stokes"
                print(f"    Δe={de:+.0f} {tag:>11}: C={to_triangle(child).C:.3f}, rel_shift={rel:+.4f}")
            except ValueError as ex:
                print(f"    Δe={de:+.0f} skipped: {ex}")


if __name__ == "__main__":
    demo()

