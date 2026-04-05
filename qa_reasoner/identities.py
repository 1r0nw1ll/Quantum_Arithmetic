"""
The 16 QA identities + chromogeometric quadrances.

All computations are exact integer arithmetic. No floats. Per axiom S1 we use
b*b, never b**2. Per A1 we assume (b, e) live in {1..m} or unbounded positive ints.

Canonical identities (from elements.txt, certified in cert [133]):
    A = a*a          D = d*d          B = b*b          E = e*e
    C = 2*d*e        F = a*b  (semi-latus; also F = d*d - e*e for direction d,e)
    G = d*d + e*e
    H = C + F        I = C - F
    J = b*d          K = a*d
    L = C*F / 12     (integer only when C*F divisible by 12; 12-folding form)
    X = e*d          (= C/2)
    W = d*(e + a) = X + K
    Y = A - D = a*a - d*d
    Z = E + K

Key relations:
    G = (A + B) / 2
    G + C = A
    G - C = B
    A - B = 2*C
    C*C + F*F = G*G           (chromogeometry theorem)
    F*F - F*W + W*W = Z*Z     (Eisenstein-norm identity)
    Y*Y - Y*W + W*W = Z*Z

Chromogeometric quadrances (Wildberger) for direction vector (d, e):
    Qr = d*d - e*e    (red; F above)
    Qg = 2*d*e        (green; C above)
    Qb = d*d + e*e    (blue; G above)
    Qr*Qr + Qg*Qg = Qb*Qb
"""

from __future__ import annotations

from typing import Dict


def compute_16_identities(b: int, e: int) -> Dict[str, int]:
    """Return the 16 canonical QA identities for the pair (b, e).

    All values are exact integers. Uses b*b form only (S1 compliance).
    """
    d = b + e
    a = b + 2 * e

    A = a * a
    B = b * b
    D = d * d
    E = e * e

    C = 2 * d * e
    F = a * b  # semi-latus; equals (d*d - e*e) for direction (d,e) but NOT for (b,e)
    G = d * d + e * e

    H = C + F
    I = C - F

    J = b * d
    K = a * d
    X = e * d
    W = d * (e + a)  # = X + K
    Y = A - D
    Z = E + K

    # L only integer when C*F divisible by 12
    CF = C * F
    L: int | None = CF // 12 if CF % 12 == 0 else None

    return {
        "A": A, "B": B, "C": C, "D": D, "E": E, "F": F, "G": G,
        "H": H, "I": I, "J": J, "K": K, "L": L, "X": X, "W": W,
        "Y": Y, "Z": Z,
    }


def chromogeometric_quadrances(d: int, e: int) -> Dict[str, int]:
    """Wildberger's three chromogeometric quadrances for direction (d, e).

    Qr = d*d - e*e  (red, Euclidean-complement)
    Qg = 2*d*e      (green, hyperbolic-complement)
    Qb = d*d + e*e  (blue, Euclidean)

    Satisfies Qr*Qr + Qg*Qg = Qb*Qb exactly on integer pairs.
    """
    Qr = d * d - e * e
    Qg = 2 * d * e
    Qb = d * d + e * e
    return {"Qr": Qr, "Qg": Qg, "Qb": Qb}


def verify_identities(b: int, e: int) -> Dict[str, bool]:
    """Verify the structural relations that must hold for any (b, e).

    Returns a dict of relation_name -> bool. All must be True for valid integers.
    """
    ids = compute_16_identities(b, e)
    A, B, C, D, E, F, G = ids["A"], ids["B"], ids["C"], ids["D"], ids["E"], ids["F"], ids["G"]
    H, I, W, Y, Z = ids["H"], ids["I"], ids["W"], ids["Y"], ids["Z"]

    d = b + e
    qq = chromogeometric_quadrances(d, e)

    return {
        "G = (A+B)/2": 2 * G == A + B,
        "G + C = A":   G + C == A,
        "G - C = B":   G - C == B,
        "A - B = 2C":  A - B == 2 * C,
        "H = C + F":   H == C + F,
        "I = C - F":   I == C - F,
        # Chromogeometry: Qr*Qr + Qg*Qg = Qb*Qb (on direction (d, e))
        "Qr² + Qg² = Qb²": qq["Qr"] * qq["Qr"] + qq["Qg"] * qq["Qg"] == qq["Qb"] * qq["Qb"],
        # Eisenstein-norm identities (certified [133])
        "F² - FW + W² = Z²": F * F - F * W + W * W == Z * Z,
        "Y² - YW + W² = Z²": Y * Y - Y * W + W * W == Z * Z,
    }
