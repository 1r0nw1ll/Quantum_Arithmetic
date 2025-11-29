"""
qa_wow_physics_loss.py - QA physics loss for WoW-style world models.

Enforces QA harmonic laws as physics constraints:
- Right-triangle identity: C² + F² ≈ G²
- QA tuple constraints: b+e=d, e+d=a
- Temporal smoothness in C, F, G
- Positivity of geometric quantities
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


def _apply_mask(x: torch.Tensor, mask: Optional[torch.Tensor]) -> torch.Tensor:
    """Broadcast-safe mask application."""
    if mask is None:
        return x.mean()
    while mask.ndim < x.ndim:
        mask = mask.unsqueeze(-1)
    mask = mask.to(x.dtype)
    masked = x * mask
    denom = mask.sum().clamp(min=1.0)
    return masked.sum() / denom


class QAWoWPhysicsLoss(nn.Module):
    """QA physics loss for WoW-style world models.

    Enforces:
    - Right-triangle identity: C² + F² ≈ G²
      where C = 2ed, F = ba, G = e² + d²
    - QA tuple constraints: b+e=d, e+d=a
    - Temporal smoothness (optional)
    - Positivity (optional)
    """

    def __init__(
        self,
        w_triangle: float = 1.0,
        w_qa_constraints: float = 1.0,
        w_smooth: float = 0.0,
        w_positive: float = 0.0,
        eps: float = 1e-8,
    ) -> None:
        super().__init__()
        self.w_triangle = w_triangle
        self.w_qa_constraints = w_qa_constraints
        self.w_smooth = w_smooth
        self.w_positive = w_positive
        self.eps = eps

    @staticmethod
    def _compute_derived(
        b: torch.Tensor,
        e: torch.Tensor,
        d: torch.Tensor,
        a: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Compute QA-derived geometric quantities from (b,e,d,a)."""
        C = 2.0 * e * d  # long leg
        F = b * a        # short leg
        G = e ** 2 + d ** 2  # hypotenuse
        J = b * d        # perigee
        X = e * d        # half foci distance
        K = d * a        # apogee
        return {"C": C, "F": F, "G": G, "J": J, "X": X, "K": K}

    def _triangle_loss(
        self,
        C: torch.Tensor,
        F_: torch.Tensor,
        G: torch.Tensor,
        mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """Enforce C² + F² ≈ G²."""
        lhs = C ** 2 + F_ ** 2
        rhs = G ** 2
        residual = (lhs - rhs) ** 2
        return _apply_mask(residual, mask)

    def _qa_constraint_loss(
        self,
        b: torch.Tensor,
        e: torch.Tensor,
        d: torch.Tensor,
        a: torch.Tensor,
        mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """Enforce b+e=d, e+d=a."""
        res1 = (b + e - d) ** 2
        res2 = (e + d - a) ** 2
        residual = res1 + res2
        return _apply_mask(residual, mask)

    def _smoothness_loss(
        self,
        C: torch.Tensor,
        F_: torch.Tensor,
        G: torch.Tensor,
        mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """Temporal smoothness penalty."""
        if C.size(1) <= 1:
            return C.new_tensor(0.0)
        dC = C[:, 1:] - C[:, :-1]
        dF = F_[:, 1:] - F_[:, :-1]
        dG = G[:, 1:] - G[:, :-1]
        diff_sq = dC ** 2 + dF ** 2 + dG ** 2
        if mask is not None:
            m_t = mask[:, 1:] & mask[:, :-1]
        else:
            m_t = None
        return _apply_mask(diff_sq, m_t)

    def _positivity_loss(
        self,
        C: torch.Tensor,
        F_: torch.Tensor,
        G: torch.Tensor,
        J: torch.Tensor,
        X: torch.Tensor,
        K: torch.Tensor,
        mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """Soft hinge penalty for positivity."""
        stacked = torch.stack([C, F_, G, J, X, K], dim=-1)
        penalty = F.relu(-stacked)
        penalty_sq = penalty ** 2
        return _apply_mask(penalty_sq, mask)

    def forward(
        self,
        qa_tuples: Dict[str, torch.Tensor],
        valid_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Compute total QA physics loss.

        Args:
            qa_tuples: dict with keys "b", "e", "d", "a"
                Each value: Tensor[batch, time, objects]
            valid_mask: optional Tensor[batch, time, objects]

        Returns:
            total_loss: scalar Tensor
            loss_dict: dict of component scalars
        """
        b = qa_tuples["b"]
        e = qa_tuples["e"]
        d = qa_tuples["d"]
        a = qa_tuples["a"]

        derived = self._compute_derived(b, e, d, a)
        C, F_, G = derived["C"], derived["F"], derived["G"]
        J, X, K = derived["J"], derived["X"], derived["K"]

        loss_triangle = self._triangle_loss(C, F_, G, valid_mask) if self.w_triangle > 0 else C.new_tensor(0.0)
        loss_qa_constraints = self._qa_constraint_loss(b, e, d, a, valid_mask) if self.w_qa_constraints > 0 else C.new_tensor(0.0)
        loss_smooth = self._smoothness_loss(C, F_, G, valid_mask) if self.w_smooth > 0 else C.new_tensor(0.0)
        loss_positive = self._positivity_loss(C, F_, G, J, X, K, valid_mask) if self.w_positive > 0 else C.new_tensor(0.0)

        total = (
            self.w_triangle * loss_triangle
            + self.w_qa_constraints * loss_qa_constraints
            + self.w_smooth * loss_smooth
            + self.w_positive * loss_positive
        )

        loss_dict = {
            "triangle": loss_triangle.detach(),
            "qa_constraints": loss_qa_constraints.detach(),
            "smooth": loss_smooth.detach(),
            "positive": loss_positive.detach(),
        }
        return total, loss_dict


def demo():
    """Demo the QA WoW physics loss."""
    print("=== QA WoW Physics Loss Demo ===")

    # Create sample QA tuples (batch=2, time=4, objects=3)
    batch, time, objects = 2, 4, 3

    # Valid QA tuples: b, e given; d=b+e, a=e+d
    b = torch.rand(batch, time, objects) + 0.5
    e = torch.rand(batch, time, objects) + 0.5
    d = b + e
    a = e + d

    qa_tuples = {"b": b, "e": e, "d": d, "a": a}

    # Test with perfect QA tuples
    loss_fn = QAWoWPhysicsLoss(
        w_triangle=1.0,
        w_qa_constraints=1.0,
        w_smooth=0.1,
        w_positive=0.1,
    )

    total_loss, components = loss_fn(qa_tuples)

    print(f"\nWith valid QA tuples:")
    print(f"  Total loss: {total_loss.item():.6f}")
    for k, v in components.items():
        print(f"  {k}: {v.item():.6f}")

    # Test with violated constraints
    bad_d = d + 0.5  # Violate b+e=d
    bad_qa = {"b": b, "e": e, "d": bad_d, "a": a}
    bad_loss, bad_components = loss_fn(bad_qa)

    print(f"\nWith violated constraints:")
    print(f"  Total loss: {bad_loss.item():.6f}")
    for k, v in bad_components.items():
        print(f"  {k}: {v.item():.6f}")


if __name__ == "__main__":
    demo()
