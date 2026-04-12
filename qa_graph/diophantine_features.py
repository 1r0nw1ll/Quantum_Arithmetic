"""QA Diophantine Feature Extension — Eisenstein norm, family, identities.

Supplements the 84 invariants in feature_map.py with Diophantine properties
from certs [133], [183], [213], [214]:

    FROM [214] Norm-Flip:
      eisenstein_norm:     f(b,e) = b*b + b*e - e*e (integer)
      norm_mod9:           f(b,e) % 9
      norm_sign:           +1, -1, or 0
      family_label:        Fibonacci/Lucas/Phibonacci/null (from norm_mod9)
      family_code:         1=Fibonacci, 2=Lucas, 3=Phibonacci, 0=null

    FROM [133] Eisenstein:
      eisenstein_identity_error: |F*F - F*W + W*W - Z*Z| (should be 0)

    FROM [183] Eisenstein Crystal:
      crystal_identity_error: |Z - Y - J| (should be 0, where J=b*d)

    FROM [213] Causal DAG:
      pair_invertible:     1 if gcd(2, m) == 1 for this m; else 0
      inradius:            b * e (= r for the Pythagorean right triangle)

    Pythagorean triple check:
      pyth_C, pyth_F, pyth_G: the triple legs
      pyth_is_primitive:   gcd(C, F) == 2 (primitive Pythagorean triples have gcd=2)

All integer-only. No floats in QA state. S1-compliant (b*b not b**2).
"""

QA_COMPLIANCE = "observer=diophantine_feature_extractor, state_alphabet=qa_integer_invariants, tier=algebraic_identity_features"

from math import gcd
from typing import Dict, List, Tuple

# Family classification table from [214]
NORM_MOD9_TO_FAMILY = {
    1: ("Fibonacci", 1),
    8: ("Fibonacci", 1),
    4: ("Lucas", 2),
    5: ("Lucas", 2),
    2: ("Phibonacci", 3),
    7: ("Phibonacci", 3),
    0: ("null", 0),
    3: ("other", 4),
    6: ("other", 4),
}


def diophantine_features(b: int, e: int) -> Dict[str, float]:
    """Compute the full Diophantine feature vector from (b, e).

    Returns dict of float-valued features (for numpy compatibility).
    All QA quantities are computed as integers first; float conversion is
    observer-layer only.
    """
    # A2: derived coordinates
    d = b + e
    a = b + 2 * e

    # Core elements (S1: b*b not b**2)
    B = b * b
    E = e * e
    D = d * d
    A = a * a
    C = 2 * e * d
    F = a * b
    G = D + E
    J = b * d
    K = d * a
    W = d * (e + a)  # = X + K
    Y = A - D
    Z = E + K  # = e*e + d*a

    # [214] Eisenstein norm
    eisenstein = B + b * e - E  # = b*b + b*e - e*e
    norm_mod9 = eisenstein % 9
    norm_sign = 1 if eisenstein > 0 else (-1 if eisenstein < 0 else 0)
    family_name, family_code = NORM_MOD9_TO_FAMILY.get(norm_mod9, ("unknown", -1))

    # [133] Eisenstein identity: F*F - F*W + W*W == Z*Z
    eis_lhs = F * F - F * W + W * W
    eis_rhs = Z * Z
    eisenstein_identity_error = abs(eis_lhs - eis_rhs)

    # [183] Crystal identity: Z - Y == J (= b*d)
    crystal_identity_error = abs(Z - Y - J)

    # Pythagorean triple (C, F, G)
    pyth_error = abs(C * C + F * F - G * G)
    pyth_gcd = gcd(C, F)
    pyth_is_primitive = 1 if pyth_gcd == 2 else 0

    # [213] Pair invertibility: all 6 pairs bijective iff gcd(2, m) == 1
    # For raw integers, gcd(2, gcd(b, e)) indicates if the (b,a) pair
    # has a unique solution
    pair_gcd = gcd(2, gcd(b, e))
    pair_invertible = 1 if pair_gcd == 1 else 0

    # Inradius of the Pythagorean right triangle: r = b * e
    inradius = b * e

    # Divisibility features
    d_divides_W = 1 if W % d == 0 else 0  # always true: W = d*(e+a)
    b_divides_F = 1 if F % b == 0 else 0  # always true: F = a*b
    e_divides_C = 1 if C % e == 0 else 0  # always true: C = 2*e*d

    return {
        # [214] Norm-flip features
        "eisenstein_norm": float(eisenstein),
        "norm_mod9": float(norm_mod9),
        "norm_sign": float(norm_sign),
        "family_code": float(family_code),

        # [133] Eisenstein identity
        "eisenstein_identity_error": float(eisenstein_identity_error),

        # [183] Crystal identity
        "crystal_identity_error": float(crystal_identity_error),

        # Pythagorean triple
        "pyth_error": float(pyth_error),
        "pyth_is_primitive": float(pyth_is_primitive),
        "pyth_gcd_CF": float(pyth_gcd),

        # [213] Pair invertibility
        "pair_invertible": float(pair_invertible),

        # Inradius
        "inradius": float(inradius),

        # Divisibility (diagnostic — should all be 1)
        "d_divides_W": float(d_divides_W),
        "b_divides_F": float(b_divides_F),
        "e_divides_C": float(e_divides_C),

        # Ratios involving Diophantine quantities
        "norm_over_inradius": float(eisenstein) / float(inradius) if inradius != 0 else 0.0,
        "F_over_G": float(F) / float(G) if G != 0 else 0.0,
        "C_over_F": float(C) / float(F) if F != 0 else 0.0,
        "J_over_Z": float(J) / float(Z) if Z != 0 else 0.0,
    }


DIOPHANTINE_FEATURE_NAMES = sorted(diophantine_features(1, 1).keys())
N_DIOPHANTINE = len(DIOPHANTINE_FEATURE_NAMES)


def diophantine_feature_vector(b: int, e: int) -> Tuple[List[float], List[str]]:
    """Return (vector, names) in a consistent order for numpy stacking."""
    feats = diophantine_features(b, e)
    names = DIOPHANTINE_FEATURE_NAMES
    return [feats[n] for n in names], names


def full_qa_feature_vector(b: int, e: int) -> Tuple[List[float], List[str]]:
    """Concatenate qa83 + diophantine features into one vector.

    Returns (vector, names) where len = 84 + N_DIOPHANTINE.
    """
    from qa_graph.feature_map import compute_qa_invariants

    qa_inv = compute_qa_invariants(float(b), float(e))
    qa_names = sorted(qa_inv.keys())
    qa_vec = [float(qa_inv[n]) for n in qa_names]

    dio_vec, dio_names = diophantine_feature_vector(b, e)

    return qa_vec + dio_vec, qa_names + dio_names


__all__ = [
    "diophantine_features",
    "diophantine_feature_vector",
    "full_qa_feature_vector",
    "DIOPHANTINE_FEATURE_NAMES",
    "N_DIOPHANTINE",
    "NORM_MOD9_TO_FAMILY",
]
