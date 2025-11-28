#!/usr/bin/env python3
"""
fast_rerank_demo.py - Demonstrate fast E8 reranking on QA candidates.

Usage:
  python qa_lab/scripts/fast_rerank_demo.py [--n 1000] [--topk 32]
  Optionally set QA_E8_ROOTS_PATH or put roots at qa_lab/data/e8_roots(_unit).npy
"""
import argparse
import numpy as np
from qa_fastpath import fast_rerank_by_e8, get_e8_roots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=1000, help='number of candidates')
    ap.add_argument('--topk', type=int, default=32, help='top-k to keep')
    args = ap.parse_args()

    roots_info = get_e8_roots()
    if not roots_info:
        print('No E8 roots found. Please set QA_E8_ROOTS_PATH or place qa_lab/data/e8_roots.npy')
        return
    roots, unit_like = roots_info
    print(f'Loaded E8 roots: shape={roots.shape}, unit={unit_like}')

    rng = np.random.default_rng(0)
    b = rng.random(args.n)
    e = rng.random(args.n)
    d = b + e  # closure
    a = e + d

    idx = fast_rerank_by_e8(b, e, d, a, roots, topk=args.topk)
    print(f'Top-{len(idx)} indices (by E8 alignment):')
    print(idx[: min(20, len(idx))])

if __name__ == '__main__':
    main()

