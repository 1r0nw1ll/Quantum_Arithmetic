#!/usr/bin/env python3
"""
plot_fastpath_trends.py - Plot speedup trends over time for fast-path eval.

Reads artifacts/evals/fastpath_trends.json and produces:
  - artifacts/evals/fastpath_trends.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


EVALS = Path('artifacts/evals')
TRENDS = EVALS / 'fastpath_trends.json'
OUT = EVALS / 'fastpath_trends.png'


def main():
    EVALS.mkdir(parents=True, exist_ok=True)
    if not TRENDS.exists():
        return
    try:
        arr = json.loads(TRENDS.read_text())
    except Exception:
        return
    if not isinstance(arr, list) or not arr:
        return

    xs = [i for i, _ in enumerate(arr)]
    labels = [e.get('ts', f'run{i}') for i, e in enumerate(arr)]
    keys = ['default', 'numpy_pref', 'rust_disabled']
    series = {k: [] for k in keys}
    for e in arr:
        res = e.get('results', {})
        for k in keys:
            v = res.get(k, {})
            series[k].append(float(v.get('speedup_vs_baseline', 0.0)))

    plt.figure(figsize=(10, 5))
    for k, vals in series.items():
        if any(vals):
            plt.plot(xs, vals, marker='o', label=k)
    plt.xticks(xs, labels, rotation=45, ha='right')
    plt.ylabel('Speedup (pipeline / baseline)')
    plt.title('Fast-Path Speedup Trends')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT)


if __name__ == '__main__':
    main()

