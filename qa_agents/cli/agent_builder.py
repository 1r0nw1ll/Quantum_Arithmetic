"""
Auto-refactor: normalize formatting for agent_builder.py
"""

#!/usr/bin/env python3
"""
Agent Builder v1.0

Scans active tasks for agent build requests and scaffolds new agents.
Patterns:
 - Title contains: "build agent", "agent builder", "new agent"
 - Or explicit: task['agent_spec'] with {'name': '...', 'description': '...', 'events': [...]}.

Outputs:
 - Creates qa_agents/cli/<name>.py from a skeleton
 - Broadcasts builder.created event
 - Marks the task completed with execution history
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
ACTIVE = BASE / "tasks" / "active"
LOGS = BASE / "logs"
LOGS.mkdir(exist_ok=True)

import sys
sys.path.insert(0, str(BASE))
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast  # type: ignore


SKELETON = """#!/usr/bin/env python3
# Generated agent: {name}
# {description}

from datetime import datetime
import json
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast


class {class_name}:
    def __init__(self):
        self_name = "{name}"
        self.name = self_name

    def run(self):
        collab_broadcast("agent.started", {{"agent": self.name, "ts": datetime.now().isoformat()}})
        print("{name} started")


def main():
    {class_name}().run()


if __name__ == "__main__":
    main()
"""


def load_task(path: Path) -> Optional[Dict]:
    try:
        text = path.read_text(encoding="utf-8")
        return yaml.safe_load(text) if _YAML_OK else json.loads(text)
    except Exception:
        return None


def save_task(path: Path, data: Dict) -> None:
    if _YAML_OK:
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    else:
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def to_class_name(name: str) -> str:
    return re.sub(r'\W+', '', name.title())


def build_agent(spec: Dict) -> Path:
    name = spec.get('name', 'custom_agent')
    desc = spec.get('description', 'Generated agent')
    class_name = to_class_name(name)
    content = SKELETON.format(name=name, description=desc, class_name=class_name)
    out = BASE / "qa_agents" / "cli" / f"{name}.py"
    out.write_text(content, encoding="utf-8")
    try:
        out.chmod(out.stat().st_mode | 0o111)
    except Exception:
        pass
    return out


def task_matches(task: Dict) -> bool:
    title = (task.get('title') or '').lower()
    return any(k in title for k in ["build agent", "agent builder", "new agent"]) or bool(task.get('agent_spec'))


def run() -> None:
    print("🧰 Agent Builder: scanning active tasks...")
    created = 0
    for tfile in sorted(ACTIVE.glob("*.yaml")):
        task = load_task(tfile)
        if not task or not task_matches(task):
            continue

        spec = task.get('agent_spec') or {}
        if not spec.get('name'):
            # Derive from title
            base = re.sub(r'[^a-z0-9]+', '_', (task.get('title') or '').lower()).strip('_')
            spec['name'] = base or 'custom_agent'
        spec.setdefault('description', task.get('description', 'Generated agent'))

        out = build_agent(spec)
        collab_broadcast("builder.created", {"name": spec['name'], "path": str(out)})
        print(f"  • Created agent: {spec['name']} at {out}")
        created += 1

        # Mark task completed
        task.setdefault('execution', {}).setdefault('history', []).append({
            'agent': 'builder',
            'started_at': datetime.now().isoformat(),
            'completed_at': datetime.now().isoformat(),
            'result': {'status': 'ok', 'created': spec['name'], 'path': str(out)},
        })
        task['state'] = 'completed'
        task.setdefault('metadata', {})['updated_at'] = datetime.now().isoformat()
        save_task(tfile, task)

    with open(LOGS / "agent_runs.jsonl", 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'agent': 'AgentBuilder',
            'action': 'build_scan',
            'agents_created': created,
        }) + '\n')

    print(f"✅ Agent Builder complete: {created} created")


if __name__ == "__main__":
    run()
