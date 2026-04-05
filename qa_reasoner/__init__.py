"""
qa_reasoner
===========
Discrete QA reasoning system. Replacement for the broken float-based QALM.

Theorem NT compliant by construction: all reasoning is over discrete integer
states in {1..m} (A1), derived coordinates d=b+e, a=b+2e (A2), and integer
generator sequences (Q, T). No floats enter the causal reasoning path.

Public API:
    QAReasoner(m)              — bound reasoner for modulus m
      .classify(b, e)          — orbit family, length, norm
      .invariants(b, e)        — 16 identities + chromogeometric quadrances
      .witness(src, tgt)       — shortest generator sequence or obstruction reason
      .explain(b, e)           — full structured reasoning trace
      .match_pattern(examples) — find common structure across discrete tuples

This is not a neural model — it is an exact symbolic reasoner over a finite
discrete state space. The "training data" is the algebraic structure itself.
"""

from .reasoner import QAReasoner
from .identities import compute_16_identities, chromogeometric_quadrances
from .patterns import PatternMatcher

__all__ = [
    "QAReasoner",
    "compute_16_identities",
    "chromogeometric_quadrances",
    "PatternMatcher",
]

__version__ = "0.1.0"
