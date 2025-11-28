#!/usr/bin/env python3
"""
K-NN baseline on QA features (framework-free).

Loads artifacts/qa_raman_features.csv, filters by labels, z-scores features,
and runs leave-one-out k-NN (k default 5) with Euclidean distance.

Prints overall accuracy, per-class accuracy, and confusion matrix.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple
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
    keys = [
        'C','F','G','J','X','K','W','Y','Z',
        'J_over_K','C_over_F','G_over_F',
        'delta12','delta23','skew',
        'C1','C2','C3','C1_mod24','C2_mod24','C3_mod24',
        'dC12_mod24','dC23_mod24','dC13_mod24',
        'C_mod24','F_mod24','C_dr9','F_dr9',
        'de_-1_rel','de_+1_rel','de_+2_rel',
        'p1_int','p2_int','p3_int','frac1','frac2','frac3','p1_over_p2','p2_over_p3','p1_over_p3'
    ]
    v: List[float] = []
    for k in keys:
        try:
            v.append(float(row.get(k, '')))
        except Exception:
            v.append(0.0)
    return v


def zscore(feats: List[List[float]]) -> None:
    if not feats:
        return
    d = len(feats[0])
    means = [0.0]*d
    stds = [0.0]*d
    n = len(feats)
    for j in range(d):
        s = 0.0
        for i in range(n):
            s += feats[i][j]
        means[j] = s / n
    for j in range(d):
        s2 = 0.0
        m = means[j]
        for i in range(n):
            diff = feats[i][j] - m
            s2 += diff*diff
        stds[j] = (s2 / max(1, n-1)) ** 0.5
    for i in range(n):
        for j in range(d):
            if stds[j] > 1e-12:
                feats[i][j] = (feats[i][j] - means[j]) / stds[j]


def euclid(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((ai - bi)**2 for ai, bi in zip(a, b)))


def knn_loo(rows: List[Dict[str, str]], k: int = 5) -> Tuple[float, Dict[str, int], Dict[str, float], List[List[int]], List[str]]:
    if len(rows) < 2:
        return 0.0, {}, {}, [], []
    feats = [featvec(r) for r in rows]
    labels = [r['label'].lower() for r in rows]
    zscore(feats)
    # Build label index map for confusion matrix
    uniq = sorted(set(labels))
    idx = {lab: i for i, lab in enumerate(uniq)}
    cm = [[0 for _ in uniq] for _ in uniq]
    counts: Dict[str, int] = {}
    correct_by: Dict[str, int] = {}
    correct = 0
    n = len(rows)
    for i in range(n):
        dists = []
        for j in range(n):
            if j == i:
                continue
            dists.append((euclid(feats[i], feats[j]), labels[j]))
        dists.sort(key=lambda t: t[0])
        nbrs = dists[:k]
        # majority vote with tie-break by closest neighbor label
        votes: Dict[str, int] = defaultdict(int)
        for _, lab in nbrs:
            votes[lab] += 1
        best = max(votes.items(), key=lambda kv: (kv[1], -1))
        # If tie in vote counts, pick closest neighbor's label
        vote_count = best[1]
        tied = [lab for lab, c in votes.items() if c == vote_count]
        if len(tied) > 1:
            for _, lab in nbrs:
                if lab in tied:
                    pred = lab
                    break
        else:
            pred = best[0]
        true = labels[i]
        if pred == true:
            correct += 1
            correct_by[true] = correct_by.get(true, 0) + 1
        counts[true] = counts.get(true, 0) + 1
        cm[idx[true]][idx[pred]] += 1
    acc = correct / n
    per_class = {lab: (correct_by.get(lab, 0) / counts.get(lab, 1)) for lab in counts}
    return acc, counts, per_class, cm, uniq


def knn_loo_weighted(rows: List[Dict[str, str]], k: int = 5) -> Tuple[float, Dict[str, int], Dict[str, float], List[List[int]], List[str]]:
    if len(rows) < 2:
        return 0.0, {}, {}, [], []
    feats = [featvec(r) for r in rows]
    labels = [r['label'].lower() for r in rows]
    zscore(feats)
    uniq = sorted(set(labels))
    idx = {lab: i for i, lab in enumerate(uniq)}
    cm = [[0 for _ in uniq] for _ in uniq]
    counts: Dict[str, int] = {}
    correct_by: Dict[str, int] = {}
    correct = 0
    n = len(rows)
    eps = 1e-9
    for i in range(n):
        dists = []
        for j in range(n):
            if j == i:
                continue
            d = euclid(feats[i], feats[j])
            w = 1.0 / (d + eps)
            dists.append((d, labels[j], w))
        dists.sort(key=lambda t: t[0])
        nbrs = dists[:k]
        weights: Dict[str, float] = defaultdict(float)
        for _, lab, w in nbrs:
            weights[lab] += w
        # choose label with max weight; tie break by highest single-neighbor weight
        maxw = max(weights.values()) if weights else 0.0
        tied = [lab for lab, w in weights.items() if abs(w - maxw) < 1e-12]
        if len(tied) == 1:
            pred = tied[0]
        else:
            # tie-break by the closest neighbor among tied labels
            pred = None
            for d, lab, w in nbrs:
                if lab in tied:
                    pred = lab
                    break
            pred = pred or tied[0]
        true = labels[i]
        if pred == true:
            correct += 1
            correct_by[true] = correct_by.get(true, 0) + 1
        counts[true] = counts.get(true, 0) + 1
        cm[idx[true]][idx[pred]] += 1
    acc = correct / n
    per_class = {lab: (correct_by.get(lab, 0) / counts.get(lab, 1)) for lab in counts}
    return acc, counts, per_class, cm, uniq


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='')
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--weighted', action='store_true', help='Use inverse-distance weighted voting')
    args = ap.parse_args(argv)

    labels = {s.strip().lower() for s in args.labels.split(',') if s.strip()} if args.labels else None
    rows = load_rows(labels)
    if not rows:
        return
    acc, counts, pc, cm, classes = knn_loo_weighted(rows, k=args.k) if args.weighted else knn_loo(rows, k=args.k)
    print(f"k-NN (k={args.k}) LOO accuracy: {acc:.3f}")
    print(f"Class counts: {counts}")
    print(f"Per-class accuracy: {pc}")
    if cm:
        print("Confusion matrix (rows=true, cols=pred):")
        header = '          ' + ' '.join(f"{c[:8]:>8s}" for c in classes)
        print(header)
        for i, lab in enumerate(classes):
            row = ' '.join(f"{cm[i][j]:>8d}" for j in range(len(classes)))
            print(f"{lab[:8]:>8s} {row}")


if __name__ == '__main__':
    main()
