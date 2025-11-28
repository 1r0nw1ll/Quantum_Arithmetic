#!/usr/bin/env python3
"""
Generate a one-figure QA Raman benchmark report:
  - Ablation summary (centroid + k-NN)
  - Confusion matrix (k-NN weighted)
  - Per-class accuracy bars
  - Mod-24 histograms for selected classes (C_mod24 and F_mod24)

Saves a PNG to artifacts/qa_benchmark_report.png
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import matplotlib.pyplot as plt

from qa_feature_ablation import ABLATED_SETS, ABLATED_COMBOS, load_rows as load_ablation_rows, centroid_loo, knn_loo
from qa_knn_baseline import load_rows as load_knn_rows, knn_loo_weighted

IN_CSV = Path('artifacts/qa_raman_features.csv')
OUT_PNG = Path('artifacts/qa_benchmark_report.png')


def mod24_counts(rows: List[Dict[str, str]], labels: List[str], key: str) -> Dict[str, np.ndarray]:
    out = {}
    for lab in labels:
        arr = np.zeros(24, dtype=int)
        for r in rows:
            if r.get('label','').lower() != lab:
                continue
            try:
                v = int(r.get(key) or 0)
                if 0 <= v <= 23:
                    arr[v] += 1
            except Exception:
                pass
        out[lab] = arr
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='diamond,quartz,silicon,hematite,graphite,graphene,mos2,corundum,anatase,rutile')
    ap.add_argument('--k', type=int, default=5)
    args = ap.parse_args()

    labels = [s.strip().lower() for s in args.labels.split(',') if s.strip()]

    # 1) Ablation summary on a couple of subsets (positions, residues, full)
    rows_ab = load_ablation_rows(set(labels), 'Raman')
    ab_configs = {
        'positions': ABLATED_SETS['positions'],
        'residues': ABLATED_SETS['residues'],
        'full': ABLATED_SETS['positions'] + ABLATED_SETS['intensities'] + ABLATED_SETS['qa_invariants'] + ABLATED_SETS['residues']
    }
    ab_results = []
    for name, keys in ab_configs.items():
        ca, _, _ = centroid_loo(rows_ab, keys)
        ka, _, _ = knn_loo(rows_ab, keys, k=args.k)
        ab_results.append((name, ca, ka))

    # 2) Weighted k-NN confusion matrix and per-class accuracy (full features)
    rows_knn = load_knn_rows(set(labels))
    acc, counts, pc, cm, classes = knn_loo_weighted(rows_knn, k=args.k)

    # 3) Mod-24 histograms for a few classes
    # Select top-4 frequent classes for plotting
    freq = sorted([(lab, counts.get(lab,0)) for lab in set([r['label'].lower() for r in rows_knn])], key=lambda t: -t[1])
    chosen = [lab for lab,_ in freq[:4]]
    c24 = mod24_counts(rows_knn, chosen, 'C_mod24')
    f24 = mod24_counts(rows_knn, chosen, 'F_mod24')

    # Figure layout
    plt.figure(figsize=(14, 10))

    # (A) Ablation table
    ax1 = plt.subplot2grid((3,4), (0,0), colspan=2)
    ax1.axis('off')
    table_data = [['Config','Centroid','kNN']]
    for name, ca, ka in ab_results:
        table_data.append([name, f"{ca:.3f}", f"{ka:.3f}"])
    tbl = ax1.table(cellText=table_data, loc='center')
    ax1.set_title('Ablation (LOO accuracy)')
    tbl.scale(1,1.4)

    # (B) Per-class accuracy bar chart (kNN weighted)
    ax2 = plt.subplot2grid((3,4), (0,2), colspan=2)
    order = [c for c in classes]
    vals = [pc.get(c,0.0) for c in order]
    ax2.bar(order, vals, color='steelblue')
    ax2.set_ylim(0,1.05)
    ax2.set_title(f'Per-class accuracy (kNN-w, k={args.k})')
    ax2.tick_params(axis='x', rotation=45)

    # (C) Confusion matrix
    ax3 = plt.subplot2grid((3,4), (1,0), colspan=2, rowspan=2)
    cm_arr = np.array(cm)
    im = ax3.imshow(cm_arr, cmap='viridis')
    ax3.set_xticks(np.arange(len(classes)))
    ax3.set_yticks(np.arange(len(classes)))
    ax3.set_xticklabels(classes, rotation=45, ha='right')
    ax3.set_yticklabels(classes)
    ax3.set_title(f'Confusion matrix (kNN-w, acc={acc:.3f})')
    plt.colorbar(im, ax=ax3, fraction=0.046, pad=0.04)

    # (D) Mod-24 histograms (C_mod24 and F_mod24)
    ax4 = plt.subplot2grid((3,4), (1,2))
    for lab in chosen:
        ax4.plot(c24[lab], label=lab)
    ax4.set_title('C_mod24 counts')
    ax4.legend(fontsize=8)
    ax5 = plt.subplot2grid((3,4), (1,3))
    for lab in chosen:
        ax5.plot(f24[lab], label=lab)
    ax5.set_title('F_mod24 counts')

    plt.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_PNG, dpi=150)
    print(f"Report written to {OUT_PNG}")


if __name__ == '__main__':
    main()

