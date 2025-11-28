#!/usr/bin/env python3
"""
bench_e8_alignment.py - Lightweight E8 alignment benchmark (no external deps)

Measures end-to-end time of Rust E8 batch alignment functions on synthetic data
with the canonical 240 roots (unit-norm). Helps quantify SIMD/parallel changes.

Outputs a one-line summary and writes a JSON record to qa_lab/artifacts/evals/.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import sys
import os
import numpy as np


def load_roots_unit() -> np.ndarray:
    p = Path('qa_lab/data/e8_roots_unit.npy')
    if not p.exists():
        # Generate if missing
        import subprocess
        subprocess.run(['python3', 'scripts/generate_e8_roots.py'], check=False)
    return np.load(p)


def main() -> int:
    # Ensure local module imports work when invoked via make -C qa_lab
    sys.path.insert(0, str(Path('.').resolve()))
    # Best-effort: load .env so bench records applied env settings
    try:
        env_path = Path('.env')
        if env_path.exists():
            for raw in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass
    out_dir = Path('artifacts/evals')
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = load_roots_unit()
    if roots.shape[0] < 100:
        # try regenerating canonical 240 (correct path under qa_lab)
        import subprocess
        subprocess.run(['python3', 'scripts/generate_e8_roots.py'], check=False)
        roots = load_roots_unit()
    # Tile roots if QA_BENCH_M requests larger M (e.g., 2400)
    try:
        M_target = int(os.getenv('QA_BENCH_M', str(roots.shape[0])))
    except Exception:
        M_target = roots.shape[0]
    if M_target > roots.shape[0]:
        reps = int(np.ceil(M_target / roots.shape[0]))
        roots = np.tile(roots, (reps, 1))[:M_target]
    try:
        N = int(os.getenv('QA_BENCH_N', '200000'))
    except Exception:
        N = 200000
    rng = np.random.default_rng(123)
    b = rng.random((N, 8), dtype=np.float64)
    # Normalize vectors to keep cosines stable
    b /= (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)

    # Use high-level path that prefers Rust via qa_fastpath
    prenorm = os.getenv('QA_BENCH_PRENORM', '1') == '1'
    t0 = time.perf_counter()
    if prenorm:
        # High-level path that prefers Rust and prenorm roots
        from qa_fastpath import e8_scores_auto
        scores = e8_scores_auto(b, roots)
        _ = np.asarray(scores)
        mode = 'prenorm'
    else:
        # Directly call general (non-prenorm) Rust path
        import qa_lab_rs as rs
        scores = rs.compute_e8_alignment_batch_numpy_py(b, roots)
        _ = np.asarray(scores)
        mode = 'general'
    t1 = time.perf_counter()
    sec = t1 - t0
    rec = {
        'N': N,
        'M': int(roots.shape[0]),
        'D': int(roots.shape[1]),
        'time_sec': sec,
        'mode': mode,
        'notes': 'SIMD+Rayon path',
        'env': {
            'QA_E8_ROOT_CHUNK': os.getenv('QA_E8_ROOT_CHUNK', ''),
            'QA_E8_VEC_CHUNK': os.getenv('QA_E8_VEC_CHUNK', ''),
        }
    }
    (out_dir / 'bench_e8_alignment.json').write_text(json.dumps(rec, indent=2))
    print(f"bench_e8_alignment: N={N} M={roots.shape[0]} D={roots.shape[1]} time={sec:.3f}s")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
