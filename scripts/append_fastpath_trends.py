#!/usr/bin/env python3
"""
append_fastpath_trends.py - Append latest fastpath eval metrics to trends.

Appends a timestamped snapshot of the fastpath evaluation results to
artifacts/evals/fastpath_trends.json (list of entries by date).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


EVALS = Path('artifacts/evals')
FAST = EVALS / 'fastpath_eval.json'
TRENDS = EVALS / 'fastpath_trends.json'


def main():
    EVALS.mkdir(parents=True, exist_ok=True)
    if not FAST.exists():
        return
    try:
        data = json.loads(FAST.read_text())
    except Exception:
        return
    entry = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'results': data,
    }
    if TRENDS.exists():
        try:
            arr = json.loads(TRENDS.read_text())
            if not isinstance(arr, list):
                arr = []
        except Exception:
            arr = []
    else:
        arr = []
    arr.append(entry)
    TRENDS.write_text(json.dumps(arr, indent=2))


if __name__ == '__main__':
    main()

