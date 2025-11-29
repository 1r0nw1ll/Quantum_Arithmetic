#!/usr/bin/env python3
"""Benchmark Rust vs Python for QA invariants.

Measures three paths for N elements (10x100=1000, 50x100=5000, 100x100=10000):
  1) Pure Python loop
  2) Vectorized NumPy
  3) Rust batch via PyO3 returning NumPy arrays
"""

import time
import numpy as np


def py_loop_compute(b, e, d, a):
    out = {
        'J': [], 'K': [], 'X': [], 'W': [], 'Y': [], 'Z': [], 'C': [], 'F': [], 'G': []
    }
    for bi, ei, di, ai in zip(b, e, d, a):
        X = ei * di
        K = di * ai
        out['J'].append(bi * di)
        out['K'].append(K)
        out['X'].append(X)
        out['W'].append(X + K)
        out['Y'].append(ai * ai - di * di)
        out['Z'].append(ei * ei + K)
        out['C'].append(2.0 * X)
        out['F'].append(bi * ai)
        out['G'].append(ei * ei + di * di)
    return {k: np.asarray(v, dtype=np.float64) for k, v in out.items()}


def np_vectorized_compute(b, e, d, a):
    J = b * d
    K = d * a
    X = e * d
    W = X + K
    Y = a * a - d * d
    Z = e * e + K
    C = 2.0 * X
    F = b * a
    G = e * e + d * d
    return {'J': J, 'K': K, 'X': X, 'W': W, 'Y': Y, 'Z': Z, 'C': C, 'F': F, 'G': G}


def rust_numpy_compute(b, e, d, a):
    import importlib
    rs = importlib.import_module('qa_lab_rs')
    return rs.compute_bundle_batch_numpy_py(b, e, d, a)


def bench_once(n):
    rng = np.random.default_rng(123)
    b = rng.random(n, dtype=np.float64)
    e = rng.random(n, dtype=np.float64)
    d = rng.random(n, dtype=np.float64)
    a = rng.random(n, dtype=np.float64)

    # Warmups
    _ = np_vectorized_compute(b, e, d, a)

    t0 = time.perf_counter()
    py_out = py_loop_compute(b.tolist(), e.tolist(), d.tolist(), a.tolist())
    t1 = time.perf_counter()

    t2 = time.perf_counter()
    np_out = np_vectorized_compute(b, e, d, a)
    t3 = time.perf_counter()

    try:
        t4 = time.perf_counter()
        rs_out = rust_numpy_compute(b, e, d, a)
        t5 = time.perf_counter()
        rs_time = t5 - t4
    except Exception:
        rs_out = None
        rs_time = None

    py_time = t1 - t0
    np_time = t3 - t2

    # Quick correctness check
    ok = True
    for k in ('J','K','X','W','Y','Z','C','F','G'):
        if not np.allclose(py_out[k], np_out[k], rtol=0, atol=1e-12):
            ok = False
            break
        if rs_out is not None:
            if not np.allclose(np_out[k], rs_out[k], rtol=0, atol=1e-12):
                ok = False
                break

    print(f"n={n:5d}: py_loop={py_time:.6f}s, numpy={np_time:.6f}s", end='')
    if rs_time is not None:
        speedup_vs_py = (py_time / rs_time) if rs_time > 0 else float('inf')
        print(f", rust={rs_time:.6f}s (x{speedup_vs_py:.1f} vs py_loop)")
    else:
        print(", rust=unavailable")
    return ok


def main():
    print("QA invariants Rust vs Python benchmark")
    print("- 10x100=1000, 50x100=5000, 100x100=10000 elements")
    all_ok = True
    for n in (1000, 5000, 10000):
        all_ok &= bench_once(n)
    print("OK:" if all_ok else "Mismatch detected")

    # Optional: closure scenario where d=b+e and a=e+d
    try:
        import importlib
        rs = importlib.import_module('qa_lab_rs')
        print("\nClosure scenario (d=b+e, a=e+d):")
        for n in (1000, 5000, 10000, 200000):
            rng = np.random.default_rng(42)
            b = rng.random(n, dtype=np.float64)
            e = rng.random(n, dtype=np.float64)
            d = b + e
            a = e + d
            t0 = time.perf_counter(); _ = np_vectorized_compute(b,e,d,a); t1 = time.perf_counter()
            t2 = time.perf_counter(); _ = rs.compute_bundle_batch_numpy_closure_py(b,e); t3 = time.perf_counter()
            print(f"n={n:6d}: numpy={t1-t0:.6f}s, rust-closure={t3-t2:.6f}s")
    except Exception:
        pass

    # Optional large-N run: 1,000,000 elements (enable with --large)
    import sys
    if any(arg == "--large" for arg in sys.argv[1:]):
        print("\nLarge-N (1,000,000 elements)")
        n = 1_000_000
        bench_once(n)


if __name__ == '__main__':
    main()
