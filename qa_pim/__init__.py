"""QA Graph-PIM: Quantum Arithmetic Graph Database with PIM-style kernels.

Extracted from qa_graph_pim_repo_v2 vault artifact (2025-09).
Provides vectorized operations over residue classes and torus structures.
"""

from .schema import QAParams, schema_map
from .kernels import (
    RESIDUE_SELECT, TORUS_SHIFT, RADD_m, RMUL_m,
    MIRROR4, ROLLING_SUM_PHASE
)
from .crt import crt_join_general, crt_join_coprime
from .graph import build_sector_csr, neighbor_expand
from .qa_gql import compile_query, execute_plan

__version__ = "0.2.0"
__all__ = [
    "QAParams", "schema_map",
    "RESIDUE_SELECT", "TORUS_SHIFT", "RADD_m", "RMUL_m", "MIRROR4", "ROLLING_SUM_PHASE",
    "crt_join_general", "crt_join_coprime",
    "build_sector_csr", "neighbor_expand",
    "compile_query", "execute_plan",
]
