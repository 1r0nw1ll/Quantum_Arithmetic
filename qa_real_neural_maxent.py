"""
qa_real_neural_maxent.py - Neural Maximum Entropy with QA constraints

Maximum entropy principle applied to neural activations with QA structure:
- Maximize entropy subject to QA tuple constraints
- Lagrange multipliers ↔ QA invariants (J, K, X)
- Partition function Z encodes harmonic structure
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math
import numpy as np


@dataclass
class QATuple:
    """QA tuple with constraints."""
    b: float
    e: float

    @property
    def d(self) -> float:
        return self.b + self.e

    @property
    def a(self) -> float:
        return self.e + self.d

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.b, self.e, self.d, self.a)

    def invariants(self) -> Dict[str, float]:
        b, e, d, a = self.as_tuple()
        return {
            "J": b * d,
            "K": d * a,
            "X": e * d,
            "C": 2 * e * d,
            "F": b * a,
            "G": e**2 + d**2,
        }


class QAMaxEntModel:
    """Maximum Entropy model with QA constraints.

    P(x) = (1/Z) * exp(-λ·f(x))

    Where f(x) are QA-derived feature functions:
    - f_J: constraint on J = b*d
    - f_K: constraint on K = d*a
    - f_pyth: Pythagorean constraint C² + F² = G²
    """

    def __init__(
        self,
        n_features: int = 4,
        lambda_J: float = 1.0,
        lambda_K: float = 1.0,
        lambda_pyth: float = 0.1,
        beta: float = 1.0,  # Inverse temperature
    ):
        self.n_features = n_features
        self.lambda_J = lambda_J
        self.lambda_K = lambda_K
        self.lambda_pyth = lambda_pyth
        self.beta = beta

    def features_to_qa(self, x: np.ndarray) -> QATuple:
        """Map feature vector to QA tuple."""
        # Use first 2 features for b, e (ensure positive)
        b = max(0.1, float(np.abs(x[0]) + 1.0))
        e = max(0.1, float(np.abs(x[1]) + 1.0))
        return QATuple(b=b, e=e)

    def energy(self, x: np.ndarray) -> float:
        """Compute QA-constrained energy function."""
        qa = self.features_to_qa(x)
        inv = qa.invariants()

        # Target invariant values (could be learned or fixed)
        J_target = 5.0
        K_target = 20.0

        # Energy terms
        E_J = self.lambda_J * (inv["J"] - J_target) ** 2
        E_K = self.lambda_K * (inv["K"] - K_target) ** 2

        # Pythagorean constraint
        pyth_residual = inv["C"]**2 + inv["F"]**2 - inv["G"]**2
        E_pyth = self.lambda_pyth * pyth_residual**2

        return E_J + E_K + E_pyth

    def log_prob(self, x: np.ndarray, Z: float = 1.0) -> float:
        """Log probability under MaxEnt distribution."""
        return -self.beta * self.energy(x) - np.log(Z)

    def sample_mcmc(
        self,
        n_samples: int = 1000,
        burn_in: int = 100,
        step_size: float = 0.1,
    ) -> np.ndarray:
        """Sample from MaxEnt distribution via Metropolis-Hastings."""
        np.random.seed(42)

        samples = []
        x = np.random.randn(self.n_features)

        for i in range(n_samples + burn_in):
            # Propose
            x_prop = x + step_size * np.random.randn(self.n_features)

            # Accept/reject
            dE = self.energy(x_prop) - self.energy(x)
            if dE < 0 or np.random.random() < np.exp(-self.beta * dE):
                x = x_prop

            if i >= burn_in:
                samples.append(x.copy())

        return np.array(samples)

    def estimate_partition(self, samples: np.ndarray) -> float:
        """Estimate log partition function from samples."""
        energies = np.array([self.energy(x) for x in samples])
        # Using importance sampling approximation
        log_Z = -self.beta * np.mean(energies) + np.log(len(samples))
        return log_Z

    def entropy(self, samples: np.ndarray) -> float:
        """Estimate entropy from samples."""
        log_Z = self.estimate_partition(samples)
        energies = np.array([self.energy(x) for x in samples])
        # S = log Z + β<E>
        return log_Z + self.beta * np.mean(energies)


class QANeuralMaxEnt:
    """Neural network with QA MaxEnt regularization.

    Combines standard neural loss with MaxEnt QA constraints:
    L_total = L_task + α * L_maxent

    Where L_maxent encourages activations to follow QA MaxEnt distribution.
    """

    def __init__(
        self,
        input_dim: int = 784,
        hidden_dim: int = 128,
        output_dim: int = 10,
        maxent_weight: float = 0.1,
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.maxent_weight = maxent_weight

        # Initialize weights
        np.random.seed(42)
        self.W1 = np.random.randn(input_dim, hidden_dim) * 0.01
        self.W2 = np.random.randn(hidden_dim, output_dim) * 0.01
        self.b1 = np.zeros(hidden_dim)
        self.b2 = np.zeros(output_dim)

        self.maxent = QAMaxEntModel(n_features=4)

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Forward pass returning (output, hidden activations)."""
        h = np.maximum(0, x @ self.W1 + self.b1)  # ReLU
        out = h @ self.W2 + self.b2
        return out, h

    def hidden_to_qa_features(self, h: np.ndarray) -> np.ndarray:
        """Extract QA features from hidden activations."""
        # Use statistics of hidden layer as features
        return np.array([
            np.mean(h),
            np.std(h),
            np.max(h),
            np.min(h),
        ])

    def maxent_loss(self, h: np.ndarray) -> float:
        """Compute MaxEnt QA loss on hidden activations."""
        qa_features = self.hidden_to_qa_features(h)
        return self.maxent.energy(qa_features)

    def train_step(
        self,
        x: np.ndarray,
        y: np.ndarray,
        lr: float = 0.01,
    ) -> Dict[str, float]:
        """One training step with QA MaxEnt regularization."""
        # Forward
        out, h = self.forward(x)

        # Task loss (cross-entropy for classification)
        exp_out = np.exp(out - np.max(out, axis=-1, keepdims=True))
        probs = exp_out / exp_out.sum(axis=-1, keepdims=True)
        task_loss = -np.mean(np.log(probs[np.arange(len(y)), y] + 1e-8))

        # MaxEnt loss (average over batch)
        maxent_losses = [self.maxent_loss(h[i]) for i in range(len(h))]
        maxent_loss = np.mean(maxent_losses)

        # Total loss
        total_loss = task_loss + self.maxent_weight * maxent_loss

        # Simple gradient descent (would use backprop in real implementation)
        # Here we just add noise to simulate learning
        self.W1 -= lr * np.random.randn(*self.W1.shape) * 0.001
        self.W2 -= lr * np.random.randn(*self.W2.shape) * 0.001

        return {
            "task_loss": task_loss,
            "maxent_loss": maxent_loss,
            "total_loss": total_loss,
        }

    def qa_metrics(self, x: np.ndarray) -> Dict[str, float]:
        """Compute QA metrics on hidden activations."""
        _, h = self.forward(x)
        qa_features = self.hidden_to_qa_features(h[0])
        qa = self.maxent.features_to_qa(qa_features)
        inv = qa.invariants()

        return {
            "qa_tuple": qa.as_tuple(),
            "J": inv["J"],
            "K": inv["K"],
            "energy": self.maxent.energy(qa_features),
        }


def demo():
    """Demo QA Neural MaxEnt."""
    print("=== QA Neural MaxEnt Demo ===")
    print("Maximum entropy neural activations with QA constraints\n")

    # Test MaxEnt model
    print("--- QA MaxEnt Model ---")
    maxent = QAMaxEntModel(lambda_J=1.0, lambda_K=1.0, lambda_pyth=0.1)

    samples = maxent.sample_mcmc(n_samples=500, burn_in=100)
    entropy = maxent.entropy(samples)

    print(f"  Sampled {len(samples)} points from QA MaxEnt distribution")
    print(f"  Estimated entropy: {entropy:.4f}")

    # Analyze sample QA tuples
    qa_tuples = [maxent.features_to_qa(s).as_tuple() for s in samples[:10]]
    print(f"  Sample QA tuples (first 10):")
    for i, qa in enumerate(qa_tuples[:5]):
        print(f"    {i+1}. (b={qa[0]:.2f}, e={qa[1]:.2f}, d={qa[2]:.2f}, a={qa[3]:.2f})")

    # Test Neural MaxEnt
    print("\n--- QA Neural MaxEnt Network ---")
    net = QANeuralMaxEnt(input_dim=100, hidden_dim=32, output_dim=10)

    # Simulate training
    np.random.seed(42)
    for epoch in range(5):
        x = np.random.randn(16, 100)  # Batch of 16
        y = np.random.randint(0, 10, 16)

        losses = net.train_step(x, y, lr=0.01)
        print(f"  Epoch {epoch+1}: task={losses['task_loss']:.4f}, "
              f"maxent={losses['maxent_loss']:.4f}, total={losses['total_loss']:.4f}")

    # Final QA metrics
    x_test = np.random.randn(1, 100)
    metrics = net.qa_metrics(x_test)
    print(f"\n--- Final QA Metrics ---")
    print(f"  QA tuple: {tuple(f'{v:.3f}' for v in metrics['qa_tuple'])}")
    print(f"  J (perigee): {metrics['J']:.3f}")
    print(f"  K (apogee): {metrics['K']:.3f}")
    print(f"  Energy: {metrics['energy']:.4f}")


if __name__ == "__main__":
    demo()
