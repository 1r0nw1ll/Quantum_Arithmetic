#!/usr/bin/env python3
"""
Generate C_mod24 and F_mod24 histograms from artifacts/qa_raman_features.csv.
Saves PNGs into artifacts/cm24_hist.png and artifacts/fm24_hist.png.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict
import numpy as np
import matplotlib.pyplot as plt

IN_CSV = Path('artifacts/qa_raman_features.csv')


def load_rows() -> List[Dict[str, str]]:
    if not IN_CSV.exists():
        print(f"Missing {IN_CSV}; export features first.")
        return []
    out = []
    with open(IN_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            out.append(r)
    return out


def hist_mod24(rows: List[Dict[str, str]], key: str) -> np.ndarray:
    counts = np.zeros(24, dtype=int)
    for r in rows:
        try:
            v = int(r.get(key) or 0)
            if 0 <= v <= 23:
                counts[v] += 1
        except Exception:
            continue
    return counts


def plot_hist(counts: np.ndarray, title: str, outfile: Path) -> None:
    plt.figure(figsize=(8,4))
    xs = np.arange(24)
    plt.bar(xs, counts, color='steelblue')
    plt.xticks(xs)
    plt.xlabel('Residue (mod 24)')
    plt.ylabel('Count')
    plt.title(title)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()


def main() -> None:
    rows = load_rows()
    if not rows:
        return
    cm = hist_mod24(rows, 'C_mod24')
    fm = hist_mod24(rows, 'F_mod24')
    plot_hist(cm, 'C_mod24 histogram (Raman corpus)', Path('artifacts/cm24_hist.png'))
    plot_hist(fm, 'F_mod24 histogram (Raman corpus)', Path('artifacts/fm24_hist.png'))
    print('Saved artifacts/cm24_hist.png and artifacts/fm24_hist.png')


if __name__ == '__main__':
    main()

