#!/usr/bin/env python3
"""
fast_prune_stream.py - Streaming fast prune for very large N.

Demonstrates chunked processing of synthetic candidates (b,e,d,a) and
maintains a global top-k over E8 alignment scores using a heap, while
applying fast-path gates and QE pre-ranking per chunk.

Usage:
  python qa_lab/scripts/fast_prune_stream.py --n 5000000 --chunk 100000 --topk 1024 --qa_topk 8192
"""
from __future__ import annotations

import argparse
import heapq
import numpy as np
from qa_fastpath import (
    get_e8_roots, build_e8_vectors, e8_scores_auto,
    mod24_gate, digital_root_gate, closure_gate, inner_ellipse_gate, triangle_gate,
    qa_rank,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=1_000_000)
    ap.add_argument('--chunk', type=int, default=100_000)
    ap.add_argument('--topk', type=int, default=1024)
    ap.add_argument('--qe_topk', type=int, default=8192, help='QA pre-rank survivors (legacy flag name)')
    ap.add_argument('--qa_topk', type=int, dest='qe_topk', help='Alias for QA pre-rank survivors')
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()

    roots_info = get_e8_roots()
    if not roots_info:
        print('No E8 roots found; please set QA_E8_ROOTS_PATH or place roots at qa_lab/data')
        return
    roots, unit_like = roots_info
    rng = np.random.default_rng(args.seed)

    heap: list[tuple[float, int, int]] = []  # (score, chunk_idx, local_idx)
    kept_refs: list[tuple[int, int]] = []
    chunk_idx = 0
    for start in range(0, args.n, args.chunk):
        end = min(start + args.chunk, args.n)
        size = end - start
        b = rng.random(size)
        e = rng.random(size)
        d = b + e
        a = e + d
        # gates
        mask = mod24_gate(d, [1,5,7,11])
        mask &= digital_root_gate(a, [1,3,9])
        mask &= closure_gate(b, e, d, a)
        mask &= inner_ellipse_gate(b, e, d, a)
        mask &= triangle_gate(b, e, d, a)
        if not np.any(mask):
            chunk_idx += 1; continue
        # QE pre-rank
        idx_pool = np.where(mask)[0]
        scores_qe = qa_rank(b[idx_pool], e[idx_pool], d[idx_pool], a[idx_pool])
        order_qe = np.argsort(-scores_qe)
        idx_qe = idx_pool[ order_qe[: min(args.qe_topk, order_qe.shape[0])] ]
        vecs = build_e8_vectors(b[idx_qe], e[idx_qe], d[idx_qe], a[idx_qe])
        scores = e8_scores_auto(vecs, roots)
        # push to heap, keep topk
        for i, s in enumerate(scores):
            item = (float(s), chunk_idx, int(idx_qe[i]))
            if len(heap) < args.topk:
                heapq.heappush(heap, item)
            else:
                if s > heap[0][0]:
                    heapq.heapreplace(heap, item)
        chunk_idx += 1

    heap.sort(reverse=True)
    print(f"Streaming kept {len(heap)} / {args.n} (topk={args.topk})")
    print("Top 10 (score, chunk, local_idx):")
    for item in heap[:10]:
        print(item)


if __name__ == '__main__':
    main()
