#!/usr/bin/env python3
"""
Sweep k for k-NN (weighted and unweighted) on QA features.

Writes CSV with k, weighted, accuracy, and saves a PNG plot.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional
import csv

import matplotlib.pyplot as plt

from qa_knn_baseline import load_rows, knn_loo, knn_loo_weighted


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='')
    ap.add_argument('--k-list', type=str, default='1,3,5,7')
    ap.add_argument('--outfile', type=Path, default=Path('artifacts/qa_knn_sweep.csv'))
    ap.add_argument('--plot', type=Path, default=Path('artifacts/qa_knn_sweep.png'))
    args = ap.parse_args(argv)

    labels = {s.strip().lower() for s in args.labels.split(',') if s.strip()} if args.labels else None
    rows = load_rows(labels)
    if not rows:
        print('No rows; export features first or adjust labels.')
        return

    ks = [int(x) for x in args.k_list.split(',') if x.strip()]
    out = args.outfile
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['k','weighted','accuracy'])
        uw_acc = []
        wt_acc = []
        for k in ks:
            acc_u, *_ = knn_loo(rows, k=k)
            acc_w, *_ = knn_loo_weighted(rows, k=k)
            w.writerow([k, 0, f"{acc_u:.6f}"])
            w.writerow([k, 1, f"{acc_w:.6f}"])
            uw_acc.append(acc_u)
            wt_acc.append(acc_w)
    print(f"Saved sweep CSV: {out}")

    # Plot
    plt.figure(figsize=(6,4))
    plt.plot(ks, uw_acc, marker='o', label='unweighted')
    plt.plot(ks, wt_acc, marker='o', label='weighted')
    plt.xlabel('k')
    plt.ylabel('LOO accuracy')
    plt.ylim(0,1.05)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    args.plot.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.plot, dpi=150)
    print(f"Saved sweep plot: {args.plot}")


if __name__ == '__main__':
    main()

