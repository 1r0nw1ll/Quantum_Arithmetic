#!/usr/bin/env python3
"""
Create 10 E8 benchmark test tasks for Week 1 checkpoint validation.
"""

import yaml
from datetime import datetime
from pathlib import Path

# Task template
def create_e8_task(task_num):
    return {
        "id": f"test-e8-week1-{task_num:02d}",
        "project": None,
        "title": f"E8 alignment benchmark (test {task_num}/10)",
        "description": f"Week 1 checkpoint test: Compute E8 alignments for mod 24 QA system (test task {task_num} of 10)",
        "source": "week1_checkpoint",
        "touches_invariants": [],
        "state": "queued",
        "lane": "green",
        "assignee": "e8_benchmark",
        "priority": 5.0,
        "estimates": {
            "effort": 1,
            "uncertainty": 1
        },
        "impact": {
            "user_value": 5,
            "proof_impact": 3,
            "risk_reduction": 2,
            "deadline_weight": 0
        },
        "plan": {
            "steps": [
                {
                    "description": "Compute E8 alignments for all 576 QA tuples",
                    "acceptance": "JSON artifact with 576 tuples and statistics",
                    "tools": ["e8_benchmark"],
                    "effort": "5 minutes"
                }
            ],
            "risks": [],
            "dependencies": []
        },
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "4.0"
        },
        "execution": {
            "history": []
        },
        "retry_count": 0
    }

def main():
    tasks_dir = Path("tasks/active")
    tasks_dir.mkdir(parents=True, exist_ok=True)

    print("Creating 10 E8 benchmark test tasks...")
    print("=" * 60)

    for i in range(1, 11):
        task = create_e8_task(i)
        task_file = tasks_dir / f"{task['id']}.yaml"

        with open(task_file, 'w') as f:
            yaml.dump(task, f, default_flow_style=False, sort_keys=False)

        print(f"✓ Created: {task_file.name}")

    print("=" * 60)
    print(f"✓ All 10 tasks created in {tasks_dir}/")
    print("\nTo run executor on these tasks:")
    print("  python3 qa_agents/cli/executor.py")

if __name__ == "__main__":
    main()
