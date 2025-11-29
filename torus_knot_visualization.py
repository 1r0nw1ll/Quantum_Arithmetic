"""
Torus Knot Visualization for QA-SumProduct Classification

Generates scatter plot of T(m,n) fingerprints across set types.
"""

import numpy as np
import matplotlib.pyplot as plt
from qa_toroid_sumproduct_batch import classify_set, batch_classify
from typing import List, Dict
import random


def generate_ap_sets(n: int = 20) -> List[List[int]]:
    """Generate arithmetic progression sets."""
    sets = []
    for _ in range(n):
        start = random.randint(1, 10)
        diff = random.randint(1, 5)
        length = random.randint(4, 8)
        sets.append([start + i * diff for i in range(length)])
    return sets


def generate_gp_sets(n: int = 20) -> List[List[int]]:
    """Generate geometric progression sets."""
    sets = []
    for _ in range(n):
        start = random.randint(1, 5)
        ratio = random.randint(2, 3)
        length = random.randint(4, 6)
        s = [start * (ratio ** i) for i in range(length)]
        if max(s) < 10000:
            sets.append(s)
    return sets[:n]


def generate_random_sets(n: int = 20) -> List[List[int]]:
    """Generate random sets."""
    sets = []
    for _ in range(n):
        length = random.randint(4, 8)
        sets.append(sorted(random.sample(range(1, 50), length)))
    return sets


def generate_fibonacci_like(n: int = 20) -> List[List[int]]:
    """Generate Fibonacci-like sets."""
    sets = []
    for _ in range(n):
        a, b = random.randint(1, 5), random.randint(1, 5)
        seq = [a, b]
        for _ in range(random.randint(3, 6)):
            seq.append(seq[-1] + seq[-2])
        sets.append(seq)
    return sets


def generate_prime_sets(n: int = 20) -> List[List[int]]:
    """Generate sets of consecutive primes."""
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    sets = []
    for _ in range(n):
        start = random.randint(0, 8)
        length = random.randint(4, 6)
        sets.append(primes[start:start+length])
    return sets


def visualize_torus_knots():
    """Create visualization of torus knot fingerprints."""
    random.seed(42)

    # Generate sets
    ap_sets = generate_ap_sets(30)
    gp_sets = generate_gp_sets(30)
    random_sets = generate_random_sets(30)
    fib_sets = generate_fibonacci_like(30)
    prime_sets = generate_prime_sets(30)

    # Classify all
    all_data = {
        'AP': batch_classify(ap_sets),
        'GP': batch_classify(gp_sets),
        'Random': batch_classify(random_sets),
        'Fibonacci': batch_classify(fib_sets),
        'Primes': batch_classify(prime_sets)
    }

    # Extract (m, n) coordinates
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Torus knot scatter
    ax1 = axes[0]
    colors = {'AP': 'blue', 'GP': 'red', 'Random': 'gray', 'Fibonacci': 'green', 'Primes': 'orange'}
    markers = {'AP': 'o', 'GP': 's', 'Random': 'x', 'Fibonacci': '^', 'Primes': 'd'}

    for set_type, results in all_data.items():
        m_vals = [r['knot'][0] for r in results]
        n_vals = [r['knot'][1] for r in results]
        # Add jitter for visibility
        m_jitter = np.array(m_vals) + np.random.normal(0, 0.15, len(m_vals))
        n_jitter = np.array(n_vals) + np.random.normal(0, 0.15, len(n_vals))
        ax1.scatter(m_jitter, n_jitter, c=colors[set_type], marker=markers[set_type],
                   label=set_type, alpha=0.7, s=60)

    ax1.set_xlabel('m (Torus Knot)')
    ax1.set_ylabel('n (Torus Knot)')
    ax1.set_title('Torus Knot T(m,n) Fingerprints by Set Type')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-1, 25)
    ax1.set_ylim(-1, 25)
    ax1.plot([0, 24], [0, 24], 'k--', alpha=0.3, label='m=n line')

    # Plot 2: Add/Mult bias scatter
    ax2 = axes[1]
    for set_type, results in all_data.items():
        add_bias = [r['bias']['add'] for r in results]
        mult_bias = [r['bias']['mult'] for r in results]
        ax2.scatter(add_bias, mult_bias, c=colors[set_type], marker=markers[set_type],
                   label=set_type, alpha=0.7, s=60)

    ax2.set_xlabel('Additive Bias')
    ax2.set_ylabel('Multiplicative Bias')
    ax2.set_title('Add/Mult Bias Distribution by Set Type')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.plot([0, 1], [1, 0], 'k--', alpha=0.3)
    ax2.set_xlim(0.3, 0.7)
    ax2.set_ylim(0.3, 0.7)

    plt.tight_layout()
    plt.savefig('/home/player2/signal_experiments/qa_lab/torus_knot_visualization.png', dpi=150)
    plt.close()

    print("Visualization saved to torus_knot_visualization.png")

    # Print statistics
    print("\n" + "=" * 60)
    print("TORUS KNOT STATISTICS")
    print("=" * 60)

    for set_type, results in all_data.items():
        knots = [r['knot'] for r in results]
        knot_counts = {}
        for k in knots:
            knot_counts[k] = knot_counts.get(k, 0) + 1

        top_knots = sorted(knot_counts.items(), key=lambda x: -x[1])[:3]
        avg_add = np.mean([r['bias']['add'] for r in results])

        print(f"\n{set_type}:")
        print(f"  Avg additive bias: {avg_add:.2%}")
        print(f"  Top knots: {top_knots}")


if __name__ == '__main__':
    visualize_torus_knots()
