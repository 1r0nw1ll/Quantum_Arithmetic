#!/usr/bin/env python3
"""
Compute mod-24 / mod-9 stats from artifacts/qa_raman_features.csv.

Outputs:
  - Per-class frequency tables for C_mod24 and F_mod24
  - Simple chi-squared independence test for C_mod24 vs class label

Usage:
  python scripts/qa_mod_stats.py [--labels diamond,quartz,silicon] [--min-count 20]
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Optional

import math

IN_CSV = Path('artifacts/qa_raman_features.csv')


def load_rows(labels: Optional[set]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(IN_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            lab = (r.get('label') or '').lower()
            if labels and lab not in labels:
                continue
            rows.append(r)
    return rows


def chi2_independence(table: Dict[str, Counter], bins: int = 24) -> float:
    # Build contingency matrix over labels x bins
    labels = list(table.keys())
    totals_by_label = [sum(table[l].values()) for l in labels]
    total = sum(totals_by_label)
    if total == 0:
        return 0.0
    # Column totals
    totals_by_bin = [sum(table[l][b] for l in labels) for b in range(bins)]
    # Chi-squared
    chi2 = 0.0
    for i, lab in enumerate(labels):
        for b in range(bins):
            observed = table[lab][b]
            expected = (totals_by_label[i] * totals_by_bin[b]) / total if total else 0.0
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
    return chi2


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='', help='Comma-separated class labels to include')
    ap.add_argument('--min-count', type=int, default=1, help='Minimum samples per class to report')
    args = ap.parse_args(argv)

    labels = {s.strip().lower() for s in args.labels.split(',') if s.strip()} if args.labels else None
    rows = load_rows(labels)
    if not rows:
        print('No rows found; export features first.')
        return

    # Build distributions
    c24: Dict[str, Counter] = defaultdict(Counter)
    f24: Dict[str, Counter] = defaultdict(Counter)
    counts: Counter = Counter()
    for r in rows:
        lab = (r.get('label') or '').lower()
        try:
            cm = int(r.get('C_mod24') or 0)
            fm = int(r.get('F_mod24') or 0)
        except Exception:
            continue
        counts[lab] += 1
        if 0 <= cm <= 23:
            c24[lab][cm] += 1
        if 0 <= fm <= 23:
            f24[lab][fm] += 1

    # Filter by min-count
    labels_kept = [lab for lab, n in counts.items() if n >= args.min_count]
    print(f"Classes (>= {args.min_count} samples): {labels_kept}")
    print('Sample counts:', {lab: counts[lab] for lab in labels_kept})

    # Print C_mod24 tables
    print('\nC_mod24 frequency tables:')
    for lab in labels_kept:
        row = [c24[lab][b] for b in range(24)]
        print(f"  {lab:10s} -> {row}")

    # Print F_mod24 tables
    print('\nF_mod24 frequency tables:')
    for lab in labels_kept:
        row = [f24[lab][b] for b in range(24)]
        print(f"  {lab:10s} -> {row}")

    # Chi-squared independence for C_mod24 vs class
    chi_c = chi2_independence(c24, bins=24)
    print(f"\nChi-squared (C_mod24 vs class): {chi_c:.2f} (higher suggests stronger dependence)")


if __name__ == '__main__':
    main()

