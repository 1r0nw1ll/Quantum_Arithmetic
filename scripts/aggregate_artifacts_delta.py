"""
Auto-refactor: normalize formatting for aggregate_artifacts_delta.py
"""

#!/usr/bin/env python3
"""
Aggregate artifact deltas between runs.

Scans artifacts/ and qa_data/ for files, computes SHA-256 checksums, compares
to previous snapshot at logs/artifacts_snapshot.json, and produces a summary of
added/removed/modified files. Writes:

- logs/artifacts_snapshot.json  (new baseline)
- logs/artifacts_delta.json     (summary of this run)
- logs/collab_events.jsonl      (appends an event with event_type=publish.delta)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

BASE = Path(__file__).resolve().parents[1]
ART_DIRS = [BASE / 'artifacts', BASE / 'qa_data']
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)
SNAP_FILE = LOGS / 'artifacts_snapshot.json'
DELTA_FILE = LOGS / 'artifacts_delta.json'
EVENTS_FILE = LOGS / 'collab_events.jsonl'


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def build_index() -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for root in ART_DIRS:
        if not root.exists():
            continue
        for p in sorted(root.rglob('*')):
            if p.is_file():
                rel = str(p.relative_to(BASE))
                try:
                    index[rel] = {
                        'size': p.stat().st_size,
                        'mtime': int(p.stat().st_mtime),
                        'sha256': sha256_of(p),
                    }
                except Exception:
                    # Skip unreadable files
                    continue
    return index


def main() -> int:
    now = datetime.now().isoformat()
    current = build_index()

    prev: Dict[str, Dict[str, Any]] = {}
    if SNAP_FILE.exists():
        try:
            prev = json.loads(SNAP_FILE.read_text())
        except Exception:
            prev = {}

    prev_keys = set(prev.keys())
    cur_keys = set(current.keys())

    added = sorted(cur_keys - prev_keys)
    removed = sorted(prev_keys - cur_keys)

    modified = []
    for k in sorted(cur_keys & prev_keys):
        if prev[k].get('sha256') != current[k].get('sha256'):
            modified.append(k)

    summary = {
        'timestamp': now,
        'added_count': len(added),
        'removed_count': len(removed),
        'modified_count': len(modified),
        'added': added[:20],
        'removed': removed[:20],
        'modified': modified[:20],
    }

    # Persist outputs
    SNAP_FILE.write_text(json.dumps(current, indent=2))
    DELTA_FILE.write_text(json.dumps(summary, indent=2))

    # Append event
    evt = {
        'event_type': 'publish.delta',
        'data': summary,
        'timestamp': now,
        'source': 'qa_lab',
    }
    with open(EVENTS_FILE, 'a') as f:
        f.write(json.dumps(evt) + '\n')

    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

