"""
Auto-refactor: normalize formatting for sanitize_tasks.py
"""

#!/usr/bin/env python3
"""
Sanitize Active Tasks v1.0

Repairs malformed YAML task files in tasks/active by:
- Removing NUL characters
- If YAML still fails, reconstructing a minimal valid record from available lines

Writes a summary and updates logs/agent_runs.jsonl.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
ACTIVE = BASE / 'tasks' / 'active'
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)


def try_load(text: str):
    try:
        return yaml.safe_load(text) if _YAML_OK else json.loads(text)
    except Exception:
        return None


def minimal_from_text(text: str, fallback_id: str) -> Dict:
    pairs = {}
    for line in text.splitlines():
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key in {'id','title','assignee','lane','state','priority'} and val:
                pairs[key] = val
    # Ensure required fields
    pairs.setdefault('id', fallback_id)
    pairs.setdefault('title', f"Recovered task {fallback_id}")
    pairs.setdefault('assignee', 'opencode')
    pairs.setdefault('lane', 'yellow')
    pairs.setdefault('state', 'failed')
    try:
        pr = float(pairs.get('priority', '2'))
    except Exception:
        pr = 2.0
    pairs['priority'] = pr
    now = datetime.now().isoformat()
    rec = {
        'id': pairs['id'],
        'project': None,
        'title': pairs['title'],
        'description': 'Recovered from malformed YAML',
        'source': 'sanitize_tasks',
        'touches_invariants': [],
        'state': pairs['state'],
        'lane': pairs['lane'],
        'assignee': pairs['assignee'],
        'priority': pairs['priority'],
        'metadata': {'created_at': now, 'updated_at': now, 'version': '4.0'},
    }
    return rec


def main() -> int:
    fixed = 0
    examined = 0
    for p in sorted(ACTIVE.glob('*.yaml')):
        examined += 1
        text = p.read_text(encoding='utf-8', errors='ignore')
        data = try_load(text)
        if data is not None:
            continue
        # Remove NULs and retry
        clean = text.replace('\x00', '')
        data = try_load(clean)
        if data is None:
            # Reconstruct minimal
            data = minimal_from_text(clean, p.stem)
        # Write back sanitized
        if _YAML_OK:
            with open(p, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        else:
            p.write_text(json.dumps(data, indent=2), encoding='utf-8')
        fixed += 1

    entry = {
        'timestamp': datetime.now().isoformat(),
        'agent': 'Sanitizer',
        'action': 'sanitize_active',
        'active_examined': examined,
        'fixed': fixed,
    }
    print(json.dumps(entry, indent=2))
    with open(LOGS / 'agent_runs.jsonl', 'a') as f:
        f.write(json.dumps(entry) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

