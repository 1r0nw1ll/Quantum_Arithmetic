#!/usr/bin/env python3
"""
fast_prune_pipeline.py - Demonstrate gates → QE → E8 pruning pipeline.

Usage:
  python qa_lab/scripts/fast_prune_pipeline.py --n 200000 --qa_topk 4096 --topk 256
  Optionally set QA_E8_ROOTS_PATH or put roots at qa_lab/data/e8_roots(_unit).npy
"""
import argparse, time
import numpy as np
from qa_fastpath import get_e8_roots, fast_prune_and_rank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100000, help='number of candidates')
    ap.add_argument('--qe_topk', type=int, default=4096, help='QA pre-rank survivors (legacy flag name)')
    ap.add_argument('--qa_topk', type=int, dest='qe_topk', help='Alias for QE pre-rank survivors')
    ap.add_argument('--topk', type=int, default=256, help='final top-k after E8')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--e8_chunk', type=int, default=200000)
    args = ap.parse_args()

    roots_info = get_e8_roots()
    if not roots_info:
        print('No E8 roots found. Please set QA_E8_ROOTS_PATH or place qa_lab/data/e8_roots.npy')
        return
    roots, unit = roots_info
    print(f'Loaded E8 roots: shape={roots.shape}, unit={unit}')

    rng = np.random.default_rng(args.seed)
    b = rng.random(args.n)
    e = rng.random(args.n)
    d = b + e  # closure
    a = e + d

    t0 = time.perf_counter()
    idx, scores = fast_prune_and_rank(
        b, e, d, a, roots,
        mod24_allowed=[1,5,7,11], dr_allowed=[1,3,9],
        qe_topk=args.qe_topk, topk=args.topk, e8_chunk=args.e8_chunk,
    )
    t1 = time.perf_counter()

    print(f'Pipeline kept {len(idx)}/{args.n} in {(t1-t0):.3f}s')
    print('First 20 indices:', idx[:20])
    if len(scores):
        print('Score stats: min={:.4f} mean={:.4f} max={:.4f}'.format(float(scores.min()), float(scores.mean()), float(scores.max())))

if __name__ == '__main__':
    main()
