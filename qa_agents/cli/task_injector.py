"""
Auto-refactor: normalize formatting for task_injector.py
"""

#!/usr/bin/env python3
"""
Task Injector

Create tasks in tasks/inbox from CLI args or JSON stdin.

Examples:
  # Simple task
  python3 qa_agents/cli/task_injector.py \
    --title "Integrate Volk Grant QA Triangle" \
    --description "Add QA Triangle module and wire into pipeline" \
    --assignee opencode --priority 3

  # With proposed files (JSON on stdin)
  cat <<'JSON' | python3 qa_agents/cli/task_injector.py --stdin
  {
    "id": "T-VOLK-TRIANGLE",
    "title": "Integrate Volk Grant QA Triangle",
    "description": "Add initial module + docs",
    "assignee": "opencode",
    "priority": 3,
    "proposed_files": [
      {"path": "projects/volk_triangle/README.md", "content": "# QA Triangle\nDesign stub."},
      {"path": "projects/volk_triangle/__init__.py", "content": "# init"}
    ]
  }
  JSON
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
INBOX = BASE / "tasks" / "inbox"
INBOX.mkdir(parents=True, exist_ok=True)


def write_yaml_or_json(path: Path, data: Dict[str, Any]) -> None:
    if _YAML_OK:
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    else:
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def inject(task: Dict[str, Any]) -> Path:
    # Fill defaults
    now = datetime.now().isoformat()
    task.setdefault('id', f"t-{datetime.now().strftime('%H%M%S')}")
    task.setdefault('project', None)
    task.setdefault('state', 'queued')
    task.setdefault('lane', 'green')
    task.setdefault('assignee', 'auto')
    task.setdefault('priority', 2)
    task.setdefault('touches_invariants', [])
    task.setdefault('impact', {'user_value': 3, 'proof_impact': 2, 'risk_reduction': 1, 'deadline_weight': 0})
    task.setdefault('estimates', {'effort': 1, 'uncertainty': 2})
    task.setdefault('metadata', {'created_at': now, 'updated_at': now, 'version': '4.0'})

    out = INBOX / f"{task['id']}.yaml"
    write_yaml_or_json(out, task)
    return out


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description='Inject a task into tasks/inbox')
    p.add_argument('--stdin', action='store_true', help='Read full task JSON from stdin')
    p.add_argument('--id')
    p.add_argument('--title')
    p.add_argument('--description')
    p.add_argument('--assignee', default='auto')
    p.add_argument('--priority', type=int, default=2)
    args = p.parse_args()

    if args.stdin:
        data = sys.stdin.read()
        task = json.loads(data)
    else:
        if not args.title:
            p.error('--title required (or use --stdin)')
        task = {
            'id': args.id or '',
            'title': args.title,
            'description': args.description or '',
            'assignee': args.assignee,
            'priority': args.priority,
        }
    # Normalize id default
    if not task.get('id'):
        task.pop('id', None)
    path = inject(task)
    print(str(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
