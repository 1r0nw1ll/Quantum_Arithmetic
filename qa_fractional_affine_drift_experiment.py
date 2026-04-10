#!/usr/bin/env python3
"""
Exact-rational observer-projection experiment: affine drift candidate law.

This is a narrow candidate family, not a universal QA theorem.
It tests whether a sampled rational signal can be decomposed into:
  - lawful component: exact constant drift on the sample index
  - residual ledger: exact rational deviation from that drift

All arithmetic uses unreduced rational pairs to avoid arbitrary fraction reduction.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rat:
    num: int
    den: int

    def __post_init__(self) -> None:
        if self.den == 0:
            raise ValueError("denominator must be non-zero")

    def normalized(self) -> "Rat":
        if self.den < 0:
            return Rat(-self.num, -self.den)
        return self

    def add(self, other: "Rat") -> "Rat":
        return Rat(self.num * other.den + other.num * self.den, self.den * other.den).normalized()

    def sub(self, other: "Rat") -> "Rat":
        return Rat(self.num * other.den - other.num * self.den, self.den * other.den).normalized()

    def mul(self, other: "Rat") -> "Rat":
        return Rat(self.num * other.num, self.den * other.den).normalized()

    def div(self, other: "Rat") -> "Rat":
        if other.num == 0:
            raise ValueError("division by zero")
        return Rat(self.num * other.den, self.den * other.num).normalized()

    def pair(self) -> list[int]:
        n = self.normalized()
        return [int(n.num), int(n.den)]

    def is_zero(self) -> bool:
        return self.num == 0


def rat(num: int, den: int = 1) -> Rat:
    return Rat(num, den).normalized()


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sample_grid(num_points: int, step: Rat) -> list[Rat]:
    points: list[Rat] = []
    current = rat(0, 1)
    for _ in range(num_points):
        points.append(current)
        current = current.add(step)
    return points


def affine_signal(points: list[Rat], slope: Rat, intercept: Rat) -> list[Rat]:
    return [slope.mul(t).add(intercept) for t in points]


def quadratic_signal(points: list[Rat], a: Rat, b: Rat, c: Rat) -> list[Rat]:
    out: list[Rat] = []
    for t in points:
        out.append(a.mul(t).mul(t).add(b.mul(t)).add(c))
    return out


def reciprocal_shift_signal(points: list[Rat], shift: Rat, scale: Rat) -> list[Rat]:
    out: list[Rat] = []
    for t in points:
        out.append(scale.div(t.add(shift)))
    return out


def decompose_affine_drift(points: list[Rat], values: list[Rat]) -> dict[str, object]:
    if len(points) != len(values) or not points:
        raise ValueError("points and values must be non-empty and aligned")

    if len(values) == 1:
        delta = rat(0, 1)
    else:
        delta = values[1].sub(values[0])

    predicted: list[Rat] = [values[0]]
    residuals: list[Rat] = [rat(0, 1)]
    current = values[0]
    for idx in range(1, len(values)):
        current = current.add(delta)
        predicted.append(current)
        residuals.append(values[idx].sub(current))

    law_component = {
        "family": "affine_drift_candidate",
        "index_step": [1, 1],
        "domain_step": points[1].sub(points[0]).pair() if len(points) > 1 else [0, 1],
        "num_points": len(points),
        "y0": values[0].pair(),
        "delta": delta.pair(),
    }
    residual_stream = [res.pair() for res in residuals]
    raw_stream = {
        "t": [point.pair() for point in points],
        "y": [value.pair() for value in values],
    }
    law_bytes = len(canonical_json_bytes(law_component))
    residual_bytes = len(canonical_json_bytes(residual_stream))
    raw_bytes = len(canonical_json_bytes(raw_stream))
    combined_bytes = law_bytes + residual_bytes

    return {
        "law_component": law_component,
        "predicted": [value.pair() for value in predicted],
        "residual_stream": residual_stream,
        "size_summary": {
            "law_component_bytes": law_bytes,
            "residual_bytes": residual_bytes,
            "combined_bytes": combined_bytes,
            "raw_exact_stream_bytes": raw_bytes,
            "combined_vs_raw_delta_bytes": combined_bytes - raw_bytes,
        },
        "residual_summary": {
            "all_zero": all(res.is_zero() for res in residuals),
            "nonzero_residual_count": sum(1 for res in residuals if not res.is_zero()),
        },
    }


def build_corpus(num_points: int, step_num: int, step_den: int) -> dict[str, object]:
    step = rat(step_num, step_den)
    points = sample_grid(num_points=num_points, step=step)
    datasets = [
        (
            "affine_3_over_2_plus_1_over_3",
            affine_signal(points, slope=rat(3, 2), intercept=rat(1, 3)),
        ),
        (
            "quadratic_1_over_2_t2_minus_1_over_3_t_plus_5_over_4",
            quadratic_signal(points, a=rat(1, 2), b=rat(-1, 3), c=rat(5, 4)),
        ),
        (
            "reciprocal_shift_2_over_t_plus_1",
            reciprocal_shift_signal(points, shift=rat(1, 1), scale=rat(2, 1)),
        ),
    ]

    results = []
    for name, values in datasets:
        results.append(
            {
                "name": name,
                "decomposition": decompose_affine_drift(points, values),
            }
        )

    return {
        "experiment": {
            "name": "qa_fractional_affine_drift_experiment",
            "candidate_family": "affine_drift_candidate",
            "arithmetic": "exact_unreduced_rational_pairs",
            "floats_used": False,
            "num_points": num_points,
            "domain_step": step.pair(),
        },
        "datasets": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the exact-rational affine-drift observer-projection candidate experiment.")
    parser.add_argument("--num-points", type=int, default=32, help="Number of sample points per signal")
    parser.add_argument("--step-num", type=int, default=1, help="Sampling step numerator")
    parser.add_argument("--step-den", type=int, default=8, help="Sampling step denominator")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/qa_fractional_affine_drift_experiment.json"),
        help="Where to write the exact-rational decomposition report",
    )
    args = parser.parse_args()

    report = build_corpus(num_points=args.num_points, step_num=args.step_num, step_den=args.step_den)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {args.output}")
    for dataset in report["datasets"]:
        summary = dataset["decomposition"]["size_summary"]
        residual = dataset["decomposition"]["residual_summary"]
        print(
            f"{dataset['name']}: "
            f"combined_bytes={summary['combined_bytes']} "
            f"raw_bytes={summary['raw_exact_stream_bytes']} "
            f"all_zero={residual['all_zero']} "
            f"nonzero_residual_count={residual['nonzero_residual_count']}"
        )


if __name__ == "__main__":
    main()
