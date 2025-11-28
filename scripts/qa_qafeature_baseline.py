#!/usr/bin/env python3
"""
Simple QA-feature baseline classifier on artifacts/qa_raman_features.csv.

Implements a nearest-centroid classifier per label using a small subset of QA
features. Intended as a quick sanity check for "QA alone" vs Spec-CNN.

Usage:
  python scripts/qa_qafeature_baseline.py

Outputs:
  - Prints class counts and leave-one-out accuracy (if >1 sample per class)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import math

IN_CSV = Path('artifacts/qa_raman_features.csv')


def load_rows(labels: Optional[set]) -> List[Dict[str, str]]:
    if not IN_CSV.exists():
        print(f"Missing {IN_CSV}; run scripts/qa_raman_features_to_csv.py first")
        return []
    out = []
    with open(IN_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lab = (row.get('label') or '').lower()
            if labels and lab not in labels:
                continue
            out.append(row)
    return out


def featvec(row: Dict[str, str]) -> List[float]:
    # Choose a compact feature vector from QA invariants and residues
    keys = [
        'C','F','G','J','X','K','W','Y','Z',
        'J_over_K','C_over_F','G_over_F',
        'delta12','delta23','skew',
        'C1','C2','C3','C4','C5','C1_mod24','C2_mod24','C3_mod24','C4_mod24','C5_mod24',
        'dC12_mod24','dC23_mod24','dC13_mod24',
        'C_mod24','F_mod24','C_dr9','F_dr9',
        'de_-1_rel','de_+1_rel','de_+2_rel',
        'p1_int','p2_int','p3_int','p4_int','p5_int',
        'frac1','frac2','frac3','frac4','frac5',
        'p1_over_p2','p2_over_p3','p1_over_p3','p3_over_p4','p4_over_p5',
        'p2_over_p4','p3_over_p5','p1_over_p4','p1_over_p5','p2_over_p5'
    ]
    v: List[float] = []
    for k in keys:
        try:
            v.append(float(row.get(k, '')))
        except Exception:
            v.append(0.0)
    return v


def euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def nearest_centroid_LOO(rows: List[Dict[str, str]]) -> Tuple[float, Dict[str, int], Dict[str, float]]:
    if len(rows) < 2:
        return 0.0, {}, {}

    feats = [featvec(r) for r in rows]
    # Standardize features per dimension (z-score) to avoid scale dominance
    if feats:
        d = len(feats[0])
        means = [0.0]*d
        stds = [0.0]*d
        # compute means
        for j in range(d):
            s = 0.0
            for i in range(len(feats)):
                s += feats[i][j]
            means[j] = s / len(feats)
        # compute stds
        for j in range(d):
            s2 = 0.0
            for i in range(len(feats)):
                diff = feats[i][j] - means[j]
                s2 += diff*diff
            stds[j] = (s2 / max(1, len(feats)-1)) ** 0.5
        # apply z-score (skip zero std)
        for i in range(len(feats)):
            for j in range(d):
                if stds[j] > 1e-12:
                    feats[i][j] = (feats[i][j] - means[j]) / stds[j]
    labels = [r['label'].lower() for r in rows]

    # Leave-one-out
    correct = 0
    counts: Dict[str, int] = {}
    correct_by: Dict[str, int] = {}
    for i in range(len(rows)):
        # Build centroids from all except i
        cls_to_vecs: Dict[str, List[List[float]]] = {}
        for j in range(len(rows)):
            if j == i:
                continue
            cls_to_vecs.setdefault(labels[j], []).append(feats[j])
        centroids = {c: [sum(col)/len(col) for col in zip(*vs)] for c, vs in cls_to_vecs.items() if vs}
        # Predict by nearest centroid
        f = feats[i]
        pred = min(centroids.items(), key=lambda kv: euclidean(f, kv[1]))[0]
        true = labels[i]
        if pred == true:
            correct += 1
            correct_by[true] = correct_by.get(true, 0) + 1
        counts[true] = counts.get(true, 0) + 1

    acc = correct / len(rows)
    per_class_acc = {lab: (correct_by.get(lab, 0) / n) for lab, n in counts.items()}
    return acc, counts, per_class_acc


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='', help='Comma-separated labels to include')
    args = ap.parse_args(argv)

    labels = {s.strip().lower() for s in args.labels.split(',') if s.strip()} if args.labels else None
    rows = load_rows(labels)
    if not rows:
        return
    acc, counts, pc = nearest_centroid_LOO(rows)
    print(f"Nearest-centroid LOO accuracy: {acc:.3f}")
    print(f"Class counts: {counts}")
    print(f"Per-class accuracy: {pc}")


if __name__ == '__main__':
    main()
