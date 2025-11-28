#!/usr/bin/env python3
"""
prepare_e8_roots.py - Normalize an E8 roots file and save a unit-norm version.

Usage:
  python qa_lab/scripts/prepare_e8_roots.py --in roots.npy --out qa_lab/data/e8_roots_unit.npy
"""
import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True, help='input .npy (M,8)')
    ap.add_argument('--out', dest='out', required=True, help='output .npy (M,8) unit-norm rows')
    args = ap.parse_args()

    roots = np.load(args.inp)
    assert roots.ndim == 2 and roots.shape[1] == 8, 'expected shape (M,8)'
    norms = np.linalg.norm(roots, axis=1, keepdims=True) + 1e-12
    roots_unit = roots / norms
    np.save(args.out, roots_unit)
    print(f'Wrote unit-norm roots: {args.out} shape={roots_unit.shape}')

if __name__ == '__main__':
    main()

