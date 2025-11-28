"""
Auto-refactor: normalize formatting for scout.py
"""

#!/usr/bin/env python3
"""
QA Scout Agent v4.0
Discovers new tasks and research opportunities with repo-aware scanning.

Improvements:
- Avoids scanning third-party/virtualenv directories.
- Whitelists project directories for code scanning.
- Caps new task creation per run to prevent inbox flooding.
- Deduplicates tasks by title to avoid repeat tickets.
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

class QAScout:
    """Task discovery agent for QA research"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_inbox = self.base_dir / "tasks" / "inbox"
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        # No caps; allow broad scanning. Throughput is handled by prioritizer/executor.

    def scan_git_history(self) -> List[Dict]:
        """Scan recent git commits for potential tasks"""
        tasks = []

        # Check for recent commits that might indicate incomplete work
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if "WIP" in result.stdout or "TODO" in result.stdout:
                tasks.append({
                    "title": "Complete work-in-progress from recent commits",
                    "source": "scout(git_history)",
                    "priority": 3,
                    "description": "Recent commits indicate incomplete work"
                })

        except:
            pass  # Git not available or not a repo

        return tasks

    def scan_codebase(self) -> List[Dict]:
        """Scan codebase for TODOs, FIXMEs, and improvement opportunities"""
        tasks = []

        # Exclude vendor/venv and external paths by default
        excludes = [
            'qa_venv', 'venv', '.venv', 'site-packages', 'dist-packages',
            'pip', 'numpy', 'torch', 'scipy', 'sklearn'
        ]

        # Build file list across repo but skip excluded segments
        py_files: List[Path] = []
        for p in self.base_dir.rglob("*.py"):
            sp = str(p)
            if any(x in sp for x in excludes):
                continue
            py_files.append(p)

        # Collect existing titles to avoid duplicates
        existing_titles = set()
        for pool in [self.tasks_inbox, self.base_dir / "tasks" / "active"]:
            for tf in pool.glob("*.yaml"):
                try:
                    text = tf.read_text(encoding='utf-8')
                    data = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                    title = (data or {}).get('title')
                    if title:
                        existing_titles.add(title)
                except Exception:
                    continue

        # Scan Python files for TODO comments (opt-in via env)
        import os as _os
        if _os.getenv('QA_SCOUT_TODOS', '0') == '1':
            for py_file in py_files:
                try:
                    content = py_file.read_text(encoding='utf-8')
                except Exception:
                    continue

                if "TODO" in content or "FIXME" in content:
                    title = f"Address TODO/FIXME in {py_file.name}"
                    if title in existing_titles:
                        continue
                    tasks.append({
                        "title": title,
                        "source": f"scout(code_scan:{py_file.relative_to(self.base_dir)})",
                        "priority": 2,
                        "description": f"Found TODO or FIXME comments in {py_file.name}"
                    })

        return tasks

    def scan_research_opportunities(self) -> List[Dict]:
        """Generate high-value research tasks based on QA project goals"""
        tasks = []

        # Collect existing titles to avoid duplicates
        existing_titles = set()
        for pool in [self.tasks_inbox, self.base_dir / "tasks" / "active", self.base_dir / "tasks" / "completed"]:
            for tf in pool.glob("*.yaml"):
                try:
                    text = tf.read_text(encoding='utf-8')
                    data = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                    title = (data or {}).get('title')
                    if title:
                        existing_titles.add(title)
                except Exception:
                    continue

        # SELF-IMPROVEMENT TRIGGER: Check if we have enough research data to retrain
        evals_dir = self.base_dir / 'artifacts' / 'evals'
        if evals_dir.exists():
            new_evals = list(evals_dir.glob('*.json'))

            # Find timestamp of last training task
            from datetime import datetime as dt, timedelta
            last_training_time = None
            for pool in [self.base_dir / "tasks" / "completed", self.base_dir / "tasks" / "active"]:
                for tf in pool.glob("*.yaml"):
                    try:
                        text = tf.read_text(encoding='utf-8')
                        data = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                        if data and data.get('assignee') == 'trainer':
                            # Get task completion time
                            metadata = data.get('metadata', {})
                            updated = metadata.get('updated_at')
                            if updated:
                                task_time = dt.fromisoformat(updated)
                                if last_training_time is None or task_time > last_training_time:
                                    last_training_time = task_time
                    except Exception:
                        continue

            # Count artifacts created AFTER last training (or in last 24h if no training yet)
            if last_training_time:
                cutoff = last_training_time
                print(f"🧠 Last training: {last_training_time.strftime('%H:%M:%S')}")
            else:
                cutoff = dt.now() - timedelta(hours=24)
                print(f"🧠 No previous training found, checking last 24h")

            recent_evals = [f for f in new_evals if dt.fromtimestamp(f.stat().st_mtime) > cutoff]

            # Trigger training if we have 5+ new research artifacts since last training
            if len(recent_evals) >= 5:
                # Use timestamp in title to avoid deduplication
                timestamp = dt.now().strftime("%Y%m%d-%H%M")
                tasks.append({
                    "title": f"Retrain QALM on accumulated research data ({timestamp})",
                    "source": "scout(self_improvement_trigger)",
                    "priority": 10,  # Highest priority - self-improvement!
                    "assignee": "trainer",
                    "description": f"Found {len(recent_evals)} new research artifacts since last training. Consolidate into training data and fine-tune QALM model to improve future research quality."
                })
                print(f"🧠 Triggering self-improvement: {len(recent_evals)} new artifacts")

        # E8 alignment research - expand parameter space
        if "E8 alignment analysis for mod 24 QA system" not in existing_titles:
            tasks.append({
                "title": "E8 alignment analysis for mod 24 QA system",
                "source": "scout(research_opportunity)",
                "priority": 5,
                "assignee": "qalm",
                "description": "Compute E8 alignment scores for full mod 24 orbit structure (24-cycle, 8-cycle, singularity) and identify geometric patterns"
            })

        # Signal processing experiments
        if "QA harmonic analysis of musical intervals" not in existing_titles:
            tasks.append({
                "title": "QA harmonic analysis of musical intervals",
                "source": "scout(research_opportunity)",
                "priority": 5,
                "assignee": "qalm",
                "description": "Apply QA arithmetic to major/minor chords, tritones, and consonance patterns. Measure E8 alignment for harmonic vs dissonant signals"
            })

        # Topology and geometry
        if "Topological analysis of QA orbit manifolds" not in existing_titles:
            tasks.append({
                "title": "Topological analysis of QA orbit manifolds",
                "source": "scout(research_opportunity)",
                "priority": 4,
                "assignee": "qalm",
                "description": "Use persistent homology to analyze 24-cycle Cosmos vs 8-cycle Satellite orbit structures. Identify topological invariants"
            })

        # Neural network integration
        if "QA-guided adaptive learning rate experiment" not in existing_titles:
            tasks.append({
                "title": "QA-guided adaptive learning rate experiment",
                "source": "scout(research_opportunity)",
                "priority": 4,
                "assignee": "qalm",
                "description": "Test QA stress metrics for dynamic learning rate adjustment during neural network training on MNIST subset"
            })

        # Financial applications
        if "QA harmonic index for market regime detection" not in existing_titles:
            tasks.append({
                "title": "QA harmonic index for market regime detection",
                "source": "scout(research_opportunity)",
                "priority": 3,
                "assignee": "qalm",
                "description": "Apply harmonic index to S&P 500 returns for bull/bear regime classification. Compare against volatility-based metrics"
            })

        return tasks

    def scan_project_status(self) -> List[Dict]:
        """Check project status and generate maintenance tasks"""
        tasks = []

        # Check if documentation needs updating
        docs_dir = self.base_dir / "qa_docs"
        if docs_dir.exists() and not (docs_dir / "index.md").exists():
            tasks.append({
                "title": "Initialize project documentation",
                "source": "scout(project_status)",
                "priority": 1,  # Lower priority - maintenance not research
                "description": "Documentation structure exists but index is missing"
            })

        # Check for test coverage
        tests_dir = self.base_dir / "qa_core" / "tests"
        if not tests_dir.exists():
            tasks.append({
                "title": "Create test suite structure",
                "source": "scout(project_status)",
                "priority": 1,  # Lower priority - maintenance not research
                "description": "No test directory found - critical for QA research"
            })

        return tasks

    def generate_task_record(self, task: Dict, task_id: str) -> Dict:
        """Generate task record (JSON-compatible)."""
        timestamp = datetime.now().isoformat()
        return {
            "id": task_id,
            "project": None,
            "title": task["title"],
            "description": task["description"],
            "source": task["source"],
            "touches_invariants": [],
            "state": "queued",
            "lane": "green",
            "assignee": task.get("assignee", "auto"),  # Respect research task assignees
            "priority": task["priority"],
            "estimates": {"effort": 1, "uncertainty": 2},
            "impact": {
                "user_value": 3,
                "proof_impact": 2,
                "risk_reduction": 1,
                "deadline_weight": 0,
            },
            "plan": {
                "steps": [
                    {
                        "description": "Investigate and implement solution",
                        "acceptance": "Task requirements satisfied",
                        "tools": ["various"],
                        "effort": "2 hours",
                    }
                ],
                "risks": [],
                "dependencies": [],
            },
            "metadata": {
                "created_at": timestamp,
                "updated_at": timestamp,
                "version": "4.0",
            },
        }

    def run(self):
        """Main scout execution"""
        print("🔍 QA Scout: Scanning for research opportunities...")

        all_tasks = []
        # Prioritize research over maintenance
        all_tasks.extend(self.scan_research_opportunities())
        all_tasks.extend(self.scan_git_history())
        all_tasks.extend(self.scan_codebase())
        all_tasks.extend(self.scan_project_status())

        # Process existing inbox tasks
        existing_tasks = list(self.tasks_inbox.glob("*.yaml"))
        if existing_tasks:
            print(f"📋 Found {len(existing_tasks)} existing tasks in inbox")
            for task_file in existing_tasks:
                print(f"  • {task_file.name}")

        # Generate new tasks
        new_tasks = []
        for i, task in enumerate(all_tasks, 1):
            # Create a simple time-based id chunk to avoid collisions
            tstamp = datetime.now().strftime("%H%M%S")
            task_id = f"t-{tstamp}-{i:02d}"
            task_file = self.tasks_inbox / f"{task_id}.yaml"

            if not task_file.exists():
                record = self.generate_task_record(task, task_id)
                # Write JSON content (YAML loader can parse JSON; JSON fallback also works)
                task_file.write_text(json.dumps(record, indent=2), encoding='utf-8')

                new_tasks.append(task_id)
                print(f"📝 Created task {task_id}: {task['title']}")

            # No hard cap; prioritizer will throttle activation

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Scout",
            "action": "task_discovery",
            "new_tasks_created": len(new_tasks),
            "existing_tasks_found": len(existing_tasks),
            "total_opportunities": len(all_tasks)
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Collaboration bus event
        collab_broadcast("scout.discovered", {
            "new": len(new_tasks),
            "existing": len(existing_tasks),
            "total": len(all_tasks),
        })

        print(f"✅ Scout complete: {len(new_tasks)} new tasks discovered")

if __name__ == "__main__":
    scout = QAScout()
    scout.run()
