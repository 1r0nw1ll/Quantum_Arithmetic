"""
QA-Torus-SumProduct Batch Classifier

Classifies number sets as AP-like, GP-like, or Random based on
their torus knot fingerprints T(m,n).

Pipeline: Number Set → (S,P,D) stats → QA Triangle → Torus Knot → Classification
"""

import numpy as np
from math import gcd, sqrt
from typing import List, Dict, Tuple, Set
from itertools import combinations


def compute_sumproduct_stats(A: List[int]) -> Tuple[int, int, int]:
    """Compute |A+A|, |A×A|, |A-A| cardinalities."""
    A_set = set(A)

    # Sumset A+A
    sumset = {a + b for a in A_set for b in A_set}
    S = len(sumset)

    # Product set A×A
    prodset = {a * b for a in A_set for b in A_set}
    P = len(prodset)

    # Difference set A-A
    diffset = {a - b for a in A_set for b in A_set}
    D = len(diffset)

    return S, P, D


def digital_root(n: int) -> int:
    """Compute digital root (iterated digit sum until single digit)."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def primitive_knot(m: int, n: int) -> Tuple[int, int]:
    """Reduce (m, n) to primitive form by dividing by GCD."""
    if m == 0 and n == 0:
        return (0, 0)
    g = gcd(m, n) if (m != 0 or n != 0) else 1
    if g == 0:
        g = 1
    return (m // g, n // g)


def compute_bias(size: int, S: int, P: int) -> Dict[str, float]:
    """Compute additive vs multiplicative bias scores."""
    n_sq = size * size

    add_score = n_sq / S if S > 0 else 0
    mult_score = n_sq / P if P > 0 else 0

    total = add_score + mult_score
    if total == 0:
        return {'add': 0.5, 'mult': 0.5}

    return {
        'add': add_score / total,
        'mult': mult_score / total
    }


def classify_set(A: List[int]) -> Dict:
    """
    Full pipeline: set → fingerprint → classification

    Returns dict with:
        - knot: (m, n) primitive torus knot
        - resonance: (C24, F24, C9, F9) mod resonance values
        - triangle: (C, F, G) QA triangle sides
        - stats: (S, P, D) cardinalities
        - bias: {'add': float, 'mult': float}
        - classification: 'AP' | 'GP' | 'Mixed' | 'Random'
    """
    S, P, D = compute_sumproduct_stats(A)

    # QA Triangle
    C, F = S, P
    G = sqrt(S**2 + P**2)

    # Resonance values
    C24, F24 = C % 24, F % 24
    C9, F9 = digital_root(C), digital_root(F)

    # Primitive torus knot
    m, n = primitive_knot(C24, F24)

    # Bias computation
    bias = compute_bias(len(A), S, P)

    # Classification
    if bias['add'] > 0.55:
        classification = 'AP'
    elif bias['mult'] > 0.55:
        classification = 'GP'
    elif m == n:  # T(1,1) or similar degenerate
        classification = 'Random'
    else:
        classification = 'Mixed'

    return {
        'set': list(A),
        'knot': (m, n),
        'resonance': (C24, F24, C9, F9),
        'triangle': (C, F, round(G, 4)),
        'stats': (S, P, D),
        'bias': bias,
        'classification': classification
    }


def batch_classify(sets: List[List[int]]) -> List[Dict]:
    """Classify multiple number sets."""
    return [classify_set(A) for A in sets]


def generate_test_sets() -> Dict[str, List[int]]:
    """Generate canonical test sets for validation."""
    return {
        'AP_basic': [1, 2, 3, 4],
        'AP_extended': [1, 2, 3, 4, 5, 6],
        'GP_basic': [1, 2, 4, 8],
        'GP_extended': [1, 2, 4, 8, 16],
        'Random': [1, 3, 7, 10],
        'Mixed': [2, 3, 6, 12],
        'Primes': [2, 3, 5, 7],
        'Fibonacci': [1, 2, 3, 5],
        'Fibonacci_ext': [1, 2, 3, 5, 8, 13],
        'Squares': [1, 4, 9, 16],
        'Powers_3': [1, 3, 9, 27],
    }


def print_classification_table(results: List[Dict]):
    """Print formatted classification table."""
    print("\n" + "=" * 90)
    print("QA-TORUS-SUMPRODUCT CLASSIFICATION RESULTS")
    print("=" * 90)
    print(f"{'Set':<20} {'(S,P)':<10} {'Knot T(m,n)':<12} {'Add/Mult Bias':<18} {'Class':<8}")
    print("-" * 90)

    for r in results:
        set_str = str(r['set'])[:18]
        sp = f"({r['stats'][0]},{r['stats'][1]})"
        knot = f"T({r['knot'][0]},{r['knot'][1]})"
        bias = f"{r['bias']['add']*100:.0f}%/{r['bias']['mult']*100:.0f}%"
        print(f"{set_str:<20} {sp:<10} {knot:<12} {bias:<18} {r['classification']:<8}")

    print("=" * 90)


def knot_distribution(results: List[Dict]) -> Dict[Tuple[int,int], int]:
    """Count distribution of torus knots."""
    dist = {}
    for r in results:
        k = r['knot']
        dist[k] = dist.get(k, 0) + 1
    return dict(sorted(dist.items(), key=lambda x: -x[1]))


if __name__ == '__main__':
    # Test with canonical sets
    test_sets = generate_test_sets()

    print("Testing QA-Torus-SumProduct Pipeline")
    print("=" * 50)

    results = []
    for name, A in test_sets.items():
        result = classify_set(A)
        result['name'] = name
        results.append(result)

    print_classification_table(results)

    # Knot distribution
    print("\nTorus Knot Distribution:")
    dist = knot_distribution(results)
    for knot, count in dist.items():
        print(f"  T{knot}: {count} sets")

    # Classification summary
    print("\nClassification Summary:")
    class_counts = {}
    for r in results:
        c = r['classification']
        class_counts[c] = class_counts.get(c, 0) + 1
    for c, n in sorted(class_counts.items()):
        print(f"  {c}: {n} sets")
