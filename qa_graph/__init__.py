"""QA Graph — feature maps, community detection benchmarks, and evaluation.

Consolidates graph analysis infrastructure from codex_on_QA/ into an
importable package.
"""

QA_COMPLIANCE = "observer=graph_analysis_library, state_alphabet=graph_topology"

from .feature_map import qa_feature_vector, compute_qa_invariants
from .feature_map import CANONICAL_21, EXPANDED_6

__all__ = [
    "qa_feature_vector",
    "compute_qa_invariants",
    "CANONICAL_21",
    "EXPANDED_6",
]
