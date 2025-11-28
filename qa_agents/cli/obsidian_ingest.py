#!/usr/bin/env python3
"""
Obsidian Ingest v1.0

Scans an Obsidian vault (markdown) and injects actionable tasks into tasks/inbox.

Configuration:
- OB_VAULT_DIR: path to Obsidian vault (default: ./vault)
- OB_MAX_TASKS: max tasks per run (default: 10)

Task detection:
- Markdown task list items: '- [ ] Title ...' (unchecked only)
- Each task becomes a queue item with source 'obsidian:<relpath>:<lineno>'

Dedup:
- Skips titles already in inbox/active
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Set

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
INBOX = BASE / 'tasks' / 'inbox'
ACTIVE = BASE / 'tasks' / 'active'
LOGS = BASE / 'logs'
INBOX.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


def load_yaml_or_json(path: Path) -> Optional[Dict]:
    try:
        text = path.read_text(encoding='utf-8')
        return yaml.safe_load(text) if _YAML_OK else json.loads(text)
    except Exception:
        return None


def existing_titles() -> Set[str]:
    titles: Set[str] = set()
    for pool in [INBOX, ACTIVE]:
        for tf in pool.glob('*.yaml'):
            data = load_yaml_or_json(tf) or {}
            t = data.get('title')
            if t:
                titles.add(str(t))
    return titles


def _plan_for_title(title: str) -> Optional[List[str]]:
    """Generate proposed files for a task based on title keywords"""
    # Simple heuristic: if title contains certain keywords, suggest files
    title_lower = title.lower()
    plans = []
    if 'test' in title_lower or 'testing' in title_lower:
        plans.append('qa_core/tests/')
    if 'rust' in title_lower or 'backend' in title_lower:
        plans.append('src/')
        plans.append('qa_rust_ml.py')
    if 'qa' in title_lower and 'encoder' in title_lower:
        plans.append('qa_jepa_encoder.py')
    return plans if plans else None


def mk_task(title: str, relpath: Path, lineno: int) -> Dict:
    now = datetime.now().isoformat()
    tid = f"obsd-{datetime.now().strftime('%H%M%S')}-{hashlib.md5((title+str(relpath)+str(lineno)).encode('utf-8')).hexdigest()[:6]}"
    plans = _plan_for_title(title)
    rec: Dict = {
        'id': tid,
        'project': None,
        'title': title.strip(),
        'description': f'From Obsidian: {relpath}:{lineno}',
        'source': f'obsidian:{relpath}:{lineno}',
        'touches_invariants': [],
        'state': 'queued',
        'lane': 'green',
        'assignee': 'opencode' if plans else 'auto',
        'priority': 3.5 if plans else 3,
        'estimates': {'effort': 1, 'uncertainty': 2},
        'impact': {'user_value': 3, 'proof_impact': 2, 'risk_reduction': 1, 'deadline_weight': 0},
        'plan': {
            'steps': [
                {'description': 'Implement task', 'acceptance': 'Acceptance criteria met', 'tools': ['opencode','qalm'], 'effort': '1h'}
            ],
            'risks': [],
            'dependencies': [],
        },
        'metadata': {'created_at': now, 'updated_at': now, 'version': '4.0'},
    }
    if plans:
        rec['proposed_files'] = plans
    return rec


def write_task(t: Dict) -> Path:
    out = INBOX / f"{t['id']}.yaml"
    if _YAML_OK:
        with open(out, 'w') as f:
            yaml.dump(t, f, default_flow_style=False, sort_keys=False)
    else:
        out.write_text(json.dumps(t, indent=2), encoding='utf-8')
    return out


def ingest() -> Dict:
    vault = Path(os.getenv('OB_VAULT_DIR', str(BASE / 'vault')))
    max_tasks = int(os.getenv('OB_MAX_TASKS', '10'))
    if not vault.exists():
        return {'created': 0, 'note': f'vault_not_found:{vault}'}

    titles = existing_titles()
    created = 0
    task_pattern = re.compile(r"^\s*(>?)\s*[-*]\s*\[ \]\s*(.+)")  # unchecked tasks (including quoted)

    for md in sorted(vault.rglob('*.md')):
        if created >= max_tasks:
            break
        try:
            lines = md.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            m = task_pattern.match(line)
            if not m:
                continue
            title = m.group(2).strip()  # group 2 is the title now
            if not title or title in titles:
                continue
            t = mk_task(title, md.relative_to(vault), i)
            write_task(t)
            titles.add(title)
            created += 1
            if created >= max_tasks:
                break

    return {'created': created, 'vault': str(vault)}


def main() -> int:
    res = ingest()
    entry = {
        'timestamp': datetime.now().isoformat(),
        'agent': 'ObsidianIngest',
        'action': 'ingest',
        **res,
    }
    (LOGS / 'agent_runs.jsonl').write_text('', encoding='utf-8') if False else None
    with open(LOGS / 'agent_runs.jsonl', 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(json.dumps(entry))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
