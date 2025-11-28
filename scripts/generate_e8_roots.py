#!/usr/bin/env python3
"""
generate_e8_roots.py - Generate canonical 240 E8 roots and save unit-norm rows.

The E8 root system consists of 240 vectors in R^8 of two types:
  - 112 roots: permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) with even number of minus signs
  - 128 roots: (±1/2, ..., ±1/2) eight entries, with an even number of plus signs

Both types have norm sqrt(2); we scale to unit length.

Outputs:
  qa_lab/data/e8_roots_unit.npy
"""
from __future__ import annotations

import itertools
import numpy as np
from pathlib import Path


def generate_e8_roots() -> np.ndarray:
    roots = []
    # Type I: 112 roots of form (±1, ±1, 0, 0, 0, 0, 0, 0) with all sign choices
    for i, j in itertools.combinations(range(8), 2):
        for s0 in (-1.0, 1.0):
            for s1 in (-1.0, 1.0):
                v = np.zeros(8, dtype=np.float64)
                v[i] = s0
                v[j] = s1
                roots.append(v)

    # Type II: 128 roots (±1/2, ..., ±1/2) with even number of plus signs
    for signs in itertools.product((-0.5, 0.5), repeat=8):
        plus = sum(1 for s in signs if s > 0)
        if plus % 2 == 0:
            roots.append(np.array(signs, dtype=np.float64))

    roots_arr = np.stack(roots, axis=0)
    # Normalize to unit length
    norms = np.linalg.norm(roots_arr, axis=1, keepdims=True) + 1e-12
    roots_unit = roots_arr / norms
    return roots_unit


def main():
    out_dir = Path('qa_lab/data')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'e8_roots_unit.npy'
    roots = generate_e8_roots()
    np.save(out_path, roots)
    print(f"Wrote {roots.shape[0]} unit E8 roots to {out_path}")


if __name__ == '__main__':
    main()
