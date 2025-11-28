"""
Auto-refactor: normalize formatting for planner.py
"""

#!/usr/bin/env python3
"""
QA Planner Agent v4.0
Creates detailed execution plans for prioritized tasks
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

class QAPlanner:
    """Task planning agent for detailed execution strategies"""

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

    def enhance_plan(self, task: Dict) -> Dict:
        """Enhance task with detailed execution plan"""
        title = task['title'].lower()

        # Generate plan based on task type
        if 'test' in title or 'pytest' in title:
            plan = {
                'steps': [
                    {
                        'description': 'Set up test environment and dependencies',
                        'acceptance': 'All required packages installed and importable',
                        'tools': ['pip', 'pytest'],
                        'effort': '30 minutes'
                    },
                    {
                        'description': 'Write comprehensive test cases covering edge cases',
                        'acceptance': 'Test coverage > 80%, all invariants verified',
                        'tools': ['pytest', 'fractions'],
                        'effort': '2 hours'
                    },
                    {
                        'description': 'Run test suite and verify all tests pass',
                        'acceptance': 'pytest returns 0 exit code, no failures',
                        'tools': ['pytest', 'make test'],
                        'effort': '15 minutes'
                    }
                ],
                'risks': [
                    'Complex rational arithmetic edge cases',
                    'Performance issues with large test matrices'
                ],
                'dependencies': []
            }

        elif 'doc' in title or 'documentation' in title:
            plan = {
                'steps': [
                    {
                        'description': 'Set up MkDocs documentation structure',
                        'acceptance': 'docs/index.md exists with basic content',
                        'tools': ['mkdocs'],
                        'effort': '30 minutes'
                    },
                    {
                        'description': 'Document all public APIs and mathematical concepts',
                        'acceptance': 'All functions/classes have docstrings and examples',
                        'tools': ['sphinx', 'doctest'],
                        'effort': '3 hours'
                    },
                    {
                        'description': 'Build and verify documentation renders correctly',
                        'acceptance': 'mkdocs build succeeds, site loads in browser',
                        'tools': ['mkdocs build'],
                        'effort': '15 minutes'
                    }
                ],
                'risks': [
                    'Outdated documentation becoming stale',
                    'Complex mathematical concepts hard to explain clearly'
                ],
                'dependencies': []
            }

        elif 'fix' in title or 'todo' in title:
            plan = {
                'steps': [
                    {
                        'description': 'Analyze the TODO/FIXME comments in codebase',
                        'acceptance': 'All TODO items identified and categorized',
                        'tools': ['grep', 'code_analysis'],
                        'effort': '30 minutes'
                    },
                    {
                        'description': 'Implement fixes for identified issues',
                        'acceptance': 'All TODO comments resolved or updated',
                        'tools': ['editor', 'pytest'],
                        'effort': '2 hours'
                    },
                    {
                        'description': 'Verify fixes work and don\'t break existing functionality',
                        'acceptance': 'Tests pass, SpecLock intact',
                        'tools': ['pytest', 'speclock'],
                        'effort': '30 minutes'
                    }
                ],
                'risks': [
                    'Fixing one TODO might introduce new issues',
                    'Some TODOs might be obsolete or no longer relevant'
                ],
                'dependencies': []
            }

        else:
            # Generic research task plan
            plan = {
                'steps': [
                    {
                        'description': 'Research and understand the problem domain',
                        'acceptance': 'Clear problem statement and success criteria defined',
                        'tools': ['literature_review', 'code_analysis'],
                        'effort': '1 hour'
                    },
                    {
                        'description': 'Design and implement solution approach',
                        'acceptance': 'Working prototype or proof of concept',
                        'tools': ['python', 'mathematical_tools'],
                        'effort': '3 hours'
                    },
                    {
                        'description': 'Test and validate the implementation',
                        'acceptance': 'All tests pass, invariants preserved',
                        'tools': ['pytest', 'validation_scripts'],
                        'effort': '1 hour'
                    }
                ],
                'risks': [
                    'Technical complexity higher than estimated',
                    'Mathematical assumptions might not hold'
                ],
                'dependencies': []
            }

        task['plan'] = plan
        task['metadata']['updated_at'] = datetime.now().isoformat()

        return task

    def plan_tasks(self) -> List[Dict]:
        """Load and enhance all active tasks with detailed plans"""
        planned_tasks = []

        for task_file in self.tasks_active.glob("*.yaml"):
            try:
                task = self.load_task(task_file)

                if task and 'plan' not in task:
                    enhanced_task = self.enhance_plan(task)

                    # Write back the enhanced task
                    if _YAML_OK:
                        with open(task_file, 'w') as f:
                            yaml.dump(enhanced_task, f, default_flow_style=False, sort_keys=False)
                    else:
                        task_file.write_text(json.dumps(enhanced_task, indent=2), encoding='utf-8')

                    planned_tasks.append(enhanced_task)
                    print(f"📋 Planned task {enhanced_task['id']}: {len(enhanced_task['plan']['steps'])} steps")

            except Exception as e:
                print(f"⚠️  Error planning task {task_file.name}: {e}")
                continue

        return planned_tasks

    def run(self):
        """Main planner execution"""
        print("📋 QA Planner: Creating execution plans...")

        planned_tasks = self.plan_tasks()

        if not planned_tasks:
            print("📭 No tasks found needing planning")
            return

        print(f"✅ Planning complete: {len(planned_tasks)} tasks enhanced with detailed plans")

        # Show summary of plans created
        for task in planned_tasks[:3]:  # Show first 3
            plan = task['plan']
            print(f"  • {task['id']}: {len(plan['steps'])} steps, {len(plan['risks'])} risks identified")

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Planner",
            "action": "task_planning",
            "tasks_planned": len(planned_tasks)
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

if __name__ == "__main__":
    planner = QAPlanner()
    planner.run()
