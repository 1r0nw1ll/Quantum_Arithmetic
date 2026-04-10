#!/usr/bin/env python3
"""
Exact-rational projective observable matrix experiment.

Compares narrow QA-shaped observer-law candidates across two observables:
  - y = e / b
  - y = d / a where d = b + e and a = d + e

Each observable gets two one-axis drift subfamilies:
  - direct: b fixed, e drifts affinely
  - inverse: e fixed, b drifts affinely

This is a family-comparison experiment, not a universal theorem.
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

    def inv(self) -> "Rat":
        if self.num == 0:
            raise ValueError("cannot invert zero")
        return Rat(self.den, self.num).normalized()

    def pair(self) -> list[int]:
        n = self.normalized()
        return [int(n.num), int(n.den)]

    def is_zero(self) -> bool:
        return self.num == 0

    def equals(self, other: "Rat") -> bool:
        left = self.normalized()
        right = other.normalized()
        return left.num * right.den == right.num * left.den


def rat(num: int, den: int = 1) -> Rat:
    return Rat(num, den).normalized()


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sample_grid(num_points: int, step: Rat) -> list[Rat]:
    points = []
    current = rat(0, 1)
    for _ in range(num_points):
        points.append(current)
        current = current.add(step)
    return points


def exact_constant_delta(values: list[Rat]) -> Rat | None:
    if len(values) < 2:
        return rat(0, 1)
    delta = values[1].sub(values[0])
    for idx in range(2, len(values)):
        if not values[idx].sub(values[idx - 1]).equals(delta):
            return None
    return delta


def projective_state_record(b: Rat, e: Rat) -> dict[str, object]:
    d = b.add(e)
    a = d.add(e)
    return {"b": b.pair(), "e": e.pair(), "d": d.pair(), "a": a.pair()}


def pack_result(
    law_component: dict[str, object],
    states: list[dict[str, object]],
    predicted: list[Rat],
    residuals: list[Rat],
    observed: list[Rat],
) -> dict[str, object]:
    residual_stream = [res.pair() for res in residuals]
    observed_stream = [value.pair() for value in observed]
    all_zero = all(res.is_zero() for res in residuals)
    law_bytes = len(canonical_json_bytes(law_component))
    residual_bytes = len(canonical_json_bytes(residual_stream))
    raw_bytes = len(canonical_json_bytes(observed_stream))
    residual_payload_bytes = 0 if all_zero else residual_bytes
    return {
        "law_component": law_component,
        "states": states,
        "predicted": [value.pair() for value in predicted],
        "residual_stream": residual_stream,
        "size_summary": {
            "law_component_bytes": law_bytes,
            "residual_bytes": residual_bytes,
            "residual_payload_bytes": residual_payload_bytes,
            "combined_bytes": law_bytes + residual_payload_bytes,
            "raw_value_stream_bytes": raw_bytes,
            "combined_vs_raw_delta_bytes": law_bytes + residual_payload_bytes - raw_bytes,
        },
        "residual_summary": {
            "all_zero": all_zero,
            "nonzero_residual_count": sum(1 for res in residuals if not res.is_zero()),
        },
    }


def cand_direct_e_over_b(values: list[Rat]) -> dict[str, object]:
    delta = exact_constant_delta(values)
    if delta is None:
        raise ValueError("not affine under e/b direct")
    b_const = rat(1, 1)
    e_current = values[0]
    states = [projective_state_record(b_const, e_current)]
    predicted = [e_current]
    for _ in range(1, len(values)):
        e_current = e_current.add(delta)
        states.append(projective_state_record(b_const, e_current))
        predicted.append(e_current)
    residuals = [obs.sub(pred) for obs, pred in zip(values, predicted)]
    return pack_result(
        {
            "family": "direct_axis_drift",
            "observable": "e_over_b",
            "b_const": b_const.pair(),
            "e0": values[0].pair(),
            "delta_e": delta.pair(),
            "num_points": len(values),
        },
        states,
        predicted,
        residuals,
        values,
    )


def cand_inverse_e_over_b(values: list[Rat]) -> dict[str, object]:
    inverses = [value.inv() for value in values]
    delta = exact_constant_delta(inverses)
    if delta is None:
        raise ValueError("inverse not affine under e/b inverse")
    e_const = rat(1, 1)
    b_current = inverses[0]
    states = [projective_state_record(b_current, e_const)]
    predicted = [e_const.div(b_current)]
    for _ in range(1, len(values)):
        b_current = b_current.add(delta)
        states.append(projective_state_record(b_current, e_const))
        predicted.append(e_const.div(b_current))
    residuals = [obs.sub(pred) for obs, pred in zip(values, predicted)]
    return pack_result(
        {
            "family": "inverse_axis_drift",
            "observable": "e_over_b",
            "e_const": e_const.pair(),
            "b0": inverses[0].pair(),
            "delta_b": delta.pair(),
            "num_points": len(values),
        },
        states,
        predicted,
        residuals,
        values,
    )


def cand_direct_d_over_a(values: list[Rat]) -> dict[str, object]:
    transformed = []
    for value in values:
        transformed.append(rat(1, 1).sub(value).div(value.mul(rat(2, 1)).sub(rat(1, 1))))
    delta = exact_constant_delta(transformed)
    if delta is None:
        raise ValueError("transformed direct d/a coordinate not affine")
    b_const = rat(1, 1)
    e_current = transformed[0]
    states = [projective_state_record(b_const, e_current)]
    predicted = [b_const.add(e_current).div(b_const.add(e_current).add(e_current))]
    for _ in range(1, len(values)):
        e_current = e_current.add(delta)
        states.append(projective_state_record(b_const, e_current))
        predicted.append(b_const.add(e_current).div(b_const.add(e_current).add(e_current)))
    residuals = [obs.sub(pred) for obs, pred in zip(values, predicted)]
    return pack_result(
        {
            "family": "direct_axis_drift",
            "observable": "d_over_a",
            "b_const": b_const.pair(),
            "e0": transformed[0].pair(),
            "delta_e": delta.pair(),
            "num_points": len(values),
        },
        states,
        predicted,
        residuals,
        values,
    )


def cand_inverse_d_over_a(values: list[Rat]) -> dict[str, object]:
    transformed = []
    for value in values:
        transformed.append(rat(1, 1).sub(value.mul(rat(2, 1))).div(value.sub(rat(1, 1))))
    delta = exact_constant_delta(transformed)
    if delta is None:
        raise ValueError("transformed inverse d/a coordinate not affine")
    e_const = rat(1, 1)
    b_current = transformed[0]
    states = [projective_state_record(b_current, e_const)]
    predicted = [b_current.add(e_const).div(b_current.add(e_const).add(e_const))]
    for _ in range(1, len(values)):
        b_current = b_current.add(delta)
        states.append(projective_state_record(b_current, e_const))
        predicted.append(b_current.add(e_const).div(b_current.add(e_const).add(e_const)))
    residuals = [obs.sub(pred) for obs, pred in zip(values, predicted)]
    return pack_result(
        {
            "family": "inverse_axis_drift",
            "observable": "d_over_a",
            "e_const": e_const.pair(),
            "b0": transformed[0].pair(),
            "delta_b": delta.pair(),
            "num_points": len(values),
        },
        states,
        predicted,
        residuals,
        values,
    )


def best_candidate(values: list[Rat]) -> dict[str, object]:
    candidates = []
    funcs = [
        ("direct_axis_drift__e_over_b", cand_direct_e_over_b),
        ("inverse_axis_drift__e_over_b", cand_inverse_e_over_b),
        ("direct_axis_drift__d_over_a", cand_direct_d_over_a),
        ("inverse_axis_drift__d_over_a", cand_inverse_d_over_a),
    ]
    for name, fn in funcs:
        try:
            result = fn(values)
            result["candidate_name"] = name
            candidates.append(result)
        except ValueError:
            continue
    if not candidates:
        return {"status": "no_exact_candidate", "candidates_considered": [name for name, _ in funcs]}
    best = min(candidates, key=lambda item: item["size_summary"]["combined_bytes"])
    best["status"] = "ok"
    best["candidates_considered"] = [name for name, _ in funcs]
    return best


def affine_signal(points: list[Rat], slope: Rat, intercept: Rat) -> list[Rat]:
    return [slope.mul(t).add(intercept) for t in points]


def quadratic_signal(points: list[Rat], a: Rat, b: Rat, c: Rat) -> list[Rat]:
    out = []
    for t in points:
        out.append(a.mul(t).mul(t).add(b.mul(t)).add(c))
    return out


def reciprocal_shift_signal(points: list[Rat], shift: Rat, scale: Rat) -> list[Rat]:
    return [scale.div(t.add(shift)) for t in points]


def d_over_a_inverse_signal(points: list[Rat]) -> list[Rat]:
    out = []
    for t in points:
        out.append(t.add(rat(1, 1)).div(t.add(rat(2, 1))))
    return out


def d_over_a_direct_signal(points: list[Rat]) -> list[Rat]:
    out = []
    for t in points:
        out.append(t.add(rat(1, 1)).div(t.mul(rat(2, 1)).add(rat(1, 1))))
    return out


def build_report(num_points: int, step_num: int, step_den: int) -> dict[str, object]:
    step = rat(step_num, step_den)
    points = sample_grid(num_points=num_points, step=step)
    datasets = [
        ("affine_3_over_2_plus_1_over_3", affine_signal(points, rat(3, 2), rat(1, 3))),
        ("reciprocal_shift_2_over_t_plus_1", reciprocal_shift_signal(points, rat(1, 1), rat(2, 1))),
        ("quadratic_1_over_2_t2_minus_1_over_3_t_plus_5_over_4", quadratic_signal(points, rat(1, 2), rat(-1, 3), rat(5, 4))),
        ("d_over_a_inverse_family_t_plus_1_over_t_plus_2", d_over_a_inverse_signal(points)),
        ("d_over_a_direct_family_t_plus_1_over_2t_plus_1", d_over_a_direct_signal(points)),
    ]
    rows = []
    for name, values in datasets:
        rows.append({"name": name, "values": [value.pair() for value in values], "best_candidate": best_candidate(values)})
    return {
        "experiment": {
            "name": "qa_fractional_projective_observable_matrix_experiment",
            "observables": ["e_over_b", "d_over_a"],
            "arithmetic": "exact_unreduced_rational_pairs",
            "floats_used": False,
            "num_points": num_points,
            "domain_step": step.pair(),
        },
        "datasets": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare exact-rational projective observer-law candidates across e/b and d/a.")
    parser.add_argument("--num-points", type=int, default=32)
    parser.add_argument("--step-num", type=int, default=1)
    parser.add_argument("--step-den", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("results/qa_fractional_projective_observable_matrix_experiment.json"))
    args = parser.parse_args()

    report = build_report(num_points=args.num_points, step_num=args.step_num, step_den=args.step_den)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {args.output}")
    for dataset in report["datasets"]:
        best = dataset["best_candidate"]
        if best.get("status") != "ok":
            print(f"{dataset['name']}: no_exact_candidate")
            continue
        summary = best["size_summary"]
        residual = best["residual_summary"]
        print(
            f"{dataset['name']}: candidate={best['candidate_name']} "
            f"all_zero={residual['all_zero']} "
            f"combined_bytes={summary['combined_bytes']} "
            f"raw_bytes={summary['raw_value_stream_bytes']}"
        )


if __name__ == "__main__":
    main()
