#!/usr/bin/env python3
"""
bench_harmonic_index.py - Benchmark harmonic index computation (Python vs Rust).

HI = e8 * exp(-k * loss)

Outputs: qa_lab/artifacts/evals/bench_harmonic_index.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

OUT = Path('artifacts/evals/bench_harmonic_index.json')
BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def py_harmonic_index(e8: np.ndarray, loss: np.ndarray, k: float) -> np.ndarray:
    return e8 * np.exp(-k * loss)


def main() -> None:
    N = int(os.getenv('QA_HI_BENCH_N', '200000'))
    k = float(os.getenv('QA_HI_BENCH_K', '0.25'))
    rng = np.random.default_rng(0)
    e8 = rng.random(N).astype(np.float64)
    loss = rng.random(N).astype(np.float64)

    t0 = time.perf_counter()
    _p = py_harmonic_index(e8, loss, k)
    t1 = time.perf_counter()

    rust_avail = False
    rust_sec = None
    try:
        import qa_lab_rs as rs  # type: ignore
        if hasattr(rs, 'harmonic_index_batch_numpy_py'):
            rust_avail = True
            t2 = time.perf_counter()
            _r = rs.harmonic_index_batch_numpy_py(e8, loss, k)
            t3 = time.perf_counter()
            rust_sec = t3 - t2
    except Exception:
        rust_avail = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'n': N,
        'python_sec': t1 - t0,
        'rust_available': rust_avail,
        'rust_sec': rust_sec,
        'k': k,
    }, indent=2))
    print(str(OUT))


if __name__ == '__main__':
    main()

