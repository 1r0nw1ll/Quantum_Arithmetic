"""
Auto-refactor: normalize formatting for scout_collaborative.py
"""

#!/usr/bin/env python3
"""
QA Scout Agent (Collaborative Version)
Example of how to upgrade an existing agent to use real-time collaboration
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))
from qa_agent_base import CollaborativeAgent


class CollaborativeScout(CollaborativeAgent):
    """Scout agent with real-time collaboration capabilities"""

    def __init__(self):
        # Initialize collaborative agent
        super().__init__(
            name="scout",
            auto_connect=True,
            metadata={
                "role": "task_discovery",
                "capabilities": ["file_scan", "pattern_match", "ticket_parse"]
            }
        )

        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_inbox = self.base_dir / "tasks" / "inbox"
        self.tasks_inbox.mkdir(parents=True, exist_ok=True)

        # Subscribe to relevant events
        if self.connected:
            self.subscribe("request_scan")
            self.subscribe("help_needed")

            # Register event handlers
            self.on("request_scan", self.on_scan_requested)
            self.on("help_needed", self.on_help_needed)

            print(f"✅ Collaborative Scout initialized")
            print(f"   📡 Listening for: request_scan, help_needed")

    def on_scan_requested(self, data):
        """Handle scan requests from other agents"""
        requester = data.get('payload', {}).get('agent_name', 'unknown')
        context = data.get('payload', {}).get('data', {})

        print(f"📡 Scan requested by {requester}")
        print(f"   Context: {context}")

        # Run scan and broadcast results
        self.run(requested_by=requester)

    def on_help_needed(self, data):
        """Handle help requests"""
        problem = data.get('payload', {}).get('data', {}).get('problem', '')

        # Check if we can help
        if 'find' in problem.lower() or 'search' in problem.lower():
            print(f"💡 Scout can help with: {problem}")
            self.broadcast("offering_help", {
                "problem": problem,
                "capability": "search_and_discovery"
            })

    def find_tasks(self) -> List[Dict]:
        """
        Find new tasks from various sources
        (Simplified example - extend as needed)
        """
        tasks = []

        # Example: Scan for TODO/FIXME comments
        source_dirs = [
            self.base_dir / "qa_agents",
            self.base_dir / "scripts",
        ]

        for source_dir in source_dirs:
            if not source_dir.exists():
                continue

            for py_file in source_dir.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    lines = content.split('\n')

                    for i, line in enumerate(lines):
                        if 'TODO' in line or 'FIXME' in line:
                            tasks.append({
                                'id': f"TODO-{len(tasks)+1}",
                                'title': f"Address {line.strip()[:50]}...",
                                'source': str(py_file.relative_to(self.base_dir)),
                                'line': i + 1,
                                'type': 'code_improvement',
                                'priority': 'low'
                            })
                except Exception:
                    continue

        return tasks[:10]  # Limit to 10 for demo

    def write_tasks_to_files(self, tasks: List[Dict]):
        """Write tasks to inbox directory (backward compatibility)"""
        for task in tasks:
            task_file = self.tasks_inbox / f"{task['id']}.json"

            task_data = {
                **task,
                'state': 'queued',
                'assignee': 'auto',
                'lane': 'green',
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'discovered_by': 'scout'
                }
            }

            task_file.write_text(json.dumps(task_data, indent=2), encoding='utf-8')

    def run(self, requested_by: str = None):
        """Run scout agent"""
        print("🔍 QA Scout: Discovering tasks...")

        # Log activity
        if self.connected:
            self.log_activity("scan_started", {
                "requested_by": requested_by or "scheduled",
                "timestamp": datetime.now().isoformat()
            })

        # Find tasks
        tasks = self.find_tasks()

        if not tasks:
            print("   📭 No tasks found")

            if self.connected:
                self.broadcast("scan_completed", {
                    "tasks_found": 0,
                    "requested_by": requested_by
                })

            return

        print(f"   ✅ Found {len(tasks)} tasks")

        # Write to files (backward compatibility)
        self.write_tasks_to_files(tasks)

        # Broadcast discovery (real-time collaboration)
        if self.connected:
            self.broadcast("tasks_discovered", {
                "count": len(tasks),
                "tasks": [t['id'] for t in tasks],
                "summary": {
                    "code_improvement": sum(1 for t in tasks if t['type'] == 'code_improvement')
                }
            })

            # Update shared state
            self.set_state("last_scan_time", datetime.now().isoformat())
            self.set_state("last_scan_count", len(tasks))
            self.set_state("queue:inbox", [t['id'] for t in tasks])

            # Log completion
            self.log_activity("scan_completed", {
                "tasks_found": len(tasks),
                "requested_by": requested_by or "scheduled"
            })

        print(f"   📊 Tasks written to {self.tasks_inbox}")

        # Query other agents
        if self.connected:
            agents = self.query_agents()
            print(f"   👥 {len(agents)} other agents active:")
            for agent in agents[:5]:  # Show first 5
                print(f"      • {agent['name']} ({agent['status']})")


def main():
    """Run collaborative scout"""
    scout = CollaborativeScout()

    try:
        # Run initial scan
        scout.run()

        # If collaborative, keep running to handle events
        if scout.connected:
            print("\n✨ Scout running in collaborative mode")
            print("   Press Ctrl+C to stop\n")

            import time
            while True:
                time.sleep(60)  # Scan every minute
                scout.run()

        else:
            print("\nℹ️  Scout running in standalone mode (no collaboration)")

    except KeyboardInterrupt:
        print("\n")

    finally:
        scout.disconnect()


if __name__ == "__main__":
    main()
