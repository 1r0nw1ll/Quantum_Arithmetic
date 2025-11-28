#!/usr/bin/env python3
"""
bench_qe_invariants.py - Benchmark QA invariants (Y,Z,C,F,G) Python vs Rust.

Writes qa_lab/artifacts/evals/bench_qa_invariants.json with timing and availability.
(Legacy script name kept for compatibility.)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
import sys

import numpy as np

OUT = Path('artifacts/evals/bench_qa_invariants.json')
# Ensure module import path includes repo root when invoked from outside qa_lab
BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def py_invariants(b: np.ndarray, e: np.ndarray, d: np.ndarray, a: np.ndarray):
    Y = a * a - d * d
    Z = e * e + d * a
    C = 2.0 * e * d
    F = b * a
    G = e * e + d * d
    return Y, Z, C, F, G


def main() -> None:
    # Accept new QA_* envs first; fall back to legacy QA_QE_*
    N = int(os.getenv('QA_QA_BENCH_N', os.getenv('QA_QE_BENCH_N', '200000')))
    rng = np.random.default_rng(0)
    b = rng.random(N).astype(np.float64)
    e = rng.random(N).astype(np.float64)
    d = (b + e).astype(np.float64)
    a = (e + d).astype(np.float64)

    t0 = time.perf_counter()
    Y, Z, C, F, G = py_invariants(b, e, d, a)
    t1 = time.perf_counter()

    rust_avail = False
    rust_sec = None
    scorer_avail = False
    rust_scorer_sec = None
    try:
        import qa_lab_rs as rs  # type: ignore
        # Use existing combined invariant API in Rust if available
        if hasattr(rs, 'compute_bundle_batch_numpy_py'):
            rust_avail = True
            t2 = time.perf_counter()
            r = rs.compute_bundle_batch_numpy_py(b, e, d, a)
            # r is a dict of NumPy arrays including Y,Z,C,F,G
            _ = r
            t3 = time.perf_counter()
            rust_sec = t3 - t2
        if hasattr(rs, 'qe_score_batch_numpy_py'):
            scorer_avail = True
            t4 = time.perf_counter()
            # use env-derived weights for realistic timing
            def _envf(*keys: str, default: str) -> float:
                for k in keys:
                    v = os.getenv(k)
                    if v is not None:
                        try:
                            return float(v)
                        except Exception:
                            pass
                return float(default)
            w_curv = _envf('QA_QA_CURV_WEIGHT','QA_QE_CURV_WEIGHT', default='0.25')
            w_phi = _envf('QA_QA_PHI_WEIGHT','QA_QE_PHI_WEIGHT', default='0.0')
            w_phi_eb = _envf('QA_QA_PHI_EB_WEIGHT','QA_QE_PHI_EB_WEIGHT', default='0.0')
            w_family = _envf('QA_QA_FAMILY_WEIGHT','QA_QE_FAMILY_WEIGHT', default='0.0')
            w_ideal = _envf('QA_QA_IDEAL_WEIGHT','QA_QE_IDEAL_WEIGHT', default='0.0')
            _s = rs.qe_score_batch_numpy_py(b, e, d, a, w_curv, w_phi, w_phi_eb, w_family, w_ideal)
            t5 = time.perf_counter()
            rust_scorer_sec = t5 - t4
    except Exception:
        rust_avail = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'n': N,
        'python_sec': t1 - t0,
        'rust_available': rust_avail,
        'rust_sec': rust_sec,
        'scorer_available': scorer_avail,
        'rust_scorer_sec': rust_scorer_sec,
    }, indent=2))
    print(str(OUT))


if __name__ == '__main__':
    main()
