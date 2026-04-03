"""
Auto-refactor: normalize formatting for dispatcher.py
"""

#!/usr/bin/env python3
"""
QA Dispatcher Agent v4.0
Assigns planned tasks to execution agents.

Enhancements:
- Supports selecting target agent via environment variable `QA_FORCE_AGENT` or `QA_DEFAULT_AGENT`.
- Recognized agents: codex, gemini, opencode, qalm.
- Optional `QA_REASSIGN_ACTIVE=1` to reassign already-assigned tasks (non-red lane).
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

class QADispatcher:
    """Task assignment agent for optimal resource allocation"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_active = self.base_dir / "tasks" / "active"
        self.logs_dir = self.base_dir / "logs"

    def load_task(self, task_file: Path) -> Dict:
        """Load a task from YAML or JSON file"""
        text = task_file.read_text(encoding='utf-8')
        if _YAML_OK:
            return yaml.safe_load(text)
        else:
            return json.loads(text)

    def assign_agent(self, task: Dict) -> str:
        """Assign task to appropriate AI agent based on requirements or override"""
        title = task['title'].lower()
        lane = task.get('lane', 'green')

        # Red lane tasks require manual assignment
        if lane == 'red':
            return 'manual'

        # Forced override via environment
        force = os.getenv('QA_FORCE_AGENT') or os.getenv('QA_DEFAULT_AGENT')
        recognized = {'codex', 'gemini', 'claude', 'opencode', 'qalm', 'qalm_multimodal', 'qalm_data_collector', 'builder'}
        if force:
            chosen = force.strip().lower()
            if chosen in recognized:
                return chosen

        # Route based on task type
        if any(keyword in title for keyword in ['code', 'implement', 'refactor', 'fix']):
            return 'opencode'  # Open code agent for code changes

        elif any(keyword in title for keyword in ['analyze', 'review', 'test', 'validate', 'evaluate']):
            # Choose analysis agent via env, default gemini; support claude
            analysis_agent = os.getenv('QA_ANALYSIS_AGENT', 'gemini').strip().lower()
            if analysis_agent not in recognized:
                analysis_agent = 'gemini'
            return analysis_agent

        elif any(keyword in title for keyword in ['build agent', 'agent builder', 'new agent']):
            return 'builder'
        elif any(keyword in title for keyword in ['multimodal', 'vision', 'audio', 'agential', 'computer use', 'tool use']):
            return 'qalm_multimodal'  # Enhanced QALM with multimodal and agential capabilities

        elif any(keyword in title for keyword in ['data collection', 'data foraging', 'collect data', 'gather data', 'dataset', 'training data']):
            return 'qalm_data_collector'  # Autonomous data collection for QALM training

        elif any(keyword in title for keyword in ['pim', 'sector', 'residue', 'kernel', 'graph', 'spectral', 'community', 'clustering', 'feature map']):
            return 'pim_kernel'  # PIM graph kernel executor

        elif any(keyword in title for keyword in ['research', 'design', 'plan', 'theorem', 'proof', 'qa', 'invariant']):
            return 'qalm'  # Local QA reasoning agent

        else:
            return 'qalm'  # Default to QALM for general tasks here

    def dispatch_tasks(self) -> List[Dict]:
        """Assign agents to all active tasks"""
        dispatched_tasks = []

        reassign = os.getenv('QA_REASSIGN_ACTIVE', '0') == '1'

        for task_file in self.tasks_active.glob("*.yaml"):
            try:
                task = self.load_task(task_file)

                if not task:
                    continue

                # Determine whether to assign or reassign
                should_assign = task.get('assignee') == 'auto'
                should_reassign = reassign and task.get('lane', 'green') != 'red'

                # Also assign tasks that have no state field yet (newly generated tasks)
                if task.get('state') is None and task.get('assignee') not in (None, 'auto', 'manual'):
                    should_assign = True

                # Also process failed tasks for retry (up to 3 retries)
                if task.get('state') == 'failed':
                    retry_count = task.get('retry_count', 0)
                    if retry_count < 3:
                        should_reassign = True
                        task['retry_count'] = retry_count + 1

                # Never (re)assign tasks that were explicitly reviewed and rejected unless overridden
                rev = (task.get('review') or {})
                if rev.get('approved') is False and os.getenv('QA_REASSIGN_REJECTED', '0') != '1':
                    should_assign = False
                    should_reassign = False

                if should_assign or should_reassign:
                    previous = task.get('assignee', 'auto')
                    assignee = self.assign_agent(task)
                    # Ensure task has an id for logging
                    if not task.get('id'):
                        task['id'] = task_file.stem
                    task['assignee'] = assignee
                    task['state'] = 'assigned'
                    # Ensure metadata exists
                    if 'metadata' not in task:
                        task['metadata'] = {}
                    task['metadata']['updated_at'] = datetime.now().isoformat()

                    # Write back the assigned task
                    if _YAML_OK:
                        with open(task_file, 'w') as f:
                            yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                    else:
                        task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')

                    dispatched_tasks.append(task)
                    action = "Reassigned" if not should_assign else "Assigned"
                    if previous != assignee or should_assign:
                        print(f"🚀 {action} {task['id']} to {assignee} (lane: {task['lane']})")

            except Exception as e:
                print(f"⚠️  Error dispatching task {task_file.name}: {e}")
                continue

        return dispatched_tasks

    def run(self):
        """Main dispatcher execution"""
        print("🚀 QA Dispatcher: Assigning tasks to agents...")

        dispatched_tasks = self.dispatch_tasks()

        if not dispatched_tasks:
            print("📭 No tasks found needing assignment")
            return

        # Group by assignee for summary
        by_assignee = {}
        for task in dispatched_tasks:
            assignee = task['assignee']
            if assignee not in by_assignee:
                by_assignee[assignee] = []
            by_assignee[assignee].append(task['id'])

        print(f"✅ Dispatch complete: {len(dispatched_tasks)} tasks assigned")

        # Show assignment summary
        for assignee, task_ids in by_assignee.items():
            print(f"  • {assignee}: {', '.join(task_ids)}")

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Dispatcher",
            "action": "task_assignment",
            "tasks_assigned": len(dispatched_tasks),
            "assignments": by_assignee
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Collaboration bus event
        collab_broadcast("dispatch.assigned", {
            "counts": {k: len(v) for k, v in by_assignee.items()},
            "total": len(dispatched_tasks),
        })

if __name__ == "__main__":
    dispatcher = QADispatcher()
    dispatcher.run()
