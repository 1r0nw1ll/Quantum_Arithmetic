#!/usr/bin/env python3
"""
QA feature ablation study (framework-free).

Runs LOO baselines (centroid and k-NN) across multiple feature subsets on
artifacts/qa_raman_features.csv. Helps quantify which QA features drive
performance: positions, intensities, invariants, residues, etc.

Usage (example):
  python scripts/qa_feature_ablation.py \
    --labels diamond,quartz,silicon,hematite,graphite,graphene,mos2,corundum,anatase,rutile \
    --k 5 --modality Raman

Outputs: Prints a compact table with overall and per-class accuracies
for each ablation (centroid and k-NN).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import math

IN_CSV = Path('artifacts/qa_raman_features.csv')


ABLATED_SETS = {
    'positions': [
        'C1','C2','C3','delta12','delta23','skew'
    ],
    'intensities': [
        'p1_int','p2_int','p3_int','frac1','frac2','frac3','p1_over_p2','p2_over_p3','p1_over_p3'
    ],
    'qa_invariants': [
        'C','F','G','J','X','K','W','Y','Z','J_over_K','C_over_F','G_over_F'
    ],
    'residues': [
        'C_mod24','F_mod24','C_dr9','F_dr9',
        'C1_mod24','C2_mod24','C3_mod24','dC12_mod24','dC23_mod24','dC13_mod24'
    ],
}

ABLATED_COMBOS = {
    'positions+intensities': ABLATED_SETS['positions'] + ABLATED_SETS['intensities'],
    'full': ABLATED_SETS['positions'] + ABLATED_SETS['intensities'] + ABLATED_SETS['qa_invariants'] + ABLATED_SETS['residues'],
}


def load_rows(labels: Optional[set], modality: Optional[str]) -> List[Dict[str, str]]:
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
            # Mode: we assume exporter already filtered modality, but allow override
            out.append(row)
    return out


def build_featvec(row: Dict[str, str], keys: List[str]) -> List[float]:
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
        s = sum(feats[i][j] for i in range(n))
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


def centroid_loo(rows: List[Dict[str, str]], keys: List[str]) -> Tuple[float, Dict[str, int], Dict[str, float]]:
    if len(rows) < 2:
        return 0.0, {}, {}
    feats = [build_featvec(r, keys) for r in rows]
    labels = [r['label'].lower() for r in rows]
    zscore(feats)
    counts: Dict[str, int] = {}
    correct_by: Dict[str, int] = {}
    correct = 0
    n = len(rows)
    for i in range(n):
        # centroids from all except i
        cls_to_vecs: Dict[str, List[List[float]]] = defaultdict(list)
        for j in range(n):
            if j == i:
                continue
            cls_to_vecs[labels[j]].append(feats[j])
        centroids = {c: [sum(col)/len(col) for col in zip(*vs)] for c, vs in cls_to_vecs.items() if vs}
        pred = min(centroids.items(), key=lambda kv: euclid(feats[i], kv[1]))[0]
        true = labels[i]
        if pred == true:
            correct += 1
            correct_by[true] = correct_by.get(true, 0) + 1
        counts[true] = counts.get(true, 0) + 1
    acc = correct / n
    per_class = {lab: (correct_by.get(lab, 0) / counts.get(lab, 1)) for lab in counts}
    return acc, counts, per_class


def knn_loo(rows: List[Dict[str, str]], keys: List[str], k: int) -> Tuple[float, Dict[str, int], Dict[str, float]]:
    if len(rows) < 2:
        return 0.0, {}, {}
    feats = [build_featvec(r, keys) for r in rows]
    labels = [r['label'].lower() for r in rows]
    zscore(feats)
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
        votes: Dict[str, int] = defaultdict(int)
        for _, lab in nbrs:
            votes[lab] += 1
        vote_count = max(votes.values())
        tied = [lab for lab, c in votes.items() if c == vote_count]
        if len(tied) == 1:
            pred = tied[0]
        else:
            # break tie by closest neighbor among tied
            pred = None
            for _, lab in nbrs:
                if lab in tied:
                    pred = lab
                    break
            pred = pred or tied[0]
        true = labels[i]
        if pred == true:
            correct += 1
            correct_by[true] = correct_by.get(true, 0) + 1
        counts[true] = counts.get(true, 0) + 1
    acc = correct / n
    per_class = {lab: (correct_by.get(lab, 0) / counts.get(lab, 1)) for lab in counts}
    return acc, counts, per_class


def run_ablation(rows: List[Dict[str, str]], k: int, name: str, keys: List[str]) -> None:
    ca, cc, cpc = centroid_loo(rows, keys)
    ka, kc, kpc = knn_loo(rows, keys, k)
    print(f"\n=== Ablation: {name} ===")
    print(f"Centroid LOO: {ca:.3f}")
    print(f"k-NN (k={k}) LOO: {ka:.3f}")
    # Brief per-class summaries
    print(f"Per-class (k-NN): {kpc}")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='', help='comma-separated label filter')
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--modality', type=str, default='Raman')
    ap.add_argument('--save-csv', action='store_true', help='Save ablation table to artifacts/qa_ablation_table.csv')
    ap.add_argument('--save-md', action='store_true', help='Save ablation table to artifacts/qa_ablation_table.md')
    args = ap.parse_args(argv)

    labels = {s.strip().lower() for s in args.labels.split(',') if s.strip()} if args.labels else None
    rows = load_rows(labels, args.modality)
    if not rows:
        print('No rows; export features first or adjust filters.')
        return

    print(f"Rows: {len(rows)}; Labels: {sorted(set(r['label'] for r in rows))}")

    # Prepare ablation sets
    configs = {
        **ABLATED_SETS,
        **ABLATED_COMBOS,
    }

    results_rows = []  # (name, centroid_acc, knn_acc)
    for name, keys in configs.items():
        ca, _, _ = centroid_loo(rows, keys)
        ka, _, _ = knn_loo(rows, keys, k=args.k)
        results_rows.append((name, ca, ka))
        run_ablation(rows, args.k, name, keys)

    # Save tables if requested
    if args.save_csv:
        out = Path('artifacts/qa_ablation_table.csv')
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8', newline='') as f:
            f.write('config,centroid_acc,knn_acc\n')
            for name, ca, ka in results_rows:
                f.write(f"{name},{ca:.6f},{ka:.6f}\n")
        print(f"Saved CSV: {out}")

    if args.save_md:
        outm = Path('artifacts/qa_ablation_table.md')
        outm.parent.mkdir(parents=True, exist_ok=True)
        lines = ["| Config | Centroid | kNN |", "|---|---:|---:|"]
        for name, ca, ka in results_rows:
            lines.append(f"| {name} | {ca:.3f} | {ka:.3f} |")
        outm.write_text('\n'.join(lines), encoding='utf-8')
        print(f"Saved Markdown: {outm}")


if __name__ == '__main__':
    main()
