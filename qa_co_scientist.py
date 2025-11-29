"""
qa_co_scientist.py - QA-based hypothesis generation engine

Based on Google's AI Co-Scientist architecture, maps hypotheses to QA tuples:
- Hypothesis encoding → (b, e, d, a) representation
- Consistency scoring via QA constraints
- Hypothesis evolution via HGD-style updates
- Tournament selection for hypothesis refinement
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
import math
import random
import hashlib


@dataclass
class QATuple:
    """QA tuple with constraints d=b+e, a=e+d."""
    b: float
    e: float
    d: float = field(init=False)
    a: float = field(init=False)

    def __post_init__(self):
        self.d = self.b + self.e
        self.a = self.e + self.d

    @property
    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.b, self.e, self.d, self.a)

    def invariants(self) -> Dict[str, float]:
        """Compute QA invariants."""
        b, e, d, a = self.as_tuple
        return {
            "J": b * d,      # perigee
            "K": d * a,      # apogee
            "X": e * d,      # half-foci
            "C": 2 * e * d,  # long leg
            "F": b * a,      # short leg
            "G": e**2 + d**2,  # hypotenuse
        }


@dataclass
class Hypothesis:
    """A scientific hypothesis with QA representation."""
    text: str
    qa: QATuple
    confidence: float = 0.5
    evidence_count: int = 0
    parent_id: Optional[str] = None
    generation: int = 0

    @property
    def id(self) -> str:
        return hashlib.md5(self.text.encode()).hexdigest()[:8]

    def qa_score(self) -> float:
        """Score based on QA harmonic properties."""
        inv = self.qa.invariants()
        # Pythagorean residual: C² + F² ≈ G²
        pyth_res = abs(inv["C"]**2 + inv["F"]**2 - inv["G"]**2)
        # Normalize
        norm = max(inv["G"]**2, 1.0)
        return 1.0 / (1.0 + pyth_res / norm)

    def total_score(self) -> float:
        """Combined confidence and QA score."""
        return self.confidence * self.qa_score()


def text_to_qa(text: str, seed: Optional[int] = None) -> QATuple:
    """Encode text hypothesis as QA tuple via hash-based mapping."""
    h = hashlib.sha256(text.encode()).hexdigest()
    if seed is not None:
        h = hashlib.sha256((text + str(seed)).encode()).hexdigest()

    # Map first 8 hex chars to b, e in [1, 10]
    b_raw = int(h[0:4], 16) / 65535.0
    e_raw = int(h[4:8], 16) / 65535.0

    b = 1.0 + 9.0 * b_raw  # [1, 10]
    e = 1.0 + 9.0 * e_raw  # [1, 10]

    return QATuple(b=b, e=e)


class HypothesisPool:
    """Pool of hypotheses with tournament selection."""

    def __init__(self, max_size: int = 100):
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.max_size = max_size

    def add(self, hyp: Hypothesis) -> None:
        self.hypotheses[hyp.id] = hyp
        self._prune()

    def _prune(self) -> None:
        if len(self.hypotheses) > self.max_size:
            sorted_hyps = sorted(
                self.hypotheses.values(),
                key=lambda h: h.total_score(),
                reverse=True
            )
            self.hypotheses = {h.id: h for h in sorted_hyps[:self.max_size]}

    def tournament_select(self, k: int = 3) -> Optional[Hypothesis]:
        """Select best of k random hypotheses."""
        if not self.hypotheses:
            return None
        candidates = random.sample(list(self.hypotheses.values()), min(k, len(self.hypotheses)))
        return max(candidates, key=lambda h: h.total_score())

    def top_n(self, n: int = 5) -> List[Hypothesis]:
        return sorted(
            self.hypotheses.values(),
            key=lambda h: h.total_score(),
            reverse=True
        )[:n]


class QACoScientist:
    """QA-based Co-Scientist for hypothesis generation and refinement.

    Pipeline:
    1. Seed hypotheses from observations/questions
    2. Encode as QA tuples
    3. Score via QA harmonic constraints
    4. Evolve via HGD-style mutations
    5. Tournament selection for refinement
    """

    def __init__(
        self,
        pool_size: int = 100,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.3,
        rng_seed: Optional[int] = None,
    ):
        self.pool = HypothesisPool(max_size=pool_size)
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.generation = 0
        if rng_seed is not None:
            random.seed(rng_seed)

    def seed_hypothesis(self, text: str, confidence: float = 0.5) -> Hypothesis:
        """Create and add a seed hypothesis."""
        qa = text_to_qa(text)
        hyp = Hypothesis(text=text, qa=qa, confidence=confidence, generation=0)
        self.pool.add(hyp)
        return hyp

    def mutate_hypothesis(self, hyp: Hypothesis) -> Hypothesis:
        """Generate mutated hypothesis via QA perturbation."""
        # Perturb QA tuple
        b_new = hyp.qa.b + random.gauss(0, self.mutation_rate * hyp.qa.b)
        e_new = hyp.qa.e + random.gauss(0, self.mutation_rate * hyp.qa.e)
        b_new = max(0.1, b_new)
        e_new = max(0.1, e_new)

        # Generate mutated text marker
        mut_text = f"{hyp.text} [variant-{self.generation}]"

        new_hyp = Hypothesis(
            text=mut_text,
            qa=QATuple(b=b_new, e=e_new),
            confidence=hyp.confidence * 0.9,  # Slight decay
            parent_id=hyp.id,
            generation=self.generation + 1,
        )
        return new_hyp

    def crossover(self, h1: Hypothesis, h2: Hypothesis) -> Hypothesis:
        """Combine two hypotheses via QA averaging."""
        alpha = random.random()
        b_new = alpha * h1.qa.b + (1 - alpha) * h2.qa.b
        e_new = alpha * h1.qa.e + (1 - alpha) * h2.qa.e

        cross_text = f"({h1.text[:30]}... + {h2.text[:30]}...) [cross-{self.generation}]"

        new_hyp = Hypothesis(
            text=cross_text,
            qa=QATuple(b=b_new, e=e_new),
            confidence=(h1.confidence + h2.confidence) / 2,
            parent_id=h1.id,
            generation=self.generation + 1,
        )
        return new_hyp

    def evolve(self, n_offspring: int = 10) -> List[Hypothesis]:
        """Generate new hypotheses via evolution."""
        offspring = []
        self.generation += 1

        for _ in range(n_offspring):
            if random.random() < self.crossover_rate and len(self.pool.hypotheses) >= 2:
                # Crossover
                h1 = self.pool.tournament_select()
                h2 = self.pool.tournament_select()
                if h1 and h2 and h1.id != h2.id:
                    child = self.crossover(h1, h2)
                    offspring.append(child)
                    self.pool.add(child)
            else:
                # Mutation
                parent = self.pool.tournament_select()
                if parent:
                    child = self.mutate_hypothesis(parent)
                    offspring.append(child)
                    self.pool.add(child)

        return offspring

    def update_evidence(self, hyp_id: str, positive: bool) -> None:
        """Update hypothesis confidence based on evidence."""
        if hyp_id in self.pool.hypotheses:
            hyp = self.pool.hypotheses[hyp_id]
            hyp.evidence_count += 1
            if positive:
                hyp.confidence = min(1.0, hyp.confidence + 0.1 * (1 - hyp.confidence))
            else:
                hyp.confidence = max(0.0, hyp.confidence - 0.1 * hyp.confidence)

    def rank_hypotheses(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Return ranked hypotheses with QA analysis."""
        results = []
        for hyp in self.pool.top_n(top_n):
            inv = hyp.qa.invariants()
            results.append({
                "id": hyp.id,
                "text": hyp.text[:100],
                "confidence": hyp.confidence,
                "qa_score": hyp.qa_score(),
                "total_score": hyp.total_score(),
                "qa_tuple": hyp.qa.as_tuple,
                "invariants": inv,
                "generation": hyp.generation,
            })
        return results


def demo():
    """Demo the QA Co-Scientist."""
    print("=== QA Co-Scientist Demo ===")
    print("Hypothesis generation via QA tuple evolution\n")

    scientist = QACoScientist(pool_size=50, rng_seed=42)

    # Seed initial hypotheses
    seeds = [
        ("QA tuples encode Pythagorean structure", 0.7),
        ("E8 alignment correlates with harmonic quality", 0.6),
        ("Mod-9 digital roots preserve number-theoretic invariants", 0.5),
        ("Fibonacci sequences are QA-optimal", 0.8),
        ("Torus knot classification separates AP from GP", 0.65),
    ]

    print("--- Seeding hypotheses ---")
    for text, conf in seeds:
        hyp = scientist.seed_hypothesis(text, conf)
        print(f"  [{hyp.id}] {text[:50]}... (conf={conf:.2f})")

    # Evolve for several generations
    print("\n--- Evolving hypotheses ---")
    for gen in range(5):
        offspring = scientist.evolve(n_offspring=8)
        print(f"  Generation {gen+1}: {len(offspring)} new hypotheses")

    # Simulate evidence updates
    print("\n--- Simulating evidence ---")
    top = scientist.pool.top_n(3)
    for hyp in top:
        scientist.update_evidence(hyp.id, positive=random.random() > 0.3)

    # Final ranking
    print("\n--- Top Hypotheses ---")
    rankings = scientist.rank_hypotheses(top_n=5)
    for i, r in enumerate(rankings, 1):
        print(f"\n{i}. [{r['id']}] Gen {r['generation']}")
        print(f"   Text: {r['text'][:60]}...")
        print(f"   Confidence: {r['confidence']:.3f}, QA Score: {r['qa_score']:.3f}")
        print(f"   Total Score: {r['total_score']:.3f}")
        print(f"   QA tuple: (b={r['qa_tuple'][0]:.2f}, e={r['qa_tuple'][1]:.2f}, "
              f"d={r['qa_tuple'][2]:.2f}, a={r['qa_tuple'][3]:.2f})")


if __name__ == "__main__":
    demo()
