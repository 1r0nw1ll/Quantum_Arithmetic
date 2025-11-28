"""
Auto-refactor: normalize formatting for clean_backlog.py
"""

#!/usr/bin/env python3
"""
Backlog Cleaner

Moves vendor/venv-derived tasks out of active backlog to an archive folder.

Rules:
- Only targets tasks with state in {'awaiting_external','failed'}
- And whose title/source/path suggests vendor noise:
  - title contains 'TODO/FIXME' OR
  - content contains 'qa_venv' or 'site-packages' or 'dist-packages'

Destination: tasks/archive_old_vendor/
Writes a summary to stdout and logs/agent_runs.jsonl
"""

import json
from pathlib import Path
from datetime import datetime

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
ACTIVE = BASE / 'tasks' / 'active'
ARCHIVE = BASE / 'tasks' / 'archive_old_vendor'
LOGS = BASE / 'logs'
ARCHIVE.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


def load_task(path: Path):
    try:
        text = path.read_text(encoding='utf-8')
        return (yaml.safe_load(text) if _YAML_OK else json.loads(text)) or {}
    except Exception:
        return {}


def should_archive(path: Path, task: dict) -> bool:
    state = str(task.get('state', '')).lower()
    if state not in {'awaiting_external', 'failed'}:
        return False
    title = (task.get('title') or '').lower()
    source = (task.get('source') or '').lower()
    text = path.read_text(encoding='utf-8').lower()
    if 'todo/fixme' in title:
        return True
    vendor_markers = ['qa_venv', 'site-packages', 'dist-packages']
    if any(m in text or m in source for m in vendor_markers):
        return True
    return False


def main():
    moved = 0
    examined = 0
    for p in sorted(ACTIVE.glob('*.yaml')):
        task = load_task(p)
        examined += 1
        if should_archive(p, task):
            dest = ARCHIVE / p.name
            p.replace(dest)
            moved += 1
            print(f"Archived vendor backlog: {dest.name}")

    summary = {
        'timestamp': datetime.now().isoformat(),
        'agent': 'BacklogCleaner',
        'action': 'vendor_archive',
        'active_examined': examined,
        'moved': moved,
    }
    print(json.dumps(summary, indent=2))
    with open(LOGS / 'agent_runs.jsonl', 'a') as f:
        f.write(json.dumps(summary) + '\n')


if __name__ == '__main__':
    main()

