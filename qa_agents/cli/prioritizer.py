"""
Auto-refactor: normalize formatting for prioritizer.py
"""

#!/usr/bin/env python3
"""
QA Prioritizer Agent v4.0
Ranks and prioritizes discovered tasks using WSJF scoring
"""

import json
import os
try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast

class QAPrioritizer:
    """Task prioritization agent using WSJF methodology"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_inbox = self.base_dir / "tasks" / "inbox"
        self.tasks_active = self.base_dir / "tasks" / "active"
        self.logs_dir = self.base_dir / "logs"
        self.tasks_active.mkdir(exist_ok=True)

    def load_task(self, task_file: Path) -> Dict:
        """Load a task from YAML or JSON file"""
        text = task_file.read_text(encoding='utf-8')
        if _YAML_OK:
            return yaml.safe_load(text)
        else:
            return json.loads(text)

    def calculate_wsjf_priority(self, task: Dict) -> float:
        """Calculate WSJF (Weighted Shortest Job First) priority score"""
        impact = task.get('impact', {})
        estimates = task.get('estimates', {})

        user_value = impact.get('user_value', 1)
        proof_impact = impact.get('proof_impact', 1)
        risk_reduction = impact.get('risk_reduction', 0)
        deadline_weight = impact.get('deadline_weight', 0)

        effort = estimates.get('effort', 1)
        uncertainty = estimates.get('uncertainty', 1)

        # WSJF formula: (Business Value + Proof Impact + Risk Reduction + Deadline) / (Effort + Uncertainty)
        numerator = user_value + proof_impact + risk_reduction + deadline_weight
        # Downweight tasks in vendor paths but keep them in the pool
        source = (task.get('source') or '').lower()
        if any(s in source for s in ['site-packages', 'dist-packages', 'qa_venv', 'venv', '.venv']):
            numerator *= 0.25
        denominator = effort + uncertainty

        return round(numerator / denominator, 2) if denominator > 0 else 0.0

    def assign_lane(self, task: Dict) -> str:
        """Assign task to appropriate approval lane"""
        touches_invariants = task.get('touches_invariants', [])

        # Red lane: touches sacred invariants
        if any(invariant in str(touches_invariants) for invariant in ['J=b·d', 'K=d·a', 'X=e·d']):
            return "red"

        # Yellow lane: code changes not touching invariants
        if "code" in task.get('title', '').lower() or "refactor" in task.get('title', '').lower():
            return "yellow"

        # Green lane: documentation, tests, analysis
        return "green"

    def prioritize_tasks(self) -> List[Dict]:
        """Load, prioritize, and sort all inbox tasks"""
        tasks = []

        for task_file in self.tasks_inbox.glob("*.yaml"):
            try:
                task = self.load_task(task_file)
                if task:
                    # Track the original filename for later removal
                    task['_source_file'] = task_file.name

                    # Calculate priority score
                    priority = self.calculate_wsjf_priority(task)

                    # Boost PIM/graph tasks (foundational pipeline work)
                    t_title = task.get('title', '').lower()
                    if any(kw in t_title for kw in [
                        'pim', 'graph', 'sector', 'spectral',
                        'community', 'kernel', 'feature map',
                    ]):
                        priority *= 1.5

                    task['priority'] = priority

                    # Assign lane
                    lane = self.assign_lane(task)
                    task['lane'] = lane

                    # Update metadata
                    task['metadata']['updated_at'] = datetime.now().isoformat()

                    tasks.append(task)

            except Exception as e:
                print(f"⚠️  Error loading task {task_file.name}: {e}")
                continue

        # Deduplicate by title, keeping highest priority
        best_by_title = {}
        for t in tasks:
            title = t.get('title', '')
            prior = best_by_title.get(title)
            if prior is None or t['priority'] > prior['priority']:
                best_by_title[title] = t
        tasks = list(best_by_title.values())

        # Sort by priority (highest first)
        tasks.sort(key=lambda t: t['priority'], reverse=True)

        return tasks

    def move_to_active(self, task: Dict):
        """Move prioritized task to active queue"""
        task_id = task.get('id', task.get('_source_file', 'unknown').replace('.yaml', ''))
        source_filename = task.get('_source_file', f"{task_id}.yaml")
        source_file = self.tasks_inbox / source_filename
        target_file = self.tasks_active / f"{task_id}.yaml"

        # Remove internal tracking field before saving
        task_copy = dict(task)
        task_copy.pop('_source_file', None)

        # Executor handoff fix: if an assignee is already set (e.g. by self_improver)
        # and state is still 'queued', flip to 'assigned' so executor picks it up.
        # Without this, tasks land in active/ but executor skips them forever.
        if task_copy.get('assignee') and task_copy.get('state', 'queued') == 'queued':
            task_copy['state'] = 'assigned'

        # Write updated task to active directory
        if _YAML_OK:
            with open(target_file, 'w') as f:
                yaml.dump(task_copy, f, default_flow_style=False, sort_keys=False)
        else:
            target_file.write_text(json.dumps(task_copy, indent=2), encoding='utf-8')

        # Remove from inbox
        if source_file.exists():
            source_file.unlink()
            print(f"📋 Activated task {task_id} (priority: {task['priority']}, lane: {task['lane']})")
        else:
            print(f"⚠️  Activated task {task_id} but source file {source_filename} not found")

    def scan_active_for_stuck_queued(self) -> int:
        """Idempotent handoff fix: scan tasks/active/ for any task that
        was moved into active/ while still in state=queued with an
        assignee set (e.g. from a pre-2026-04-05 prioritizer run that
        predated the move_to_active handoff fix, or from a direct-drop
        workflow that bypasses the inbox). Flip them to state=assigned
        so the executor will pick them up.

        Returns the number of tasks flipped.
        """
        if not self.tasks_active.exists():
            return 0
        flipped = 0
        for task_file in self.tasks_active.glob("*.yaml"):
            try:
                text = task_file.read_text(encoding="utf-8")
                task = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                if not isinstance(task, dict):
                    continue
                if task.get("assignee") and task.get("state") == "queued":
                    task["state"] = "assigned"
                    task.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()
                    if _YAML_OK:
                        with open(task_file, "w") as f:
                            yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                    else:
                        task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")
                    flipped += 1
                    print(f"  ↗ flipped {task_file.name} queued→assigned "
                          f"(assignee={task.get('assignee')})")
            except Exception as exc:
                print(f"  ⚠ failed to scan {task_file.name}: {exc}")
                continue
        return flipped

    def run(self):
        """Main prioritizer execution"""
        print("⚖️  QA Prioritizer: Ranking and prioritizing tasks...")

        # Idempotent pre-pass: fix any already-moved tasks stuck in queued.
        stuck_fixed = self.scan_active_for_stuck_queued()
        if stuck_fixed:
            print(f"📋 Unstuck {stuck_fixed} queued-with-assignee tasks in active/")

        prioritized_tasks = self.prioritize_tasks()

        if not prioritized_tasks:
            print("📭 No tasks found in inbox")
            return

        print(f"📊 Prioritized {len(prioritized_tasks)} tasks:")

        # Display top tasks
        for i, task in enumerate(prioritized_tasks[:5], 1):
            priority = task['priority']
            lane = task['lane']
            title = task.get('title', task.get('id', 'untitled'))[:60]
            if len(task.get('title', task.get('id', ''))) > 60:
                title += "..."
            print(f"  {i}. [{lane.upper()}] {priority:.2f} - {title}")

        # Move top tasks to active; capacity controlled by env var
        max_active = int(os.getenv('QA_MAX_ACTIVE', '50'))  # Increased default from 10 to 50
        active_count = 0
        for task in prioritized_tasks:
            if active_count >= max_active:
                break

            # Only activate green and yellow lane tasks automatically
            if task['lane'] in ['green', 'yellow']:
                self.move_to_active(task)
                active_count += 1

        # Flag red lane tasks for manual review
        red_lane_tasks = [t for t in prioritized_tasks if t['lane'] == 'red']
        if red_lane_tasks:
            print(f"🚨 {len(red_lane_tasks)} red-lane tasks require manual approval:")
            for task in red_lane_tasks:
                title = task.get('title', task.get('id', 'untitled'))
                print(f"  • {task['id']}: {title}")

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Prioritizer",
            "action": "task_prioritization",
            "tasks_processed": len(prioritized_tasks),
            "tasks_activated": active_count,
            "red_lane_count": len(red_lane_tasks)
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Collaboration bus event
        collab_broadcast("prioritize.activated", {
            "activated": active_count,
            "red": len(red_lane_tasks),
            "processed": len(prioritized_tasks),
        })

        print(f"✅ Prioritization complete: {active_count} tasks activated, {len(red_lane_tasks)} flagged for review")

if __name__ == "__main__":
    prioritizer = QAPrioritizer()
    prioritizer.run()
