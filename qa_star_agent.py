"""
QA★ Star Agent - Multi-branch QA reasoning engine

Based on DS-Star Agent architecture mapping to QA framework:
- Parallel reasoning branches = (b,e,d,a) tuple families
- Rank-fusion merging = G = e² + d² collapse
- Validity checks = H,I duality tests
- Memory graph = mod-24/mod-9 resonance lattice
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any

Number = float


@dataclass
class QATuple:
    """Core QA tuple with enforced constraints:
    - d = b + e
    - a = e + d = b + 2e
    """
    b: Number
    e: Number
    d: Number | None = None
    a: Number | None = None

    def __post_init__(self) -> None:
        self.d = self.b + self.e if self.d is None else self.d
        self.a = self.e + self.d if self.a is None else self.a

        if abs(self.d - (self.b + self.e)) > 1e-9:
            raise ValueError(f"d must equal b + e (got d={self.d}, b+e={self.b + self.e})")
        if abs(self.a - (self.e + self.d)) > 1e-9:
            raise ValueError(f"a must equal e + d (got a={self.a}, e+d={self.e + self.d})")

    @property
    def as_tuple(self) -> Tuple[Number, Number, Number, Number]:
        return self.b, self.e, self.d, self.a


@dataclass
class QATriangle:
    """Right triangle & ellipse invariants derived from (b, e, d, a).

    Canonical mapping:
    - F = b * a (short leg)
    - C = 2 * e * d (long leg)
    - G = e^2 + d^2 (hypotenuse)
    - r = b * e (in-radius)
    - J = b * d (perigee)
    - X = e * d (half distance between foci)
    - K = d * a (apogee)
    - W = d * (e + a) (equilateral side, also X + K)
    - H = C + F
    - I = C - F
    """
    qa: QATuple
    C: Number = field(init=False)
    F: Number = field(init=False)
    G: Number = field(init=False)
    r: Number = field(init=False)
    J: Number = field(init=False)
    X: Number = field(init=False)
    K: Number = field(init=False)
    W: Number = field(init=False)
    H: Number = field(init=False)
    I: Number = field(init=False)

    def __post_init__(self) -> None:
        b, e, d, a = self.qa.as_tuple
        self.F = b * a
        self.C = 2.0 * e * d
        self.G = e * e + d * d
        self.r = b * e
        self.J = b * d
        self.X = e * d
        self.K = d * a
        self.W = d * (e + a)
        self.H = self.C + self.F
        self.I = self.C - self.F

    def pythagorean_residual(self) -> Number:
        """| G^2 - (C^2 + F^2) | in QA units."""
        return abs(self.G * self.G - (self.C * self.C + self.F * self.F))

    def qa_constraint_residual(self) -> Number:
        """Residual for core QA constraints."""
        b, e, d, a = self.qa.as_tuple
        r1 = abs(d - (b + e))
        r2 = abs(a - (e + d))
        r3 = abs(self.C - 2.0 * e * d)
        r4 = abs(self.X - e * d)
        r5 = abs(self.J - b * d)
        r6 = abs(self.K - d * a)
        return r1 + r2 + r3 + r4 + r5 + r6

    def harmonic_loss(self, weight_pyth: Number = 1.0, weight_qa: Number = 1.0) -> Number:
        return weight_pyth * self.pythagorean_residual() + weight_qa * self.qa_constraint_residual()

    def mod9_phase(self) -> int:
        """Digital-root style phase from G (hypotenuse)."""
        n = int(round(self.G))
        n = abs(n)
        if n == 0:
            return 0
        return 1 + (n - 1) % 9

    def mod24_phase(self) -> int:
        """Outer 24-gon phase from W."""
        return int(round(self.W)) % 24


@dataclass
class QABranchState:
    """One reasoning branch in the QA★ Star Agent."""
    qa: QATuple
    triangle: QATriangle
    text_trace: List[str] = field(default_factory=list)
    depth: int = 0
    score: float = 0.0
    done: bool = False

    def append_step(self, text: str) -> None:
        self.text_trace.append(text)
        self.depth += 1

    def current_summary(self) -> str:
        return " | ".join(self.text_trace[-5:])


@dataclass
class QAStarConfig:
    num_branches: int = 4
    max_depth: int = 8
    learning_rate: float = 0.05
    harmonic_weight_pyth: float = 1.0
    harmonic_weight_qa: float = 0.3
    branch_temperature: float = 0.7
    rng_seed: Optional[int] = None


class QAStarAgent:
    """
    QA★ Star Agent - Multi-branch QA reasoning engine

    Each branch carries a (b,e,d,a) tuple and derived triangle.
    Loss = harmonic loss over QA constraints & Pythagorean residual.
    HGD-style updates adjust (b,e) for each branch.
    Branches generate text via a user-supplied policy function.

    Pluggable:
    * policy_fn -> QA-GPT / world model
    * critic_fn -> HGD-based or task-based scorer
    """

    def __init__(
        self,
        config: Optional[QAStarConfig] = None,
        policy_fn: Optional[Callable[[QABranchState, str, Dict[str, Any]], str]] = None,
        critic_fn: Optional[Callable[[QABranchState, str, Dict[str, Any]], float]] = None,
    ) -> None:
        self.config = config or QAStarConfig()
        if self.config.rng_seed is not None:
            random.seed(self.config.rng_seed)
        self.policy_fn = policy_fn or self._default_policy
        self.critic_fn = critic_fn or self._default_critic

    def solve(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run QA★ multi-branch reasoning on a task.

        Returns:
            {"best_text": str, "best_branch": QABranchState, "branches": List[QABranchState]}
        """
        ctx: Dict[str, Any] = context.copy() if context else {}
        branches = self._init_branches()

        for _ in range(self.config.max_depth):
            for br in branches:
                if br.done:
                    continue

                action_text = self.policy_fn(br, task, ctx)
                br.append_step(action_text)

                reward = self.critic_fn(br, task, ctx)
                br.score += reward

                # Harmonic Gradient Descent step
                self._harmonic_gradient_step(br)

                loss = br.triangle.harmonic_loss(
                    self.config.harmonic_weight_pyth,
                    self.config.harmonic_weight_qa,
                )
                if loss < 1e-9:
                    br.done = True

            self._fuse_branches(branches)

        best_branch = max(branches, key=lambda b: b.score)
        best_text = "\n".join(best_branch.text_trace)
        return {
            "best_text": best_text,
            "best_branch": best_branch,
            "branches": branches,
        }

    def _init_branches(self) -> List[QABranchState]:
        branches: List[QABranchState] = []
        for _ in range(self.config.num_branches):
            b = 1.0 + 0.1 * (random.random() - 0.5)
            e = 2.0 + 0.1 * (random.random() - 0.5)
            qa = QATuple(b=b, e=e)
            tri = QATriangle(qa)
            branches.append(QABranchState(qa=qa, triangle=tri))
        return branches

    def _default_policy(
        self,
        branch: QABranchState,
        task: str,
        context: Dict[str, Any],
    ) -> str:
        """Built-in text policy (replace with LM / QA-GPT)."""
        b, e, d, a = branch.qa.as_tuple
        tri = branch.triangle
        return (
            f"[step {branch.depth}] task='{task}' "
            f"(b,e,d,a)=({b:.4f},{e:.4f},{d:.4f},{a:.4f}); "
            f"C={tri.C:.4f}, F={tri.F:.4f}, G={tri.G:.4f}, "
            f"loss={tri.harmonic_loss():.3e}, "
            f"phase9={tri.mod9_phase()}, phase24={tri.mod24_phase()}"
        )

    def _default_critic(
        self,
        branch: QABranchState,
        task: str,
        context: Dict[str, Any],
    ) -> float:
        """Simple critic: negative harmonic loss plus depth reward."""
        tri = branch.triangle
        loss = tri.harmonic_loss(
            self.config.harmonic_weight_pyth,
            self.config.harmonic_weight_qa,
        )
        return -loss + 0.01 * branch.depth

    def _harmonic_gradient_step(self, branch: QABranchState) -> None:
        """Numerical HGD on (b,e), respecting d=b+e, a=e+d."""
        lr = self.config.learning_rate
        eps = 1e-4
        b0, e0, _, _ = branch.qa.as_tuple

        def loss_at(be: Tuple[Number, Number]) -> Number:
            b, e = be
            qa = QATuple(b=b, e=e)
            tri = QATriangle(qa)
            return tri.harmonic_loss(
                self.config.harmonic_weight_pyth,
                self.config.harmonic_weight_qa,
            )

        base_loss = loss_at((b0, e0))
        lb = loss_at((b0 + eps, e0))
        le = loss_at((b0, e0 + eps))
        db = (lb - base_loss) / eps
        de = (le - base_loss) / eps

        b_new = b0 - lr * db
        e_new = e0 - lr * de

        branch.qa = QATuple(b=b_new, e=e_new)
        branch.triangle = QATriangle(branch.qa)

    def _fuse_branches(self, branches: List[QABranchState]) -> None:
        """Soft fusion: nudge lower-scoring branches toward best in (b,e)-space."""
        if not branches:
            return
        best = max(branches, key=lambda b: b.score)
        b_best, e_best, _, _ = best.qa.as_tuple
        temp = max(self.config.branch_temperature, 1e-6)
        scores = [br.score for br in branches]
        max_s = max(scores)
        exps = [math.exp((s - max_s) / temp) for s in scores]
        Z = sum(exps) or 1.0
        probs = [x / Z for x in exps]

        for br, p in zip(branches, probs):
            if br is best:
                continue
            alpha = 0.1 * (1.0 - p)
            b_cur, e_cur, _, _ = br.qa.as_tuple
            b_new = (1 - alpha) * b_cur + alpha * b_best
            e_new = (1 - alpha) * e_cur + alpha * e_best
            br.qa = QATuple(b=b_new, e=e_new)
            br.triangle = QATriangle(br.qa)


def run_qa_star_demo() -> None:
    """Standalone demo of the QA★ Star Agent."""
    cfg = QAStarConfig(
        num_branches=4,
        max_depth=6,
        learning_rate=0.05,
        harmonic_weight_pyth=1.0,
        harmonic_weight_qa=0.3,
        branch_temperature=0.7,
        rng_seed=42,
    )
    agent = QAStarAgent(config=cfg)
    result = agent.solve("Stabilize QA right triangle & ellipse invariants")

    best = result["best_branch"]
    print("=== QA★ Star Agent Demo ===")
    print("Task: Stabilize QA right triangle & ellipse invariants")
    print("\n--- Best branch trace ---")
    for line in best.text_trace:
        print(line)

    print("\n--- Final QA state ---")
    b, e, d, a = best.qa.as_tuple
    tri = best.triangle
    print(f"(b,e,d,a)=({b:.6f},{e:.6f},{d:.6f},{a:.6f})")
    print(f"C={tri.C:.6f}, F={tri.F:.6f}, G={tri.G:.6f}")
    print(f"Pythagorean residual: {tri.pythagorean_residual():.3e}")
    print(f"QA constraint residual: {tri.qa_constraint_residual():.3e}")
    print(f"mod-9 phase: {tri.mod9_phase()}, mod-24 phase: {tri.mod24_phase()}")
    print(f"Total score: {best.score:.4f}")


if __name__ == "__main__":
    run_qa_star_demo()
