"""
Auto-refactor: normalize formatting for archivist.py
"""

#!/usr/bin/env python3
"""
QA Archivist Agent v4.0
Knowledge management and historical record maintenance
"""

import json
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

class QAArchivist:
    """Knowledge management agent for QA research"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_completed = self.base_dir / "tasks" / "completed"
        self.logs_dir = self.base_dir / "logs"
        self.docs_dir = self.base_dir / "qa_docs"

    def update_changelog(self, completed_tasks: List[Dict]):
        """Update CHANGELOG.md with completed tasks"""
        changelog_path = self.base_dir / "CHANGELOG.md"

        # Read existing changelog
        existing_content = ""
        if changelog_path.exists():
            with open(changelog_path, 'r') as f:
                existing_content = f.read()

        # Generate new entries
        date = datetime.now().strftime("%Y-%m-%d")
        new_entries = f"\n## [{date}]\n"

        for task in completed_tasks:
            task_id = task['id']
            title = task['title']
            assignee = task.get('assignee', 'unknown')
            score = task.get('review', {}).get('score', 'N/A')

            new_entries += f"- **{task_id}**: {title} (by {assignee}, score: {score})\n"

        # Prepend to existing content
        new_content = f"# QA Bob-iverse Changelog\n\n{new_entries}\n{existing_content}"

        with open(changelog_path, 'w') as f:
            f.write(new_content)

        print(f"📝 Updated changelog with {len(completed_tasks)} completed tasks")

    def update_run_log(self, completed_tasks: List[Dict]):
        """Update the runs documentation"""
        runs_path = self.docs_dir / "agents" / "runs.md"
        runs_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing runs
        existing_content = ""
        if runs_path.exists():
            with open(runs_path, 'r') as f:
                existing_content = f.read()

        # Generate new entries
        timestamp = datetime.now().isoformat()
        new_entries = f"\n### {timestamp}\n"

        for task in completed_tasks:
            task_id = task['id']
            title = task['title']
            assignee = task.get('assignee', 'unknown')
            lane = task.get('lane', 'unknown')
            priority = task.get('priority', 'unknown')

            new_entries += f"- **{task_id}** ({lane} lane, prio: {priority}): {title}\n"
            new_entries += f"  - Assigned to: {assignee}\n"
            new_entries += f"  - Completed: {timestamp}\n"

        # Prepend to existing content
        new_content = f"# QA Agent Runs\n\n{new_entries}\n{existing_content}"

        with open(runs_path, 'w') as f:
            f.write(new_content)

        print(f"📊 Updated runs documentation")

    def archive_completed_tasks(self) -> List[Dict]:
        """Get list of recently completed tasks"""
        completed_tasks = []

        for task_file in self.tasks_completed.glob("*.yaml"):
            try:
                text = task_file.read_text(encoding='utf-8')
                task = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                if task:
                    completed_tasks.append(task)
            except Exception as e:
                print(f"⚠️  Error reading completed task {task_file.name}: {e}")
                continue

        return completed_tasks

    def run(self):
        """Main archivist execution"""
        print("📦 QA Archivist: Updating knowledge base...")

        completed_tasks = self.archive_completed_tasks()

        if not completed_tasks:
            print("📭 No completed tasks to archive")
            return

        # Update documentation
        self.update_changelog(completed_tasks)
        self.update_run_log(completed_tasks)

        print(f"✅ Archival complete: {len(completed_tasks)} tasks documented")

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Archivist",
            "action": "knowledge_update",
            "tasks_archived": len(completed_tasks)
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Collaboration bus event
        collab_broadcast("archive.archived", {"count": len(completed_tasks)})

if __name__ == "__main__":
    archivist = QAArchivist()
    archivist.run()
