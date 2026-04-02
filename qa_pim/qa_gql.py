"""QA-GQL: Tiny JSON DSL for composing kernel operations."""

import json
import numpy as np
from typing import Dict, List, Any, Tuple

from .kernels import RESIDUE_SELECT, ROLLING_SUM_PHASE


def compile_query(query_json) -> List[Tuple]:
    """Compile QA-GQL JSON to kernel execution plan."""
    if isinstance(query_json, str):
        query = json.loads(query_json)
    else:
        query = query_json

    plan = []

    if "select_sectors" in query:
        sectors = set(query["select_sectors"])
        plan.append(("RESIDUE_SELECT", sectors))

    if "op" in query:
        op = query["op"]
        if op == "rolling_sum_phase":
            width = query.get("width", 64)
            modulus = query.get("modulus", None)
            plan.append(("ROLLING_SUM_PHASE", width, modulus))
        else:
            raise ValueError(f"Unknown operation: {op}")

    return plan


def execute_plan(
    plan: List[Tuple],
    sectors: np.ndarray,
    phases: np.ndarray,
    values: np.ndarray,
    params=None,
) -> Dict[str, Any]:
    """Execute compiled kernel plan on data."""
    current_mask = np.ones(len(sectors), dtype=bool)
    results = {}

    for step in plan:
        op_name = step[0]

        if op_name == "RESIDUE_SELECT":
            mask_set = step[1]
            current_mask = RESIDUE_SELECT(sectors, mask_set)
            results["selected_count"] = int(np.sum(current_mask))
            results["selected_sectors"] = list(mask_set)

        elif op_name == "ROLLING_SUM_PHASE":
            width = step[1]
            modulus = step[2] if len(step) > 2 else None

            selected_phases = phases[current_mask]
            selected_values = values[current_mask]

            if len(selected_values) == 0:
                results["rolling_sums"] = np.array([])
                continue

            if params and hasattr(params, "P"):
                P = params.P
            else:
                P = int(max(selected_phases)) + 1

            phase_sums = np.zeros(P)
            for p, v in zip(selected_phases, selected_values):
                phase_sums[p] += v

            rolling_result = ROLLING_SUM_PHASE(phase_sums, width, modulus)
            results["rolling_sums"] = rolling_result
            results["rolling_sum_shape"] = rolling_result.shape

    return results
