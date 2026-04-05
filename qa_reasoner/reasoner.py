"""
QAReasoner — exact symbolic reasoning over the discrete QA state space.

Theorem NT compliance:
    - All state components are ints in {1..m} (A1)
    - Derived coordinates computed: d = qa_mod(b+e), a = qa_mod(b+2e) (A2)
    - Generators Q and T applied as integer maps (S2, T1)
    - No floats enter reasoning — observer projections only as output channels

This is NOT a machine learning model. It is a symbolic reasoner. The state
space is finite (|Z_m^2| = m²), fully enumerable, and every orbit/classification/
witness is computed exactly by graph search.

Unlike the scrapped float-transformer QALM, this reasoner:
    - Gives correct answers on day 1
    - Has no training phase (the algebra IS the knowledge)
    - Never drifts from axioms
    - Composes with qa_core, qa_graph, qa_pim, qa_observer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from qa_core import (
    qa_mod,
    qa_step,
    qa_tuple,
    qa_norm,
    classify_state,
    orbit,
    orbit_length,
    shortest_witness,
    reachable_states,
    same_orbit,
    is_reachable,
    structural_obstruction,
    INERT_PRIMES,
)

from .identities import compute_16_identities, chromogeometric_quadrances, verify_identities


@dataclass(frozen=True)
class ClassificationResult:
    b: int
    e: int
    m: int
    tuple4: Tuple[int, int, int, int]
    family: str
    orbit_length_: int
    norm: int
    norm_mod: int
    obstructed: bool
    orbit: Tuple[Tuple[int, int], ...]

    def to_dict(self) -> Dict:
        return {
            "b": self.b, "e": self.e, "m": self.m,
            "tuple": list(self.tuple4),
            "family": self.family,
            "orbit_length": self.orbit_length_,
            "norm": self.norm,
            "norm_mod_m": self.norm_mod,
            "structurally_obstructed": self.obstructed,
            "orbit": [list(p) for p in self.orbit],
        }


@dataclass(frozen=True)
class WitnessResult:
    source: Tuple[int, int]
    target: Tuple[int, int]
    reachable: bool
    steps: int
    generator_trace: List[str]
    witness_states: List[Tuple[int, int]]
    reason_if_unreachable: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "source": list(self.source),
            "target": list(self.target),
            "reachable": self.reachable,
            "steps": self.steps,
            "generator_trace": self.generator_trace,
            "witness_states": [list(p) for p in self.witness_states],
            "reason_if_unreachable": self.reason_if_unreachable,
        }


class QAReasoner:
    """Exact symbolic reasoner bound to a single modulus.

    Usage:
        r = QAReasoner(m=9)
        r.classify(1, 1)             # -> ClassificationResult
        r.invariants(3, 5)           # -> dict of 16 identities + quadrances
        r.witness((1, 1), (3, 5))    # -> WitnessResult with generator trace
        r.explain(1, 1)              # -> full structured reasoning dict
    """

    def __init__(self, m: int):
        if m < 2:
            raise ValueError(f"modulus m must be >= 2, got {m}")
        self.m = int(m)

    # ------------------------------------------------------------------
    # Core queries
    # ------------------------------------------------------------------

    def canonicalize(self, b: int, e: int) -> Tuple[int, int]:
        """Reduce (b, e) into canonical A1 form: components in {1..m}."""
        return (qa_mod(b, self.m), qa_mod(e, self.m))

    def tuple4(self, b: int, e: int) -> Tuple[int, int, int, int]:
        """Full 4-tuple (b, e, d, a) with A1-compliant derived coords."""
        return qa_tuple(*self.canonicalize(b, e), self.m)

    def classify(self, b: int, e: int) -> ClassificationResult:
        """Classify (b, e) mod m: orbit family, length, norm, obstruction."""
        bc, ec = self.canonicalize(b, e)
        t4 = qa_tuple(bc, ec, self.m)
        family = classify_state(bc, ec, self.m)
        orb = orbit(bc, ec, self.m)
        n = qa_norm(bc, ec)
        n_mod = n % self.m
        inert = INERT_PRIMES.get(self.m, [])
        obs = structural_obstruction(n_mod, self.m) if inert else False
        return ClassificationResult(
            b=bc, e=ec, m=self.m,
            tuple4=t4,
            family=family,
            orbit_length_=len(orb),
            norm=n,
            norm_mod=n_mod,
            obstructed=obs,
            orbit=tuple(orb),
        )

    def invariants(self, b: int, e: int) -> Dict[str, object]:
        """Return the 16 QA identities + chromogeometric quadrances + verification.

        All values are exact integers. `verification` is a dict of relation
        names to bools, all of which MUST be True if the algebra is consistent.
        """
        bc, ec = self.canonicalize(b, e)
        d = bc + ec  # unreduced to preserve identity algebra
        ids = compute_16_identities(bc, ec)
        quads = chromogeometric_quadrances(d, ec)
        verif = verify_identities(bc, ec)
        return {
            "b": bc, "e": ec, "d": d, "a": bc + 2 * ec,
            "identities": ids,
            "chromogeometric": quads,
            "verification": verif,
            "all_verified": all(verif.values()),
        }

    def witness(
        self,
        source: Tuple[int, int],
        target: Tuple[int, int],
        generators: Tuple[str, ...] = ("Q",),
    ) -> WitnessResult:
        """Find a shortest generator sequence from source → target under the given
        generator set. Returns reachable=False with structural reason if impossible.
        """
        src = self.canonicalize(*source)
        tgt = self.canonicalize(*target)
        result = shortest_witness(src[0], src[1], tgt[0], tgt[1], self.m, generators=generators)
        if result is not None:
            return WitnessResult(
                source=src, target=tgt,
                reachable=True,
                steps=int(result["steps"]),
                generator_trace=list(result["generator_trace"]),
                witness_states=[tuple(x) for x in result["witness_states"]],
            )
        # Unreachable — diagnose
        src_orbit_family = classify_state(src[0], src[1], self.m)
        tgt_orbit_family = classify_state(tgt[0], tgt[1], self.m)
        if src_orbit_family != tgt_orbit_family:
            reason = (
                f"cross-orbit: source in {src_orbit_family}, target in {tgt_orbit_family}. "
                f"Generators {list(generators)} do not leave orbit families."
            )
        else:
            # Same family but different orbit cycles
            reason = (
                f"same family ({src_orbit_family}) but distinct orbit cycles. "
                f"No Q-trajectory connects source to target."
            )
        return WitnessResult(
            source=src, target=tgt,
            reachable=False,
            steps=-1,
            generator_trace=[],
            witness_states=[],
            reason_if_unreachable=reason,
        )

    def explain(self, b: int, e: int) -> Dict[str, object]:
        """Full structured reasoning trace for (b, e) mod m.

        This is what the old QALM tried and failed to do. Here it is exact,
        deterministic, and correct by construction.
        """
        cls = self.classify(b, e)
        inv = self.invariants(b, e)

        bc, ec = cls.b, cls.e
        trace = {
            "query": {"b": b, "e": e, "m": self.m},
            "step_1_canonicalize": {
                "input": [b, e],
                "canonical": [bc, ec],
                "rule": "A1: map to {1..m} via qa_mod(x, m) = ((x-1) % m) + 1",
            },
            "step_2_derived_coords": {
                "d": cls.tuple4[2],
                "a": cls.tuple4[3],
                "rule": "A2: d = qa_mod(b+e, m), a = qa_mod(b+2e, m)",
            },
            "step_3_classify": {
                "family": cls.family,
                "orbit_length": cls.orbit_length_,
                "rule": (
                    "length=1 → singularity; length=max(m²) → cosmos; else satellite. "
                    "Classification by orbit iteration under Q: (b,e) → (e, qa_mod(b+e,m))."
                ),
            },
            "step_4_norm": {
                "f(b,e)": cls.norm,
                "f(b,e) mod m": cls.norm_mod,
                "T_invariant": True,
                "rule": "Norm f(b,e) = b*b + b*e - e*e = N(b+eφ) in Z[φ]. T-invariant.",
            },
            "step_5_obstruction": {
                "inert_primes_mod_m": INERT_PRIMES.get(self.m, []),
                "structurally_obstructed": cls.obstructed,
                "rule": "v_p(f) == 1 for any inert prime p ⟹ unreachable as norm.",
            },
            "step_6_identities": inv["identities"],
            "step_7_chromogeometry": inv["chromogeometric"],
            "step_8_verification": inv["verification"],
            "all_verified": inv["all_verified"],
        }
        return trace

    # ------------------------------------------------------------------
    # Enumerative queries
    # ------------------------------------------------------------------

    def enumerate_orbits(self) -> Dict[str, List[List[Tuple[int, int]]]]:
        """Return all orbits grouped by family. Full enumeration for the modulus."""
        seen = set()
        by_family: Dict[str, List[List[Tuple[int, int]]]] = {
            "cosmos": [], "satellite": [], "singularity": []
        }
        for b in range(1, self.m + 1):
            for e in range(1, self.m + 1):
                if (b, e) in seen:
                    continue
                o = orbit(b, e, self.m)
                family = classify_state(b, e, self.m)
                by_family[family].append(o)
                for s in o:
                    seen.add(s)
        return by_family

    def orbit_statistics(self) -> Dict[str, int]:
        """Count pairs per orbit family."""
        counts = {"cosmos": 0, "satellite": 0, "singularity": 0}
        for b in range(1, self.m + 1):
            for e in range(1, self.m + 1):
                counts[classify_state(b, e, self.m)] += 1
        return counts
