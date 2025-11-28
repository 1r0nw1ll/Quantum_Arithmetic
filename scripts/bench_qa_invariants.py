#!/usr/bin/env python3
"""
bench_qa_invariants.py - Alias wrapper for QE invariants benchmark under QA naming.

This invokes scripts/bench_qe_invariants.py and also writes a QA-named JSON copy:
  - artifacts/evals/bench_qe_invariants.json (primary, for compatibility)
  - artifacts/evals/bench_qa_invariants.json (QA alias)

Env vars: prefers QA_QA_* and falls back to QA_QE_* as in the source script.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def main() -> None:
    # Run the original benchmark script; it now writes QA-named artifact directly
    subprocess.run(['python3', 'scripts/bench_qe_invariants.py'], check=False)
    dst = Path('artifacts/evals/bench_qa_invariants.json')
    if dst.exists():
        print(str(dst))


if __name__ == '__main__':
    main()
