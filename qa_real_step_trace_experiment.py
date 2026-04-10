#!/usr/bin/env python3
"""
qa_lab.qa_real_step_trace_experiment
====================================

Generate real QA-native (b,e) trace corpora by running exact integer query-step
tasks through the live QA Lab kernel. The output is a standalone JSON corpus that
can be benchmarked by qa_compression_benchmark.py without reconstructing states
from prose or mixed logs.

Pre-registered experiment intent:
- Hypothesis: real kernel-driven step chains will yield long lawful QA traces that
  are more appropriate for compression testing than the short mixed kernel log.
- Success criteria:
  1) produce at least one run with >= 128 ordered states
  2) all exported states remain exact integer pairs
  3) benchmark-ready JSON corpus written under results/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_LAB_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from qa_lab.session_start import build_kernel
from qa_lab.kernel import Task, TaskType


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def run_step_chain(
    *,
    modulus: int,
    start_b: int,
    start_e: int,
    steps: int,
) -> dict[str, Any]:
    kernel = build_kernel(dry_run=True, verbose=False, max_cycles=steps + 16)
    states: list[list[int]] = [[start_b, start_e]]
    current_b = start_b
    current_e = start_e

    for _ in range(steps):
        result = kernel.run_cycle(
            Task(
                task_type=TaskType.QUERY,
                description=f"One Q-step from ({current_b},{current_e}) mod {modulus}",
                inputs={
                    "query_type": "step",
                    "b": current_b,
                    "e": current_e,
                    "m": modulus,
                },
            )
        )
        after = result.output.get("after")
        if not isinstance(after, list) or len(after) != 2:
            raise RuntimeError(f"missing step output.after for ({current_b},{current_e}) mod {modulus}")
        next_b, next_e = after
        if not isinstance(next_b, int) or not isinstance(next_e, int):
            raise RuntimeError("non-integer state encountered")
        states.append([next_b, next_e])
        current_b = next_b
        current_e = next_e

    return {
        "name": f"kernel_step_chain_m{modulus}_{start_b}_{start_e}_{steps}",
        "description": (
            f"Real kernel/query-agent QA step chain starting at ({start_b},{start_e}) "
            f"mod {modulus} for {steps} exact steps"
        ),
        "modulus": modulus,
        "start_state": [start_b, start_e],
        "steps": steps,
        "states": states,
        "num_states": len(states),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate real QA-native step-trace corpora via the live kernel.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/qa_real_step_trace_sequences.json"),
        help="Output JSON corpus path",
    )
    parser.add_argument(
        "--steps-mod9",
        type=int,
        default=192,
        help="Step count for each mod-9 chain",
    )
    parser.add_argument(
        "--steps-mod24",
        type=int,
        default=192,
        help="Step count for each mod-24 chain",
    )
    args = parser.parse_args()

    sequences = [
        run_step_chain(modulus=9, start_b=1, start_e=1, steps=args.steps_mod9),
        run_step_chain(modulus=9, start_b=3, start_e=6, steps=args.steps_mod9),
        run_step_chain(modulus=24, start_b=1, start_e=1, steps=args.steps_mod24),
        run_step_chain(modulus=24, start_b=5, start_e=8, steps=args.steps_mod24),
    ]

    report = {
        "experiment": "qa_real_step_trace_experiment",
        "notes": [
            "Exact integer QA states only",
            "No floats",
            "No arbitrary fraction reduction",
            "Generated via live QALabKernel + QueryAgent step tasks",
        ],
        "sequences": sequences,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_canonical_json(report) + "\n", encoding="utf-8")

    print(f"Wrote {args.output}")
    for seq in sequences:
        print(
            f"{seq['name']}: modulus={seq['modulus']} "
            f"states={seq['num_states']} start={tuple(seq['start_state'])}"
        )


if __name__ == "__main__":
    main()
