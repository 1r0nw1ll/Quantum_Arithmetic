#!/usr/bin/env python3
"""
bench_fast_prune_stream.py - Measure streaming fast-prune performance.

Runs fast_prune_stream with configured N/chunk and records wall time to
qa_lab/artifacts/evals/bench_fast_prune_stream.json.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
import subprocess

OUT = Path('artifacts/evals/bench_fast_prune_stream.json')


def main() -> None:
    N = int(os.getenv('QA_STREAM_BENCH_N', '2000000'))
    CHUNK = int(os.getenv('QA_STREAM_BENCH_CHUNK', '200000'))
    TOPK = int(os.getenv('QA_STREAM_BENCH_TOPK', '1024'))
    # Prefer QA_* naming; fall back to legacy QE_* naming for compatibility
    QE_TOPK = int(os.getenv('QA_STREAM_BENCH_QA', os.getenv('QA_STREAM_BENCH_QE', '8192')))

    cmd = [
        'python3', 'scripts/fast_prune_stream.py',
        '--n', str(N), '--chunk', str(CHUNK),
        '--topk', str(TOPK), '--qe_topk', str(QE_TOPK),
    ]
    t0 = time.perf_counter()
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    subprocess.run(cmd, check=False, cwd=Path(__file__).resolve().parents[1], env=env)
    t1 = time.perf_counter()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'n': N,
        'chunk': CHUNK,
        'topk': TOPK,
        'qa_topk': QE_TOPK,
        'time_sec': t1 - t0,
    }, indent=2))
    print(str(OUT))


if __name__ == '__main__':
    main()
