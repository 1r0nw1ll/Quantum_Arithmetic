"""
qa_neural_rg.py - Renormalization Group flow with QA tracking

Models neural network training as RG flow:
- Layer depth = RG scale
- Weight statistics → QA tuple (b,e,d,a)
- Loss landscape → QA harmonic potential
- Fixed points = QA resonance states
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import math
import numpy as np


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

    def pythagorean_residual(self) -> float:
        inv = self.invariants()
        return abs(inv["C"]**2 + inv["F"]**2 - inv["G"]**2)


@dataclass
class RGFlowState:
    """State at one RG scale (layer/epoch)."""
    scale: int  # Layer depth or epoch
    qa: QATuple
    loss: float
    grad_norm: float
    weight_stats: Dict[str, float] = field(default_factory=dict)

    def harmonic_score(self) -> float:
        """QA harmonic quality metric."""
        pyth = self.qa.pythagorean_residual()
        inv = self.qa.invariants()
        norm = max(inv["G"]**2, 1.0)
        return 1.0 / (1.0 + pyth / norm)


class QARGTracker:
    """Track RG flow via QA tuple evolution.

    Maps neural network statistics to QA space:
    - b ∝ weight mean
    - e ∝ weight std
    - Loss → QA potential energy
    - Gradient → QA force
    """

    def __init__(
        self,
        b_scale: float = 1.0,
        e_scale: float = 1.0,
        offset: float = 1.0,  # Ensure positivity
    ):
        self.b_scale = b_scale
        self.e_scale = e_scale
        self.offset = offset
        self.history: List[RGFlowState] = []

    def weights_to_qa(
        self,
        weights: np.ndarray,
    ) -> QATuple:
        """Map weight statistics to QA tuple."""
        mean_w = float(np.mean(np.abs(weights)))
        std_w = float(np.std(weights))

        b = self.offset + self.b_scale * mean_w
        e = self.offset + self.e_scale * std_w

        return QATuple(b=b, e=e)

    def record_state(
        self,
        scale: int,
        weights: np.ndarray,
        loss: float,
        grad_norm: float,
    ) -> RGFlowState:
        """Record RG state from network statistics."""
        qa = self.weights_to_qa(weights)

        state = RGFlowState(
            scale=scale,
            qa=qa,
            loss=loss,
            grad_norm=grad_norm,
            weight_stats={
                "mean": float(np.mean(weights)),
                "std": float(np.std(weights)),
                "min": float(np.min(weights)),
                "max": float(np.max(weights)),
            }
        )
        self.history.append(state)
        return state

    def compute_beta_function(self) -> List[Dict[str, float]]:
        """Compute RG beta function (derivative of QA w.r.t. scale).

        β(b,e) = d(b,e)/d(scale)

        Fixed points where β ≈ 0 correspond to QA resonance.
        """
        if len(self.history) < 2:
            return []

        betas = []
        for i in range(1, len(self.history)):
            prev = self.history[i - 1]
            curr = self.history[i]
            ds = curr.scale - prev.scale
            if ds == 0:
                ds = 1

            db = (curr.qa.b - prev.qa.b) / ds
            de = (curr.qa.e - prev.qa.e) / ds

            betas.append({
                "scale": curr.scale,
                "beta_b": db,
                "beta_e": de,
                "beta_norm": math.sqrt(db**2 + de**2),
                "loss": curr.loss,
            })
        return betas

    def find_fixed_points(self, threshold: float = 0.01) -> List[RGFlowState]:
        """Find approximate fixed points where beta ≈ 0."""
        betas = self.compute_beta_function()
        fixed = []

        for i, beta in enumerate(betas):
            if beta["beta_norm"] < threshold:
                fixed.append(self.history[i + 1])

        return fixed

    def flow_summary(self) -> Dict[str, Any]:
        """Summarize RG flow statistics."""
        if not self.history:
            return {}

        initial = self.history[0]
        final = self.history[-1]
        betas = self.compute_beta_function()

        return {
            "n_steps": len(self.history),
            "initial_qa": initial.qa.as_tuple(),
            "final_qa": final.qa.as_tuple(),
            "initial_loss": initial.loss,
            "final_loss": final.loss,
            "initial_harmonic": initial.harmonic_score(),
            "final_harmonic": final.harmonic_score(),
            "avg_beta_norm": np.mean([b["beta_norm"] for b in betas]) if betas else 0,
            "fixed_points": len(self.find_fixed_points()),
        }


def simulate_training(
    n_epochs: int = 50,
    initial_loss: float = 2.0,
    decay_rate: float = 0.05,
    noise_level: float = 0.1,
) -> Tuple[List[np.ndarray], List[float], List[float]]:
    """Simulate neural network training trajectory."""
    np.random.seed(42)

    weights_history = []
    loss_history = []
    grad_history = []

    # Initial weights
    weights = np.random.randn(100, 100) * 0.5

    for epoch in range(n_epochs):
        # Simulate loss decay with noise
        loss = initial_loss * np.exp(-decay_rate * epoch) + noise_level * np.random.randn()
        loss = max(0.01, loss)

        # Simulate gradient
        grad_norm = loss * (1 + 0.1 * np.random.randn())

        # Update weights (simplified SGD-like)
        weights = weights * (1 - 0.01 * grad_norm) + 0.01 * np.random.randn(*weights.shape)

        weights_history.append(weights.copy())
        loss_history.append(loss)
        grad_history.append(grad_norm)

    return weights_history, loss_history, grad_history


def demo():
    """Demo QA RG flow tracking."""
    print("=== QA Neural RG Flow Demo ===")
    print("Tracking neural network training as RG flow\n")

    # Simulate training
    weights_hist, loss_hist, grad_hist = simulate_training(n_epochs=50)

    # Track via QA
    tracker = QARGTracker(b_scale=10.0, e_scale=5.0)

    for epoch, (w, loss, grad) in enumerate(zip(weights_hist, loss_hist, grad_hist)):
        tracker.record_state(
            scale=epoch,
            weights=w,
            loss=loss,
            grad_norm=grad,
        )

    # Summary
    summary = tracker.flow_summary()
    print("--- RG Flow Summary ---")
    print(f"  Steps: {summary['n_steps']}")
    print(f"  Initial QA: {tuple(f'{x:.3f}' for x in summary['initial_qa'])}")
    print(f"  Final QA: {tuple(f'{x:.3f}' for x in summary['final_qa'])}")
    print(f"  Loss: {summary['initial_loss']:.4f} → {summary['final_loss']:.4f}")
    print(f"  Harmonic: {summary['initial_harmonic']:.4f} → {summary['final_harmonic']:.4f}")
    print(f"  Avg beta norm: {summary['avg_beta_norm']:.4f}")
    print(f"  Fixed points found: {summary['fixed_points']}")

    # Beta function analysis
    betas = tracker.compute_beta_function()
    print("\n--- Beta Function (sample) ---")
    for b in betas[::10]:  # Every 10th
        print(f"  Scale {b['scale']:3d}: β=(β_b={b['beta_b']:+.4f}, β_e={b['beta_e']:+.4f}), "
              f"|β|={b['beta_norm']:.4f}, loss={b['loss']:.4f}")

    # Fixed points
    fixed = tracker.find_fixed_points(threshold=0.02)
    if fixed:
        print(f"\n--- Fixed Points (threshold=0.02) ---")
        for fp in fixed[:5]:
            print(f"  Scale {fp.scale}: QA={tuple(f'{x:.3f}' for x in fp.qa.as_tuple())}, "
                  f"H={fp.harmonic_score():.4f}")


if __name__ == "__main__":
    demo()
