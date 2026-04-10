#!/usr/bin/env python3
"""
Exact-rational scaffold for the observer-projection compression track.

Purpose:
  - build a no-float corpus of sampled rational functions
  - preserve exact Fraction values in a stable JSON form
  - provide a reproducible substrate for future fractional QA embedding work

This does NOT claim a QA decomposition yet. It only prepares the exact-rational
corpus and a size baseline so the next experiment can compare:
  function specification
  exact sampled stream
  future fractional QA lawful component + residual
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path


def frac_pair(value: Fraction) -> list[int]:
    return [int(value.numerator), int(value.denominator)]


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sample_grid(num_points: int, step: Fraction) -> list[Fraction]:
    points: list[Fraction] = []
    current = Fraction(0, 1)
    for _ in range(num_points):
        points.append(current)
        current += step
    return points


def affine_signal(points: list[Fraction], slope: Fraction, intercept: Fraction) -> list[Fraction]:
    return [slope * t + intercept for t in points]


def quadratic_signal(points: list[Fraction], a: Fraction, b: Fraction, c: Fraction) -> list[Fraction]:
    return [a * t * t + b * t + c for t in points]


def reciprocal_shift_signal(points: list[Fraction], shift: Fraction, scale: Fraction) -> list[Fraction]:
    out: list[Fraction] = []
    for t in points:
        out.append(scale / (t + shift))
    return out


def build_dataset(name: str, points: list[Fraction], values: list[Fraction], spec: dict[str, object]) -> dict[str, object]:
    raw_stream = {
        "t": [frac_pair(x) for x in points],
        "y": [frac_pair(y) for y in values],
    }
    spec_bytes = len(canonical_json_bytes(spec))
    raw_bytes = len(canonical_json_bytes(raw_stream))
    return {
        "name": name,
        "spec": spec,
        "samples": raw_stream,
        "size_baseline": {
            "function_spec_bytes": spec_bytes,
            "exact_sample_stream_bytes": raw_bytes,
            "spec_vs_stream_delta_bytes": spec_bytes - raw_bytes,
        },
        "qa_fractional_embedding": {
            "status": "unimplemented",
            "note": "Reserved for future exact-rational QA lawful-component plus observer-projection residual decomposition."
        },
    }


def build_corpus(num_points: int, step_num: int, step_den: int) -> dict[str, object]:
    step = Fraction(step_num, step_den)
    points = sample_grid(num_points=num_points, step=step)

    datasets = [
        build_dataset(
            name="affine_3_over_2_plus_1_over_3",
            points=points,
            values=affine_signal(points, slope=Fraction(3, 2), intercept=Fraction(1, 3)),
            spec={
                "family": "affine",
                "formula": "y = m*t + c",
                "parameters": {"m": frac_pair(Fraction(3, 2)), "c": frac_pair(Fraction(1, 3))},
                "domain_step": frac_pair(step),
                "num_points": num_points,
            },
        ),
        build_dataset(
            name="quadratic_1_over_2_t2_minus_1_over_3_t_plus_5_over_4",
            points=points,
            values=quadratic_signal(points, a=Fraction(1, 2), b=Fraction(-1, 3), c=Fraction(5, 4)),
            spec={
                "family": "quadratic",
                "formula": "y = a*t^2 + b*t + c",
                "parameters": {
                    "a": frac_pair(Fraction(1, 2)),
                    "b": frac_pair(Fraction(-1, 3)),
                    "c": frac_pair(Fraction(5, 4)),
                },
                "domain_step": frac_pair(step),
                "num_points": num_points,
            },
        ),
        build_dataset(
            name="reciprocal_shift_2_over_t_plus_1",
            points=points,
            values=reciprocal_shift_signal(points, shift=Fraction(1, 1), scale=Fraction(2, 1)),
            spec={
                "family": "reciprocal_shift",
                "formula": "y = s / (t + h)",
                "parameters": {"s": frac_pair(Fraction(2, 1)), "h": frac_pair(Fraction(1, 1))},
                "domain_step": frac_pair(step),
                "num_points": num_points,
            },
        ),
    ]

    return {
        "experiment": {
            "name": "qa_fractional_observer_projection_scaffold",
            "arithmetic": "exact_fraction",
            "num_points": num_points,
            "domain_step": frac_pair(step),
            "floats_used": False,
        },
        "datasets": datasets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an exact-rational scaffold corpus for future observer-projection QA experiments.")
    parser.add_argument("--num-points", type=int, default=32, help="Number of rational sample points per signal")
    parser.add_argument("--step-num", type=int, default=1, help="Sampling step numerator")
    parser.add_argument("--step-den", type=int, default=8, help="Sampling step denominator")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/qa_fractional_observer_projection_scaffold.json"),
        help="Where to write the exact-rational scaffold corpus",
    )
    args = parser.parse_args()

    corpus = build_corpus(num_points=args.num_points, step_num=args.step_num, step_den=args.step_den)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(corpus, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {args.output}")
    for dataset in corpus["datasets"]:
        baseline = dataset["size_baseline"]
        print(
            f"{dataset['name']}: "
            f"function_spec_bytes={baseline['function_spec_bytes']} "
            f"exact_sample_stream_bytes={baseline['exact_sample_stream_bytes']}"
        )


if __name__ == "__main__":
    main()
