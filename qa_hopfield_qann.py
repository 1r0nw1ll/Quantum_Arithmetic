"""
qa_hopfield_qann.py - QA-augmented Hopfield/Associative Memory Network

Connects classical Hopfield networks to QA structure:
- Energy function = QA harmonic potential
- Stored patterns indexed by (b,e,d,a) tuples
- Retrieval dynamics follow HGD (Harmonic Gradient Descent)
- Modern Hopfield attention as QA-weighted softmax

Key insight: Hopfield energy minimization ≈ QA attractor convergence
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import math


@dataclass
class QATuple:
    """QA tuple with constraints d=b+e, a=e+d."""
    b: float
    e: float

    @property
    def d(self) -> float:
        return self.b + self.e

    @property
    def a(self) -> float:
        return self.e + self.d

    def as_array(self) -> np.ndarray:
        return np.array([self.b, self.e, self.d, self.a])

    def invariants(self) -> Dict[str, float]:
        b, e, d, a = self.b, self.e, self.d, self.a
        return {
            "J": b * d,
            "K": d * a,
            "X": e * d,
            "G": e**2 + d**2,
        }


def pattern_to_qa(pattern: np.ndarray) -> QATuple:
    """Map binary/continuous pattern to QA tuple."""
    # Use pattern statistics
    mean_p = float(np.mean(pattern))
    std_p = float(np.std(pattern)) + 0.1
    b = 1.0 + abs(mean_p)
    e = 1.0 + std_p
    return QATuple(b=b, e=e)


class QAHopfieldNetwork:
    """Classical Hopfield network with QA energy augmentation.

    Energy: E(s) = -0.5 * s^T W s + λ * E_QA(s)

    Where E_QA penalizes deviation from QA harmonic structure.
    """

    def __init__(
        self,
        n_neurons: int,
        qa_weight: float = 0.1,
        beta: float = 1.0,
    ):
        self.n_neurons = n_neurons
        self.qa_weight = qa_weight
        self.beta = beta  # Inverse temperature
        self.W = np.zeros((n_neurons, n_neurons))
        self.patterns: List[np.ndarray] = []
        self.pattern_qa: List[QATuple] = []

    def store_pattern(self, pattern: np.ndarray) -> QATuple:
        """Store pattern using Hebbian learning with QA indexing."""
        assert len(pattern) == self.n_neurons
        p = np.sign(pattern)  # Binarize to {-1, +1}

        # Hebbian update
        self.W += np.outer(p, p) / self.n_neurons
        np.fill_diagonal(self.W, 0)  # No self-connections

        # Index by QA tuple
        qa = pattern_to_qa(p)
        self.patterns.append(p.copy())
        self.pattern_qa.append(qa)

        return qa

    def hopfield_energy(self, state: np.ndarray) -> float:
        """Classical Hopfield energy."""
        return -0.5 * state @ self.W @ state

    def qa_energy(self, state: np.ndarray) -> float:
        """QA harmonic energy based on state statistics."""
        qa = pattern_to_qa(state)
        inv = qa.invariants()

        # Target: Pythagorean balance
        # C² + F² = G² where C=2ed, F=ba
        C = 2 * qa.e * qa.d
        F = qa.b * qa.a
        G = inv["G"]
        pyth_residual = (C**2 + F**2 - G**2)**2

        return pyth_residual

    def total_energy(self, state: np.ndarray) -> float:
        """Combined Hopfield + QA energy."""
        return self.hopfield_energy(state) + self.qa_weight * self.qa_energy(state)

    def update_async(self, state: np.ndarray, n_steps: int = 100) -> np.ndarray:
        """Asynchronous update with QA-biased selection."""
        s = state.copy()

        for _ in range(n_steps):
            # QA-biased neuron selection
            qa = pattern_to_qa(s)
            # Bias toward neurons at QA-significant indices
            idx = int(qa.d) % self.n_neurons
            idx = np.random.choice(self.n_neurons)  # Random for now

            # Compute local field
            h = self.W[idx] @ s

            # Update with temperature
            if self.beta * h > 0:
                s[idx] = 1
            elif self.beta * h < 0:
                s[idx] = -1
            else:
                s[idx] = np.sign(np.random.randn())

        return s

    def retrieve(
        self,
        probe: np.ndarray,
        max_iters: int = 100,
        tol: float = 1e-6,
    ) -> Tuple[np.ndarray, Dict]:
        """Retrieve pattern from probe with QA tracking."""
        s = np.sign(probe)
        energies = [self.total_energy(s)]
        qa_trace = [pattern_to_qa(s)]

        for i in range(max_iters):
            s_new = self.update_async(s, n_steps=self.n_neurons)

            e_new = self.total_energy(s_new)
            energies.append(e_new)
            qa_trace.append(pattern_to_qa(s_new))

            if np.allclose(s, s_new):
                break
            s = s_new

        return s, {
            "energies": energies,
            "qa_trace": qa_trace,
            "iterations": i + 1,
            "final_qa": qa_trace[-1],
        }

    def find_nearest_pattern(self, state: np.ndarray) -> Tuple[int, float]:
        """Find stored pattern closest to state."""
        overlaps = [np.dot(state, p) / self.n_neurons for p in self.patterns]
        idx = int(np.argmax(overlaps))
        return idx, overlaps[idx]


class ModernQAHopfield:
    """Modern Hopfield network with QA-weighted attention.

    Attention: softmax(β * X^T * Ξ) where β incorporates QA weighting.

    Connects to Transformer attention via:
    - Queries = current state QA projection
    - Keys = stored pattern QA indices
    - Values = stored patterns
    """

    def __init__(
        self,
        dim: int,
        n_heads: int = 4,
        qa_temperature: float = 1.0,
    ):
        self.dim = dim
        self.n_heads = n_heads
        self.qa_temperature = qa_temperature
        self.patterns: List[np.ndarray] = []
        self.pattern_qa: List[QATuple] = []

    def store(self, pattern: np.ndarray) -> None:
        """Store continuous pattern."""
        self.patterns.append(pattern.copy())
        self.pattern_qa.append(pattern_to_qa(pattern))

    def qa_similarity(self, qa1: QATuple, qa2: QATuple) -> float:
        """QA-space similarity between two tuples."""
        v1 = qa1.as_array()
        v2 = qa2.as_array()
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8))

    def retrieve(self, query: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """Retrieve via QA-weighted softmax attention."""
        if not self.patterns:
            return query, {"attention": []}

        query_qa = pattern_to_qa(query)

        # Compute attention weights
        # Standard: dot product similarity
        # QA-augmented: blend with QA tuple similarity
        scores = []
        for i, (p, p_qa) in enumerate(zip(self.patterns, self.pattern_qa)):
            # Content similarity
            content_sim = np.dot(query, p) / (np.linalg.norm(query) * np.linalg.norm(p) + 1e-8)
            # QA similarity
            qa_sim = self.qa_similarity(query_qa, p_qa)
            # Combined
            score = content_sim + self.qa_temperature * qa_sim
            scores.append(score)

        # Softmax
        scores = np.array(scores)
        exp_scores = np.exp(scores - np.max(scores))
        attention = exp_scores / (exp_scores.sum() + 1e-8)

        # Weighted retrieval
        result = sum(a * p for a, p in zip(attention, self.patterns))

        return result, {
            "attention": attention.tolist(),
            "query_qa": query_qa,
            "top_pattern_idx": int(np.argmax(attention)),
        }


def demo():
    """Demo QA Hopfield networks."""
    print("=== QA Hopfield Network Demo ===\n")

    np.random.seed(42)
    n = 100

    # Classical Hopfield with QA
    print("--- Classical QA-Hopfield ---")
    hopfield = QAHopfieldNetwork(n_neurons=n, qa_weight=0.1)

    # Store patterns
    patterns = [np.sign(np.random.randn(n)) for _ in range(5)]
    for i, p in enumerate(patterns):
        qa = hopfield.store_pattern(p)
        print(f"  Pattern {i}: QA=(b={qa.b:.2f}, e={qa.e:.2f}, d={qa.d:.2f}, a={qa.a:.2f})")

    # Retrieve from noisy probe
    probe = patterns[2].copy()
    noise_idx = np.random.choice(n, size=20, replace=False)
    probe[noise_idx] *= -1  # Flip 20% of bits

    retrieved, info = hopfield.retrieve(probe, max_iters=50)
    idx, overlap = hopfield.find_nearest_pattern(retrieved)

    print(f"\n  Retrieval from 20% corrupted pattern 2:")
    print(f"    Iterations: {info['iterations']}")
    print(f"    Matched pattern: {idx} (overlap={overlap:.3f})")
    print(f"    Final QA: (b={info['final_qa'].b:.2f}, e={info['final_qa'].e:.2f})")

    # Modern Hopfield with QA attention
    print("\n--- Modern QA-Hopfield (Attention) ---")
    modern = ModernQAHopfield(dim=64, qa_temperature=0.5)

    # Store continuous patterns
    for i in range(5):
        p = np.random.randn(64)
        modern.store(p)
        qa = modern.pattern_qa[-1]
        print(f"  Pattern {i}: QA=(b={qa.b:.2f}, e={qa.e:.2f})")

    # Query
    query = modern.patterns[3] + 0.3 * np.random.randn(64)
    result, info = modern.retrieve(query)

    print(f"\n  Query (noisy pattern 3):")
    print(f"    Top match: pattern {info['top_pattern_idx']}")
    print(f"    Attention: {[f'{a:.3f}' for a in info['attention']]}")
    print(f"    Query QA: (b={info['query_qa'].b:.2f}, e={info['query_qa'].e:.2f})")


if __name__ == "__main__":
    demo()
