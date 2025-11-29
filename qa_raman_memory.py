"""
qa_raman_memory.py - QA-based Raman quantum memory simulator

Models the Hankel-transform-based Raman quantum memory as a QA rotor
that maps optical tuples to spinwave tuples while preserving QA family.

Key concepts:
- Hankel transform = QA radial rotor
- Spinwave compaction = HGD on (J, K) space
- Near-unity efficiency = single QA family isolation
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Callable, Sequence, Optional, List
import math
import random

QATuple = Tuple[int, int, int, int]  # (b, e, d, a)
AmplitudeDict = Dict[QATuple, complex]


def digital_root_mod9(n: int) -> int:
    """QA-style digital root in {1,...,9}."""
    if n == 0:
        return 9
    n_abs = abs(n)
    r = n_abs % 9
    return r if r != 0 else 9


def mod24_bin(n: int) -> int:
    """Map integer to {0,...,23}."""
    return n % 24


@dataclass
class QARamanConfig:
    lambda_noise: float = 1.0
    mu_constraints: float = 1.0
    beta_compaction: float = 1.0
    learning_rate: float = 1e-2
    allowed_mod9: Optional[Sequence[int]] = None  # e.g. [1, 2, 3, 5, 8] for Fibonacci
    allowed_mod24: Optional[Sequence[int]] = None


class QARamanMemory:
    """QA Raman memory simulator with cost functional and optimization.

    Models a Raman quantum memory cell as a QA rotor between:
    - Optical mode tuples (b_in, e_in, d_in, a_in)
    - Spinwave tuples (b_sw, e_sw, d_sw, a_sw)

    Cost function targets:
    - High efficiency (signal family fraction)
    - Low noise (off-family leakage)
    - QA constraint integrity
    - Spinwave compaction (J, K variance)
    """

    def __init__(
        self,
        target_tuple: QATuple,
        config: Optional[QARamanConfig] = None,
    ):
        self.config = config or QARamanConfig()
        self.target_tuple = target_tuple
        b_star, e_star, d_star, a_star = target_tuple
        self.J_star = b_star * d_star
        self.K_star = d_star * a_star

    @staticmethod
    def _probabilities(amplitudes: AmplitudeDict) -> Dict[QATuple, float]:
        return {tau: abs(A) ** 2 for tau, A in amplitudes.items()}

    @staticmethod
    def _qa_constraint_term(tau: QATuple) -> float:
        b, e, d, a = tau
        return (b + e - d) ** 2 + (e + d - a) ** 2

    @staticmethod
    def _J(tau: QATuple) -> int:
        b, e, d, a = tau
        return b * d

    @staticmethod
    def _K(tau: QATuple) -> int:
        b, e, d, a = tau
        return d * a

    def _is_signal(self, tau: QATuple) -> bool:
        """Check if tuple is in allowed QA resonance family."""
        cfg = self.config
        b, e, d, a = tau

        # Hard QA constraint
        if (b + e != d) or (e + d != a):
            return False

        # mod-9 condition
        if cfg.allowed_mod9 is not None:
            if digital_root_mod9(a) not in cfg.allowed_mod9:
                return False

        # mod-24 condition
        if cfg.allowed_mod24 is not None:
            if mod24_bin(a) not in cfg.allowed_mod24:
                return False

        return True

    def _is_noise(self, tau: QATuple) -> bool:
        return not self._is_signal(tau)

    def _resonance_panel(
        self, probs: Dict[QATuple, float]
    ) -> Dict[int, Dict[int, float]]:
        """Build mod-9 x mod-24 resonance heatmap."""
        panel: Dict[int, Dict[int, float]] = {}
        for tau, p in probs.items():
            b, e, d, a = tau
            r9 = digital_root_mod9(a)
            r24 = mod24_bin(a)
            if r9 not in panel:
                panel[r9] = {}
            panel[r9][r24] = panel[r9].get(r24, 0.0) + p
        return panel

    def qa_metrics(self, amplitudes: AmplitudeDict) -> dict:
        """Compute QA metrics for the spinwave state."""
        probs = self._probabilities(amplitudes)
        P_tot = sum(probs.values()) + 1e-16

        sig_probs = {tau: p for tau, p in probs.items() if self._is_signal(tau)}
        noise_probs = {tau: p for tau, p in probs.items() if self._is_noise(tau)}
        P_sig = sum(sig_probs.values()) + 1e-16
        P_noise = sum(noise_probs.values())

        eta = P_sig / P_tot
        noise_frac = P_noise / P_tot

        constraint_penalty = sum(
            p * self._qa_constraint_term(tau) for tau, p in probs.items()
        ) / P_tot

        # Compaction penalty
        sigma_J2 = sum(
            p * (self._J(tau) - self.J_star) ** 2 for tau, p in sig_probs.items()
        ) / P_sig
        sigma_K2 = sum(
            p * (self._K(tau) - self.K_star) ** 2 for tau, p in sig_probs.items()
        ) / P_sig
        comp_penalty = sigma_J2 + sigma_K2

        return {
            "eta": eta,
            "noise_frac": noise_frac,
            "constraint_penalty": constraint_penalty,
            "compaction_penalty": comp_penalty,
            "resonance_panel": self._resonance_panel(probs),
        }

    def cost(self, amplitudes: AmplitudeDict) -> float:
        """Full QA cost: -eta + λ*noise + μ*constraints + β*compaction."""
        cfg = self.config
        m = self.qa_metrics(amplitudes)
        return (
            -m["eta"]
            + cfg.lambda_noise * m["noise_frac"]
            + cfg.mu_constraints * m["constraint_penalty"]
            + cfg.beta_compaction * m["compaction_penalty"]
        )


def simulate_hankel_rotor(
    input_tuple: QATuple,
    control_params: List[float],
    noise_level: float = 0.1,
    n_output_modes: int = 20,
) -> AmplitudeDict:
    """Simulate Hankel-transform Raman mapping as QA rotor.

    Maps input optical tuple to spinwave tuples with:
    - Primary mode near target
    - Some off-family leakage (noise)
    - Control params affect mode distribution
    """
    b_in, e_in, d_in, a_in = input_tuple
    amplitudes: AmplitudeDict = {}

    # Seed with control params influence
    random.seed(int(sum(control_params) * 1000) % 2**31)

    # Primary signal: tuples in same QA family
    for i in range(n_output_modes):
        # Generate tuples near the input family
        delta_b = int((control_params[0] if control_params else 0) + random.gauss(0, 1))
        delta_e = int((control_params[1] if len(control_params) > 1 else 0) + random.gauss(0, 1))

        b = max(1, b_in + delta_b)
        e = max(1, e_in + delta_e)
        d = b + e
        a = e + d

        # Amplitude depends on how close to target
        dist = abs(delta_b) + abs(delta_e)
        amp = math.exp(-0.5 * dist) * (1.0 + 0.1 * random.random())
        phase = random.uniform(0, 2 * math.pi)

        tau = (b, e, d, a)
        if tau in amplitudes:
            amplitudes[tau] += complex(amp * math.cos(phase), amp * math.sin(phase))
        else:
            amplitudes[tau] = complex(amp * math.cos(phase), amp * math.sin(phase))

    # Add noise: off-family tuples
    n_noise = int(n_output_modes * noise_level)
    for _ in range(n_noise):
        # Random tuple that violates QA or is off-family
        b = random.randint(1, 10)
        e = random.randint(1, 10)
        d = random.randint(1, 20)  # May violate b+e=d
        a = random.randint(1, 30)  # May violate e+d=a

        amp = noise_level * random.random()
        phase = random.uniform(0, 2 * math.pi)
        tau = (b, e, d, a)
        amplitudes[tau] = complex(amp * math.cos(phase), amp * math.sin(phase))

    return amplitudes


def demo():
    """Demo the QA Raman memory."""
    print("=== QA Raman Memory Demo ===")
    print("Simulating Hankel-transform Raman quantum memory")

    # Target spinwave: Fibonacci-like tuple
    target = (1, 2, 3, 5)  # b=1, e=2, d=3, a=5
    input_tuple = (1, 2, 3, 5)

    # Configure for Fibonacci family
    config = QARamanConfig(
        lambda_noise=1.0,
        mu_constraints=1.0,
        beta_compaction=0.5,
        allowed_mod9=[1, 2, 3, 5, 8],  # Fibonacci digital roots
    )

    memory = QARamanMemory(target_tuple=target, config=config)

    # Simulate with different control params
    print("\n--- Control params: [0, 0] (centered) ---")
    amps = simulate_hankel_rotor(input_tuple, [0, 0], noise_level=0.1)
    metrics = memory.qa_metrics(amps)
    cost = memory.cost(amps)
    print(f"  Efficiency (eta): {metrics['eta']:.4f}")
    print(f"  Noise fraction: {metrics['noise_frac']:.4f}")
    print(f"  Constraint penalty: {metrics['constraint_penalty']:.4f}")
    print(f"  Compaction penalty: {metrics['compaction_penalty']:.4f}")
    print(f"  Total cost: {cost:.4f}")

    print("\n--- Control params: [2, 1] (shifted) ---")
    amps2 = simulate_hankel_rotor(input_tuple, [2, 1], noise_level=0.1)
    metrics2 = memory.qa_metrics(amps2)
    cost2 = memory.cost(amps2)
    print(f"  Efficiency (eta): {metrics2['eta']:.4f}")
    print(f"  Noise fraction: {metrics2['noise_frac']:.4f}")
    print(f"  Constraint penalty: {metrics2['constraint_penalty']:.4f}")
    print(f"  Compaction penalty: {metrics2['compaction_penalty']:.4f}")
    print(f"  Total cost: {cost2:.4f}")

    # Show resonance panel (top entries)
    print("\n--- Resonance Panel (mod-9 x mod-24) ---")
    panel = metrics["resonance_panel"]
    for r9 in sorted(panel.keys())[:5]:
        r24_items = sorted(panel[r9].items(), key=lambda x: -x[1])[:3]
        print(f"  mod-9={r9}: {r24_items}")


if __name__ == "__main__":
    demo()
