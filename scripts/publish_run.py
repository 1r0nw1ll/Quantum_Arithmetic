"""
Auto-refactor: normalize formatting for publish_run.py
"""

#!/usr/bin/env python3
"""
Publish run artifacts:
 - Package artifacts/ and qa_data/ into releases/run-<timestamp>.tar.gz
 - Generate a concise run report with task and artifact stats
 - Append a publish.run_report event to logs/collab_events.jsonl
"""

from __future__ import annotations

import tarfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

BASE = Path(__file__).resolve().parents[1]
RELEASES = BASE / 'releases'
RELEASES.mkdir(exist_ok=True)
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)


def safe_count_completed() -> int:
    d = BASE / 'tasks' / 'completed'
    if not d.exists():
        return 0
    return sum(1 for _ in d.glob('*.yaml'))


def active_state_counts() -> Dict[str, int]:
    d = BASE / 'tasks' / 'active'
    counts: Dict[str, int] = {}
    if not d.exists():
        return counts
    for p in d.glob('*.yaml'):
        try:
            for line in p.read_text(encoding='utf-8').splitlines():
                if line.strip().startswith('state:'):
                    st = line.split(':', 1)[1].strip()
                    counts[st] = counts.get(st, 0) + 1
                    break
        except Exception:
            continue
    return counts


def read_delta() -> Dict[str, Any]:
    f = LOGS / 'artifacts_delta.json'
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}
    return {}


def make_archive(ts: str) -> str:
    out = RELEASES / f"run-{ts}.tar.gz"
    with tarfile.open(out, mode='w:gz') as tar:
        for name in ('artifacts', 'qa_data'):
            p = BASE / name
            if p.exists():
                tar.add(str(p), arcname=name)
    return str(out)


def main() -> int:
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_path = make_archive(ts)

    report = {
        'timestamp': datetime.now().isoformat(),
        'completed_count': safe_count_completed(),
        'active_state_counts': active_state_counts(),
        'artifact_archive': archive_path,
        'artifact_delta': read_delta(),
    }

    # Persist run report
    report_file = LOGS / f'run_report_{ts}.json'
    report_file.write_text(json.dumps(report, indent=2))

    # Append event line
    evt = {
        'event_type': 'publish.run_report',
        'data': report,
        'timestamp': report['timestamp'],
        'source': 'qa_lab',
    }
    with open(LOGS / 'collab_events.jsonl', 'a') as f:
        f.write(json.dumps(evt) + '\n')

    print(json.dumps({'status': 'ok', 'archive': archive_path, 'report': str(report_file)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

