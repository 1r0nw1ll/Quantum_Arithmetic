#!/usr/bin/env python3
"""
qa_toroid_sumproduct.py

QA + Toroidal + Sum-Product bridge
Integrates Volk's toroidal geometry with Sum-Product Conjecture via QA arithmetic

Based on volk_grant_sumproduct_qa_mapping.md (2025-11-20)
Implements complete pipeline from finite sets → QA triangles → torus parameters → mod-24/mod-9 resonance

Features:
- Canonical QA tuple (b,e,d,a) = (1,2,3,5) → (C,F,G) and torus params
- For finite set A:
  * compute S = |A+A|, P = |A*A|, D = |A-A|
  * build set-level QA-style triangle (C_set,F_set,G_set)
  * derive toroidal parameters (a_set,b_set,k_set,R_set,r_set)
  * reduce C_set,F_set,G_set into mod-24 + mod-9 (digital root)
  * map to primitive torus knot (m,n)
  * score additive vs multiplicative "torus-likeness"
"""

import math
from dataclasses import dataclass
from itertools import product
from typing import Iterable, List, Set, Tuple

# ---------- QA core structures ----------

@dataclass
class QATriangle:
    """QA-style right triangle (C² + F² = G²)"""
    C: float  # long leg (focal separation)
    F: float  # short leg (altitude)
    G: float  # hypotenuse

@dataclass
class QATorusParams:
    """
    Toroidal parameters derived from a QA triangle

    a : bipolar half-distance between poles (≈ C/2)
    R : major radius
    r : minor radius
    b : relative string radius R/r
    k : relative wavelength (here: C/F as one QA-consistent choice)
    """
    a: float
    R: float
    r: float
    b: float
    k: float

# ---------- 0. Small helpers (mod-9 / mod-24, knot reduction) ----------

def digital_root(n: int) -> int:
    """
    QA-style digital root mod-9
    Returns 0 for n = 0, otherwise 1..9
    """
    if n == 0:
        return 0
    return 1 + ((n - 1) % 9)

def mod24(n: float) -> int:
    """
    Mod-24 reduction for lengths; we round to nearest int first
    You could also floor instead of round if you prefer
    """
    return int(round(n)) % 24

def primitive_torus_knot_from_residues(c24: int, f24: int) -> Tuple[int, int]:
    """
    Map (C_mod24, F_mod24) to a primitive torus-knot type (m,n)

    Rules:
    - interpret 0 residues as 24 (full cycle)
    - then reduce (m0,n0) by gcd to get primitive (m,n)
    """
    m0 = c24 or 24
    n0 = f24 or 24
    g = math.gcd(m0, n0)
    m = m0 // g
    n = n0 // g
    return m, n

# ---------- 1. Concrete QA tuple (1,2,3,5) example ----------

def qa_triangle_from_tuple(b: float, e: float, d: float, a: float) -> QATriangle:
    """
    Use canonical QA definitions to get (C,F,G) from (b,e,d,a)
    Assumes (b,e,d,a) already satisfies your QA constraints

    C = 2ed  (focal separation)
    F = ba   (altitude)
    G = (b²+a²)/2 = e²+d²  (hypotenuse)
    """
    C = 2.0 * e * d  # long leg, distance between ellipse foci
    F = b * a        # short leg
    G = 0.5 * (b**2 + a**2)  # hypotenuse (also = e²+d²)
    return QATriangle(C=C, F=F, G=G)

def torus_from_triangle(tri: QATriangle) -> QATorusParams:
    """
    Map a QA triangle to toroidal parameters (triangle-centric choice)

    - R = G (hypotenuse → major radius)
    - r = F (short leg → minor radius)
    - a = C/2 (half distance between poles)
    - b = R/r (Ginzburg relative string radius)
    - k = C/F (relative wavelength)
    """
    C, F, G = tri.C, tri.F, tri.G
    R = G
    r = F
    a = C / 2.0
    b_param = R / r if r != 0 else float("inf")
    k_param = C / F if F != 0 else float("inf")
    return QATorusParams(a=a, R=R, r=r, b=b_param, k=k_param)

def demo_base_qa_tuple() -> None:
    """
    Print the bipolar/toroidal parameters for the canonical QA tuple (1,2,3,5)

    This is Robert Edward Grant's Logarithmic Right Triangle (LRT):
    - C = 12 (base)
    - F = 5 (altitude)
    - G = 13 (hypotenuse)
    """
    b, e, d, a = 1.0, 2.0, 3.0, 5.0
    tri = qa_triangle_from_tuple(b, e, d, a)
    tor = torus_from_triangle(tri)

    print("=" * 60)
    print("=== Canonical QA tuple (b,e,d,a) = (1,2,3,5) ===")
    print("=== Robert Edward Grant's Logarithmic Right Triangle ===")
    print("=" * 60)
    print(f"C (long leg) = {tri.C}")
    print(f"F (short leg) = {tri.F}")
    print(f"G (hypotenuse) = {tri.G}")
    print()
    print("Pythagorean check: C² + F² = G²")
    print(f"  {tri.C}² + {tri.F}² = {tri.C**2} + {tri.F**2} = {tri.C**2 + tri.F**2}")
    print(f"  G² = {tri.G**2}")
    print(f"  Verified: {abs(tri.C**2 + tri.F**2 - tri.G**2) < 1e-6}")
    print()
    print("Bipolar / toroidal parameters:")
    print(f"  a (half-pole dist) = {tor.a}")
    print(f"  R (major radius) = {tor.R}")
    print(f"  r (minor radius) = {tor.r}")
    print(f"  b = R/r = {tor.b}")
    print(f"  k = C/F = {tor.k}")
    print()

# ---------- 2. Sum-Product statistics for a finite set A ----------

def sum_product_difference_stats(A: Iterable[float]) -> Tuple[int, int, int]:
    """
    Given a finite set/list A, compute cardinalities:

    S = |A + A|  (distinct sums)
    P = |A * A|  (distinct products)
    D = |A - A|  (distinct differences)

    where operations are taken over all ordered pairs (x,y) in A×A
    """
    A_list: List[float] = list(A)
    sums: Set[float] = {x + y for x, y in product(A_list, A_list)}
    prods: Set[float] = {x * y for x, y in product(A_list, A_list)}
    diffs: Set[float] = {x - y for x, y in product(A_list, A_list)}
    return len(sums), len(prods), len(diffs)

def set_triangle_from_SP(S: int, P: int) -> QATriangle:
    """
    Build a QA-style right triangle from (S,P)

    Interpretation:
      C_set = S  (additive 'leg')
      F_set = P  (multiplicative 'leg')
      G_set = √(S² + P²)  (hypotenuse)
    """
    C_set = float(S)
    F_set = float(P)
    G_set = math.sqrt(C_set**2 + F_set**2)
    return QATriangle(C=C_set, F=F_set, G=G_set)

def additive_multiplicative_scores(A: Iterable[float]) -> Tuple[float, float]:
    """
    Simple numerical scores for how "structured" A is additively vs multiplicatively

    Heuristic:
      n = |A|
      S = |A+A|
      P = |A*A|

      additive_struct ~ n²/S      (smaller S → more AP-like structure)
      multiplicative_struct ~ n²/P  (smaller P → more GP-like structure)
    """
    A_list = list(A)
    n = len(A_list) or 1
    S, P, _ = sum_product_difference_stats(A_list)

    norm = n * n
    additive_score = norm / S if S > 0 else 0
    multiplicative_score = norm / P if P > 0 else 0

    return additive_score, multiplicative_score

# ---------- 3. Resonance / (m,n) mapping for set-level triangle ----------

def resonance_from_triangle(tri: QATriangle) -> dict:
    """
    Reduce a QA triangle's legs into mod-24 / mod-9 resonance
    and compute the corresponding primitive torus-knot (m,n)

    Returns a dict with:
    - C24, F24, G24  (mod-24 residues)
    - C9, F9, G9     (mod-9 digital roots)
    - (m,n) knot type
    """
    C, F, G = tri.C, tri.F, tri.G

    # Outer QA resonance (mod-24)
    C24 = mod24(C)
    F24 = mod24(F)
    G24 = mod24(G)

    # Inner QA resonance (mod-9, digital roots)
    C9 = digital_root(int(round(C)))
    F9 = digital_root(int(round(F)))
    G9 = digital_root(int(round(G)))

    # Torus-knot type from outer (C24,F24)
    m, n = primitive_torus_knot_from_residues(C24, F24)

    return {
        "C24": C24, "F24": F24, "G24": G24,
        "C9": C9, "F9": F9, "G9": G9,
        "m": m, "n": n,
    }

def pretty_print_resonance(info: dict) -> None:
    """Nicely print the resonance profile and torus-knot type"""
    C24, F24, G24 = info["C24"], info["F24"], info["G24"]
    C9, F9, G9 = info["C9"], info["F9"], info["G9"]
    m, n = info["m"], info["n"]

    print("Resonance profile (set-level triangle):")
    print(f"  mod-24: C24={C24:2d}, F24={F24:2d}, G24={G24:2d}")
    print(f"  mod-9 : C9 ={C9:2d}, F9 ={F9:2d}, G9 ={G9:2d}")
    print(f"  primitive torus-knot: T({m},{n})")
    print()

# ---------- 4. Full pipeline for a finite set A ----------

def set_torus_from_A(A: Iterable[float], label: str = "") -> Tuple[QATriangle, QATorusParams]:
    """
    Full pipeline for a finite set A:

    1) Compute (S,P,D)
    2) Build the associated set-level QA triangle (C_set,F_set,G_set)
    3) Derive toroidal parameters from that triangle
    4) Compute mod-24 / mod-9 resonance + (m,n) torus-knot
    5) Score additive vs multiplicative torus-likeness

    Returns (triangle, torus_params)
    """
    S, P, D = sum_product_difference_stats(A)
    tri = set_triangle_from_SP(S, P)
    tor = torus_from_triangle(tri)

    print("=" * 60)
    if label:
        print(f">>> {label}")
    print("=== Set-level Sum-Product stats ===")
    print(f"A = {list(A)}")
    print(f"|A+A| = S = {S}  (distinct sums)")
    print(f"|A*A| = P = {P}  (distinct products)")
    print(f"|A-A| = D = {D}  (distinct differences)")
    print()

    print("Induced QA-style triangle:")
    print(f"  C_set (from S) = {tri.C}")
    print(f"  F_set (from P) = {tri.F}")
    print(f"  G_set = √(S² + P²) = {tri.G:.2f}")
    print()

    print("Set-level toroidal parameters:")
    print(f"  a_set = C_set/2 = {tor.a}")
    print(f"  R_set = G_set = {tor.R:.2f}")
    print(f"  r_set = F_set = {tor.r}")
    print(f"  b_set = R_set/r_set = {tor.b:.3f}")
    print(f"  k_set = C_set/F_set = {tor.k:.3f}")
    print()

    # Additive vs multiplicative scores
    add_score, mult_score = additive_multiplicative_scores(A)
    total = add_score + mult_score
    add_frac = add_score / total if total > 0 else 0.5
    mult_frac = mult_score / total if total > 0 else 0.5

    print("Additive vs multiplicative torus-likeness:")
    print(f"  additive_score = {add_score:.4f}  (larger → more AP-like)")
    print(f"  multiplicative_score = {mult_score:.4f}  (larger → more GP-like)")
    print(f"  normalized: additive={add_frac:.3f}, multiplicative={mult_frac:.3f}")

    # Classification
    if add_score > mult_score:
        print(f"  → Classification: MORE AP-LIKE (arithmetic progression)")
    elif mult_score > add_score:
        print(f"  → Classification: MORE GP-LIKE (geometric progression)")
    else:
        print(f"  → Classification: BALANCED")
    print()

    # Resonance + torus knot
    res_info = resonance_from_triangle(tri)
    pretty_print_resonance(res_info)

    return tri, tor

# ---------- 5. Quick demos ----------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("QA TOROID SUM-PRODUCT BRIDGE")
    print("Volk-Grant-QA Integration")
    print("=" * 60 + "\n")

    # Demo 1: canonical QA tuple (1,2,3,5) - Grant's LRT
    demo_base_qa_tuple()

    # Demo 2: AP-like set
    A_ap = [1, 2, 3, 4]
    set_torus_from_A(A_ap, "AP-like set demo: A = [1,2,3,4]")

    # Demo 3: GP-like set
    A_gp = [1, 2, 4, 8]
    set_torus_from_A(A_gp, "GP-like set demo: A = [1,2,4,8]")

    # Demo 4: Fibonacci sequence
    A_fib = [1, 1, 2, 3, 5]
    set_torus_from_A(A_fib, "Fibonacci sequence: A = [1,1,2,3,5]")

    # Demo 5: Primes
    A_prime = [2, 3, 5, 7]
    set_torus_from_A(A_prime, "First 4 primes: A = [2,3,5,7]")

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("  1. Add E8 alignment to set-level triangles")
    print("  2. Visualize (m,n) scatter plot: AP vs GP families")
    print("  3. Test on known Sum-Product extremal sets")
    print("  4. Connect to MCP server for integration")
    print("=" * 60 + "\n")
