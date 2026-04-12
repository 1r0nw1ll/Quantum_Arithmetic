"""QA Graph — feature maps, community detection benchmarks, and evaluation.

Consolidates graph analysis infrastructure from codex_on_QA/ into an
importable package.
"""

QA_COMPLIANCE = "observer=graph_analysis_library, state_alphabet=graph_topology"

from .feature_map import qa_feature_vector, compute_qa_invariants
from .feature_map import CANONICAL_21, EXPANDED_6
from .cayley import (
    enumerate_state_space,
    bateson_generators,
    build_cayley_graph,
    cayley_distance,
    cayley_ball,
    component_sizes,
    verify_bateson_cayley_equivalence,
    BATESON_191_S9_COUNTS,
    BATESON_191_S9_CUMULATIVE,
)
from .hypergraph import (
    qa_hyperedge,
    t_shift_hyperedge,
    build_qa_hypergraph,
    verify_sliding_window,
    verify_vertex_degree_uniformity,
    orbit_multiset_stats,
    verify_all_theorems,
    SLIDING_WINDOW_S9,
    VERTEX_DEGREE_S9,
    ORBIT_MULTISETS_S9,
)
from .knowledge_graph import (
    QAKnowledgeGraph,
    CANONICAL_EDGE_TYPES,
    ROLE_RANK,
    compute_sector,
    diagonal_index,
)
from .causal_dag import (
    CAUSAL_NODES,
    CAUSAL_EDGES,
    EXOGENOUS,
    ENDOGENOUS,
    ALL_PAIRS,
    invert_pair,
    pair_bijectivity,
    verify_y_structure,
    verify_pair_invertibility_theorem,
    pearl_level_collapse_samples,
)
from .signed_temporal import (
    eisenstein_norm,
    verify_norm_flip_identity,
    verify_t2_norm_preservation,
    signed_orbit_classification,
    temporal_sign_sequence,
    verify_all_on_s9 as verify_signed_temporal_theorems,
    SIGNED_ORBITS_S9,
)

__all__ = [
    "qa_feature_vector",
    "compute_qa_invariants",
    "CANONICAL_21",
    "EXPANDED_6",
    "enumerate_state_space",
    "bateson_generators",
    "build_cayley_graph",
    "cayley_distance",
    "cayley_ball",
    "component_sizes",
    "verify_bateson_cayley_equivalence",
    "BATESON_191_S9_COUNTS",
    "BATESON_191_S9_CUMULATIVE",
    "qa_hyperedge",
    "t_shift_hyperedge",
    "build_qa_hypergraph",
    "verify_sliding_window",
    "verify_vertex_degree_uniformity",
    "orbit_multiset_stats",
    "verify_all_theorems",
    "SLIDING_WINDOW_S9",
    "VERTEX_DEGREE_S9",
    "ORBIT_MULTISETS_S9",
    "QAKnowledgeGraph",
    "CANONICAL_EDGE_TYPES",
    "ROLE_RANK",
    "compute_sector",
    "diagonal_index",
    "CAUSAL_NODES",
    "CAUSAL_EDGES",
    "EXOGENOUS",
    "ENDOGENOUS",
    "ALL_PAIRS",
    "invert_pair",
    "pair_bijectivity",
    "verify_y_structure",
    "verify_pair_invertibility_theorem",
    "pearl_level_collapse_samples",
    "eisenstein_norm",
    "verify_norm_flip_identity",
    "verify_t2_norm_preservation",
    "signed_orbit_classification",
    "temporal_sign_sequence",
    "verify_signed_temporal_theorems",
    "SIGNED_ORBITS_S9",
]
