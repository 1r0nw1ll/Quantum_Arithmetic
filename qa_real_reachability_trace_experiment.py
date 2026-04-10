#!/usr/bin/env python3
"""
Generate exact-integer QA reachability traces from family [40] semantics.

This harvests deterministic run traces under:
  - objective: L2_TO_TARGET
  - policy: GREEDY_MIN_ENERGY_TIEBREAK_MOVE_NAME
  - generator set: {sigma, mu, lambda_k(2), nu}

The output is an exact state-sequence corpus suitable for qa_compression_benchmark.py.
No floats are used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa_reachability_descent_run_cert_v1.validator import (
    Move,
    State,
    apply_move,
    energy_l2_to_target,
    move_sort_key,
)


DEFAULT_N = 30
DEFAULT_MAX_STEPS = 256
DEFAULT_TARGET = State(1, 1)
GENERATOR_SET = [
    Move("sigma"),
    Move("mu"),
    Move("lambda_k", 2),
    Move("nu"),
]
REPRESENTATIVE_STARTS = [
    State(4, 2),
    State(8, 13),
    State(17, 5),
    State(30, 2),
    State(30, 30),
]


def choose_greedy_move(state: State, target: State, n: int) -> tuple[Move, State] | None:
    legal: list[tuple[int, str, Move, State]] = []
    for move in GENERATOR_SET:
        result = apply_move(state, move, n)
        if not result["ok"]:
            continue
        next_state = State(int(result["value"]["b"]), int(result["value"]["e"]))
        energy = energy_l2_to_target(next_state, target)
        legal.append((energy, move_sort_key(move), move, next_state))

    if not legal:
        return None

    legal.sort(key=lambda row: (row[0], row[1]))
    _, _, move, next_state = legal[0]
    return move, next_state


def simulate_run(start: State, target: State, n: int, max_steps: int) -> dict[str, object]:
    states = [[start.b, start.e]]
    chosen_moves: list[dict[str, object]] = []
    current = start

    for _ in range(max_steps):
        chosen = choose_greedy_move(current, target, n)
        if chosen is None:
            return {
                "states": states,
                "chosen_moves": chosen_moves,
                "terminated_by": "no_legal_move",
            }
        move, next_state = chosen
        chosen_moves.append(move.as_dict())
        states.append([next_state.b, next_state.e])
        current = next_state

    return {
        "states": states,
        "chosen_moves": chosen_moves,
        "terminated_by": "step_budget",
    }


def percentile(values: list[int], pct: int) -> int:
    if not values:
        raise ValueError("values must be non-empty")
    idx = ((len(values) - 1) * pct) // 100
    return values[idx]


def build_corpus(n: int, max_steps: int, target: State) -> dict[str, object]:
    run_records: list[dict[str, object]] = []
    aggregate_states: list[list[int]] = []
    lengths: list[int] = []
    budget_terminated = 0

    for b in range(1, n + 1):
        for e in range(1, n + 1):
            start = State(b, e)
            run = simulate_run(start, target, n, max_steps)
            run_records.append(
                {
                    "start_state": {"b": b, "e": e},
                    "num_states": len(run["states"]),
                    "terminated_by": run["terminated_by"],
                }
            )
            lengths.append(len(run["states"]))
            if run["terminated_by"] == "step_budget":
                budget_terminated += 1
            aggregate_states.extend(run["states"])

    representative_sequences = []
    for start in REPRESENTATIVE_STARTS:
        run = simulate_run(start, target, n, max_steps)
        representative_sequences.append(
            {
                "name": f"reachability_run_N{n}_target_{target.b}_{target.e}_start_{start.b}_{start.e}",
                "description": (
                    "Exact deterministic reachability-descent run using family [40] semantics "
                    f"on Caps({n},{n}) from start=({start.b},{start.e}) to target=({target.b},{target.e})"
                ),
                "modulus": n,
                "states": run["states"],
                "metadata": {
                    "family": 40,
                    "policy": "GREEDY_MIN_ENERGY_TIEBREAK_MOVE_NAME",
                    "generator_set": [move.as_dict() for move in GENERATOR_SET],
                    "terminated_by": run["terminated_by"],
                    "num_moves": len(run["chosen_moves"]),
                    "target_state": {"b": target.b, "e": target.e},
                },
            }
        )

    lengths_sorted = sorted(lengths)
    corpus = {
        "experiment": {
            "name": "qa_real_reachability_trace_experiment",
            "family": 40,
            "policy": "GREEDY_MIN_ENERGY_TIEBREAK_MOVE_NAME",
            "generator_set": [move.as_dict() for move in GENERATOR_SET],
            "N": n,
            "target_state": {"b": target.b, "e": target.e},
            "max_steps": max_steps,
        },
        "stats": {
            "num_runs": len(run_records),
            "aggregate_num_states": len(aggregate_states),
            "min_num_states": lengths_sorted[0],
            "p50_num_states": percentile(lengths_sorted, 50),
            "p90_num_states": percentile(lengths_sorted, 90),
            "max_num_states": lengths_sorted[-1],
            "budget_terminated_runs": budget_terminated,
        },
        "runs": run_records,
        "sequences": [
            {
                "name": f"reachability_all_runs_concat_N{n}_target_{target.b}_{target.e}",
                "description": (
                    "Concatenation of all exact deterministic reachability-descent runs in lexicographic "
                    f"start-state order on Caps({n},{n}) under family [40] semantics"
                ),
                "modulus": n,
                "states": aggregate_states,
                "metadata": {
                    "family": 40,
                    "policy": "GREEDY_MIN_ENERGY_TIEBREAK_MOVE_NAME",
                    "generator_set": [move.as_dict() for move in GENERATOR_SET],
                    "target_state": {"b": target.b, "e": target.e},
                    "num_runs": len(run_records),
                    "run_boundaries_present": True,
                },
            },
            *representative_sequences,
        ],
    }
    return corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate real exact reachability trace corpora for QA compression tests.")
    parser.add_argument("--N", type=int, default=DEFAULT_N, help="Caps(N,N) bound")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS, help="Per-run step budget")
    parser.add_argument("--target-b", type=int, default=DEFAULT_TARGET.b, help="Target state b")
    parser.add_argument("--target-e", type=int, default=DEFAULT_TARGET.e, help="Target state e")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/qa_real_reachability_trace_sequences.json"),
        help="Where to write the exact state-sequence corpus",
    )
    args = parser.parse_args()

    target = State(args.target_b, args.target_e)
    corpus = build_corpus(n=args.N, max_steps=args.max_steps, target=target)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(corpus, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {args.output}")
    print(json.dumps(corpus["stats"], indent=2, sort_keys=True))
    for item in corpus["sequences"]:
        print(f"{item['name']}: states={len(item['states'])}")


if __name__ == "__main__":
    main()
