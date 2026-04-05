"""
Pattern matching over discrete QA states.

Unlike the float-transformer QALM, patterns here are exact symbolic structures
over finite integer state spaces. A "pattern" is a predicate or a generator
program that characterizes a set of (b, e) tuples.

Three classes of patterns supported:
    1. Classification patterns  — match by orbit family + length
    2. Norm patterns            — match by norm residue class mod m
    3. Generator-path patterns  — match by reachability from a fixed source

All pattern matching is exact (no kernels, no approximations).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

from qa_core import classify_state, qa_norm, orbit_length, same_orbit


Pair = Tuple[int, int]


@dataclass
class PatternMatcher:
    """Find common structure across a set of example QA tuples.

    Given a list of (b, e) pairs, return all exact patterns they share:
        - common orbit family
        - common orbit length
        - common norm mod m
        - whether they lie in the same orbit
        - shared residue classes on each coordinate

    This IS the learning algorithm. It is fast, exact, and axiom-faithful.
    """

    m: int

    def match(self, examples: Sequence[Pair]) -> Dict[str, object]:
        if not examples:
            return {"patterns": {}, "n_examples": 0}

        examples = [(int(b), int(e)) for b, e in examples]

        families = {classify_state(b, e, self.m) for b, e in examples}
        lengths = {orbit_length(b, e, self.m) for b, e in examples}
        norms = {qa_norm(b, e) for b, e in examples}
        norms_mod = {qa_norm(b, e) % self.m for b, e in examples}
        b_residues = {b % self.m for b, _ in examples}
        e_residues = {e % self.m for _, e in examples}
        d_values = {(b + e) for b, e in examples}
        a_values = {(b + 2 * e) for b, e in examples}

        # Are they all in the same orbit?
        b0, e0 = examples[0]
        same_orbit_flag = all(same_orbit(b0, e0, b, e, self.m) for b, e in examples[1:])

        return {
            "n_examples": len(examples),
            "patterns": {
                "common_family": list(families)[0] if len(families) == 1 else None,
                "all_families_seen": sorted(families),
                "common_orbit_length": list(lengths)[0] if len(lengths) == 1 else None,
                "all_lengths_seen": sorted(lengths),
                "common_norm": list(norms)[0] if len(norms) == 1 else None,
                "common_norm_mod_m": list(norms_mod)[0] if len(norms_mod) == 1 else None,
                "all_in_same_orbit": same_orbit_flag,
                "common_b_residue": list(b_residues)[0] if len(b_residues) == 1 else None,
                "common_e_residue": list(e_residues)[0] if len(e_residues) == 1 else None,
                "common_d_value": list(d_values)[0] if len(d_values) == 1 else None,
                "common_a_value": list(a_values)[0] if len(a_values) == 1 else None,
            },
            "examples": [list(p) for p in examples],
        }

    def filter(self, predicate: Callable[[int, int], bool]) -> List[Pair]:
        """Enumerate all (b, e) in {1..m}² satisfying a predicate."""
        return [(b, e) for b in range(1, self.m + 1)
                       for e in range(1, self.m + 1)
                       if predicate(b, e)]
