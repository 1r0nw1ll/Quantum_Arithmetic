"""
Auto-refactor: normalize formatting for qa_plot_benchmarks.py
"""

#!/usr/bin/env python3
import argparse
import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt


def read_rows(path):
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            # normalize keys
            rows.append({k.strip().lower(): v for k, v in row.items()})
    return rows


def aggregate(rows):
    agg = defaultdict(lambda: {"steps": [], "compute": []})
    for row in rows:
        method = row.get("method", "").upper()
        steps = float(row.get("steps_to_tol", 0) or 0)
        # prefer explicit compute if present; else fallback to steps
        compute = float(row.get("compute_units", 0) or 0)
        agg[method]["steps"].append(steps)
        if compute:
            agg[method]["compute"].append(compute)
    # mean
    out = {}
    for m, d in agg.items():
        s = d["steps"]
        c = d["compute"] or [0.0]
        out[m] = {
            "steps_mean": sum(s) / max(len(s), 1),
            "compute_mean": sum(c) / max(len(c), 1),
        }
    return out


def plot(agg, out):
    methods = sorted(agg.keys()) or ["SGD", "HGD"]
    steps = [agg[m]["steps_mean"] for m in methods]
    compute = [agg[m]["compute_mean"] for m in methods]

    fig, axes = plt.subplots(2, 1, figsize=(7, 6), constrained_layout=True)
    axes[0].bar(methods, steps, color=["#6baed6", "#31a354"])  # blue, green
    axes[0].set_title("Steps to tolerance (mean)")
    axes[0].set_ylabel("steps")

    axes[1].bar(methods, compute, color=["#9ecae1", "#74c476"])  # lighter variants
    axes[1].set_title("Compute proxy (mean)")
    axes[1].set_ylabel("ops (proxy)")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"Wrote: {out}")


def main():
    ap = argparse.ArgumentParser(description="Plot QA vs SGD benchmark results")
    ap.add_argument("--csv", required=True, help="Path to summary.csv produced by qa_speed_benchmark")
    ap.add_argument("--out", required=True, help="Output PNG path")
    args = ap.parse_args()

    rows = read_rows(args.csv)
    agg = aggregate(rows)
    plot(agg, args.out)


if __name__ == "__main__":
    main()

