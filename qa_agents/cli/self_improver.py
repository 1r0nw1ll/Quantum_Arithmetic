#!/usr/bin/env python3
"""
Self-Improver v1.0

Continuously and iteratively improves the codebase by:
- Scanning selected directories for small, safe refactors (docstring header, trailing whitespace, final newline)
- Emitting inbox tasks with proposed_files so the Executor applies them automatically
- Updating a simple capabilities registry for observability

Quality gate compatibility: tasks include proposed_files, so Executor will set
`applied_changes` and Reviewer will approve.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
ACTIVE = BASE / "tasks" / "active"
INBOX = BASE / "tasks" / "inbox"
LOGS = BASE / "logs"
CONTEXT = BASE / "context"
INBOX.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(exist_ok=True)
CONTEXT.mkdir(exist_ok=True)

SAFE_DIRS = [BASE / "qa_agents" / "cli", BASE / "projects", BASE / "scripts"]
EXCLUDES = {"qa_venv", ".venv", "venv", "site-packages", "dist-packages"}
MAX_TASKS = 5


def _read_text(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


def _has_module_docstring(text: str) -> bool:
    # Allow optional shebang on first line
    if text.startswith('#!'):
        first_nl = text.find('\n')
        if first_nl != -1:
            text = text[first_nl+1:]
    return bool(re.match(r"^\s*\"\"\"", text))


def build_refactor_patch(path: Path) -> Optional[str]:
    """Return refactored file content or None if no change needed."""
    text = _read_text(path)
    if text is None:
        return None
    original = text
    # Strip trailing spaces and normalize line endings
    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    # Ensure module docstring header
    if not _has_module_docstring(text):
        header = f'"""\nAuto-refactor: normalize formatting for {path.name}\n"""\n\n'
        text = header + text
    if text != original:
        return text
    return None


def collect_existing_titles() -> set:
    titles = set()
    for pool in [INBOX, ACTIVE]:
        for tf in pool.glob("*.yaml"):
            try:
                t = tf.read_text(encoding="utf-8")
                data = yaml.safe_load(t) if _YAML_OK else json.loads(t)
                title = (data or {}).get("title")
                if title:
                    titles.add(title)
            except Exception:
                continue
    return titles


def make_task(title: str, description: str, proposed_files: List[Dict]) -> Dict:
    now = datetime.now().isoformat()
    tid = f"t-si-{datetime.now().strftime('%H%M%S')}-{hashlib.md5(title.encode('utf-8')).hexdigest()[:6]}"
    return {
        "id": tid,
        "project": None,
        "title": title,
        "description": description,
        "source": "self_improver",
        "touches_invariants": [],
        "state": "queued",
        "lane": "green",
        "assignee": "opencode",
        "priority": 2,
        "proposed_files": proposed_files,
        "estimates": {"effort": 1, "uncertainty": 1},
        "impact": {"user_value": 3, "proof_impact": 1, "risk_reduction": 2, "deadline_weight": 0},
        "plan": {
            "steps": [
                {"description": "Apply refactor patch", "acceptance": "File normalized", "tools": ["opencode"], "effort": "5m"}
            ],
            "risks": [],
            "dependencies": [],
        },
        "metadata": {"created_at": now, "updated_at": now, "version": "4.0"},
    }


def update_capabilities_registry() -> None:
    agents = sorted(p.stem for p in (BASE / "qa_agents" / "cli").glob("*.py"))
    registry = {
        "timestamp": datetime.now().isoformat(),
        "agents": agents,
        "projects": sorted(p.name for p in (BASE / "projects").iterdir() if p.is_dir()),
    }
    (CONTEXT / "capabilities.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")


def write_task(path: Path, data: Dict) -> None:
    if _YAML_OK:
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run() -> None:
    print("🧠 Self-Improver: scanning for safe refactors...")
    existing_titles = collect_existing_titles()
    created = 0

    for root in SAFE_DIRS:
        for p in sorted(root.rglob("*.py")):
            sp = str(p)
            if any(ex in sp for ex in EXCLUDES):
                continue
            if created >= MAX_TASKS:
                break
            patched = build_refactor_patch(p)
            if not patched:
                continue
            title = f"Refactor {p.relative_to(BASE)} (normalize header/whitespace)"
            if title in existing_titles:
                continue
            task = make_task(
                title=title,
                description=f"Normalize module header/whitespace for {p}",
                proposed_files=[{"path": str(p.relative_to(BASE)), "content": patched}]
            )
            out = INBOX / f"{task['id']}.yaml"
            write_task(out, task)
            print(f"  • Created {out.name}: {title}")
            created += 1

    update_capabilities_registry()

    # Log entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": "SelfImprover",
        "action": "refactor_scan",
        "tasks_created": created,
    }
    with open(LOGS / "agent_runs.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"✅ Self-Improver complete: {created} tasks created")


if __name__ == "__main__":
    run()
