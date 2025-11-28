#!/usr/bin/env python3
"""
QA Swarm Introspector
Autonomous self-analysis and improvement task generation

This agent analyzes swarm performance, identifies bottlenecks,
and generates actionable improvement tasks.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class SwarmIntrospector:
    """Self-reflection and continuous improvement engine"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.logs_dir = self.base_dir / "logs"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.inbox = self.tasks_dir / "inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def load_task(self, task_file: Path) -> dict:
        """Load task from YAML/JSON"""
        try:
            text = task_file.read_text(encoding='utf-8')
            if YAML_OK:
                return yaml.safe_load(text)
            else:
                return json.loads(text)
        except Exception:
            return {}

    def save_task(self, task: dict, filename: str):
        """Save task to inbox"""
        task_file = self.inbox / filename
        if YAML_OK:
            with open(task_file, 'w') as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
        print(f"  ✅ Created introspection task: {filename}")

    def analyze_failure_patterns(self) -> List[Dict]:
        """Identify common failure patterns and generate fixes"""
        tasks = []
        failure_reasons = Counter()
        error_messages = defaultdict(list)

        # Scan active tasks for failures
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task or task.get('state') != 'failed':
                    continue

                # Extract failure reason
                review = task.get('review', {})
                feedback = review.get('feedback', [])
                if feedback:
                    reason = feedback[0]
                    failure_reasons[reason] += 1

                # Extract error messages from execution history
                hist = task.get('execution', {}).get('history', [])
                for entry in hist:
                    result = entry.get('result', {})
                    if result.get('status') == 'error':
                        error_msg = result.get('error', 'Unknown error')
                        # Truncate and normalize
                        error_key = error_msg[:100]
                        error_messages[error_key].append(task.get('id'))

        # Generate tasks for top failure patterns
        for reason, count in failure_reasons.most_common(3):
            if count >= 5:  # Only if significant pattern
                task_id = f"swarm-fix-{datetime.now().strftime('%H%M%S')}-{abs(hash(reason)) % 10000:04d}"
                task = {
                    'id': task_id,
                    'project': 'swarm_improvement',
                    'title': f'Fix common failure pattern: {reason[:50]}...',
                    'description': f'Investigate and fix the failure pattern affecting {count} tasks: {reason}',
                    'source': 'swarm_introspector',
                    'priority': min(5.0, count / 10.0),  # Higher priority for more failures
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'opencode',
                    'created': datetime.now().isoformat(),
                    'tags': ['introspection', 'bug_fix', 'high_impact'],
                    'metadata': {
                        'failure_count': count,
                        'failure_reason': reason,
                        'introspection_type': 'failure_pattern',
                    },
                    'plan': {
                        'steps': [
                            {
                                'description': 'Analyze root cause of failure pattern',
                                'acceptance': 'Root cause identified and documented',
                                'tools': ['grep', 'code_analysis'],
                                'effort': 30,
                            },
                            {
                                'description': 'Implement fix for failure pattern',
                                'acceptance': 'Fix tested and prevents recurrence',
                                'tools': ['python', 'pytest'],
                                'effort': 60,
                            },
                        ],
                        'risks': ['Fix may have unintended side effects'],
                        'dependencies': [],
                    }
                }
                tasks.append(task)

        # Generate tasks for recurring errors
        for error_msg, task_ids in list(error_messages.items())[:3]:
            if len(task_ids) >= 3:
                task_id = f"swarm-error-{datetime.now().strftime('%H%M%S')}-{abs(hash(error_msg)) % 10000:04d}"
                task = {
                    'id': task_id,
                    'project': 'swarm_improvement',
                    'title': f'Fix recurring error: {error_msg[:40]}...',
                    'description': f'Resolve error affecting {len(task_ids)} tasks: {error_msg}',
                    'source': 'swarm_introspector',
                    'priority': min(5.0, len(task_ids) / 5.0),
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'opencode',
                    'created': datetime.now().isoformat(),
                    'tags': ['introspection', 'error_fix'],
                    'metadata': {
                        'error_count': len(task_ids),
                        'affected_tasks': task_ids[:10],
                        'error_message': error_msg,
                        'introspection_type': 'recurring_error',
                    }
                }
                tasks.append(task)

        return tasks

    def analyze_performance_bottlenecks(self) -> List[Dict]:
        """Identify performance bottlenecks and optimization opportunities"""
        tasks = []

        # Check for high-backlog agents
        assignee_counts = Counter()
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if task:
                    assignee = task.get('assignee', 'unassigned')
                    if task.get('state') in ('queued', 'assigned'):
                        assignee_counts[assignee] += 1

        # Generate load-balancing tasks for overloaded agents
        for assignee, count in assignee_counts.most_common(3):
            if count > 100:  # Significant backlog
                task_id = f"swarm-balance-{datetime.now().strftime('%H%M%S')}-{abs(hash(assignee)) % 10000:04d}"
                task = {
                    'id': task_id,
                    'project': 'swarm_optimization',
                    'title': f'Load-balance tasks for {assignee} ({count} backlog)',
                    'description': f'Agent {assignee} has {count} pending tasks. Implement load balancing or parallelization.',
                    'source': 'swarm_introspector',
                    'priority': 4.0,
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'opencode',
                    'created': datetime.now().isoformat(),
                    'tags': ['introspection', 'performance', 'load_balancing'],
                    'metadata': {
                        'overloaded_agent': assignee,
                        'backlog_count': count,
                        'introspection_type': 'load_balancing',
                    }
                }
                tasks.append(task)

        # Check for slow tasks (if we have timing data)
        slow_tasks = []
        completed_dir = self.tasks_dir / "completed"
        if completed_dir.exists():
            for task_file in list(completed_dir.glob("*.yaml"))[:200]:
                task = self.load_task(task_file)
                if not task:
                    continue

                hist = task.get('execution', {}).get('history', [])
                if hist:
                    last = hist[-1]
                    started = last.get('started_at')
                    completed = last.get('completed_at')
                    if started and completed:
                        try:
                            start_dt = datetime.fromisoformat(started)
                            end_dt = datetime.fromisoformat(completed)
                            duration = (end_dt - start_dt).total_seconds()
                            if duration > 300:  # > 5 minutes
                                slow_tasks.append((task.get('id'), duration, task.get('title')))
                        except Exception:
                            pass

        # Generate optimization task for slow operations
        if len(slow_tasks) >= 5:
            avg_time = sum(t[1] for t in slow_tasks) / len(slow_tasks)
            task_id = f"swarm-optimize-{datetime.now().strftime('%H%M%S')}"
            task = {
                'id': task_id,
                'project': 'swarm_optimization',
                'title': f'Optimize slow task execution (avg {avg_time:.0f}s)',
                'description': f'Found {len(slow_tasks)} tasks taking >5min. Implement caching, parallelization, or Rust ports.',
                'source': 'swarm_introspector',
                'priority': 4.5,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'opencode',
                'created': datetime.now().isoformat(),
                'tags': ['introspection', 'performance', 'optimization'],
                'metadata': {
                    'slow_task_count': len(slow_tasks),
                    'avg_duration_sec': avg_time,
                    'sample_slow_tasks': [t[0] for t in slow_tasks[:5]],
                    'introspection_type': 'performance_optimization',
                }
            }
            tasks.append(task)

        return tasks

    def analyze_artifact_gaps(self) -> List[Dict]:
        """Identify missing or incomplete artifacts"""
        tasks = []

        # Check for tasks that should have generated plots but didn't
        completed_dir = self.tasks_dir / "completed"
        plots_dir = self.base_dir / "plots"

        missing_plots_count = 0
        if completed_dir.exists() and plots_dir.exists():
            for task_file in list(completed_dir.glob("*.yaml"))[:100]:
                task = self.load_task(task_file)
                if not task:
                    continue

                title = task.get('title', '').lower()
                task_id = task.get('id', '')

                # Should have plot if experiment/benchmark/analysis task
                should_have_plot = any(kw in title for kw in ['experiment', 'benchmark', 'analysis', 'eval'])

                if should_have_plot:
                    # Check if plot exists
                    has_plot = any(plots_dir.glob(f"*{task_id}*"))
                    if not has_plot:
                        missing_plots_count += 1

        if missing_plots_count >= 10:
            task_id = f"swarm-plots-{datetime.now().strftime('%H%M%S')}"
            task = {
                'id': task_id,
                'project': 'swarm_improvement',
                'title': f'Add visualization generation for {missing_plots_count} tasks',
                'description': f'Detected {missing_plots_count} completed experiments without plots. Implement auto-plotting.',
                'source': 'swarm_introspector',
                'priority': 3.5,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'opencode',
                'created': datetime.now().isoformat(),
                'tags': ['introspection', 'visualization', 'artifacts'],
                'metadata': {
                    'missing_plot_count': missing_plots_count,
                    'introspection_type': 'artifact_gap',
                }
            }
            tasks.append(task)

        return tasks

    def generate_health_report_task(self) -> List[Dict]:
        """Generate periodic health report task"""
        tasks = []

        # Check when last health report was generated
        logs_file = self.logs_dir / "agent_runs.jsonl"
        last_health_report = None

        if logs_file.exists():
            try:
                with open(logs_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get('action') == 'health_report':
                                last_health_report = datetime.fromisoformat(entry['timestamp'])
                        except Exception:
                            continue
            except Exception:
                pass

        # Generate health report task if >6 hours since last
        should_generate = True
        if last_health_report:
            hours_since = (datetime.now() - last_health_report).total_seconds() / 3600
            if hours_since < 6:
                should_generate = False

        if should_generate:
            task_id = f"swarm-health-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            task = {
                'id': task_id,
                'project': 'swarm_monitoring',
                'title': 'Generate swarm health and performance report',
                'description': 'Create comprehensive analysis of swarm health, performance metrics, and recommendations.',
                'source': 'swarm_introspector',
                'priority': 3.0,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'qalm',
                'created': datetime.now().isoformat(),
                'tags': ['introspection', 'monitoring', 'reporting'],
                'metadata': {
                    'report_type': 'health_analysis',
                    'introspection_type': 'health_report',
                },
                'plan': {
                    'steps': [
                        {
                            'description': 'Collect swarm metrics and performance data',
                            'acceptance': 'Metrics collected and analyzed',
                            'tools': ['swarm_dashboard'],
                            'effort': 15,
                        },
                        {
                            'description': 'Generate insights and recommendations',
                            'acceptance': 'Report with actionable recommendations',
                            'tools': ['analysis', 'visualization'],
                            'effort': 30,
                        },
                    ],
                    'risks': [],
                    'dependencies': [],
                }
            }
            tasks.append(task)

        return tasks

    def run(self):
        """Main introspection execution"""
        print("🔍 QA Swarm Introspector: Analyzing swarm health...")

        all_tasks = []

        # Run all introspection analyses
        print("\n📊 Analyzing failure patterns...")
        failure_tasks = self.analyze_failure_patterns()
        all_tasks.extend(failure_tasks)
        print(f"  Found {len(failure_tasks)} failure pattern tasks")

        print("\n⚡ Analyzing performance bottlenecks...")
        perf_tasks = self.analyze_performance_bottlenecks()
        all_tasks.extend(perf_tasks)
        print(f"  Found {len(perf_tasks)} performance optimization tasks")

        print("\n📁 Analyzing artifact gaps...")
        artifact_tasks = self.analyze_artifact_gaps()
        all_tasks.extend(artifact_tasks)
        print(f"  Found {len(artifact_tasks)} artifact gap tasks")

        print("\n🏥 Checking health report schedule...")
        health_tasks = self.generate_health_report_task()
        all_tasks.extend(health_tasks)
        print(f"  Generated {len(health_tasks)} health report tasks")

        # Save all generated tasks
        if all_tasks:
            print(f"\n✅ Generating {len(all_tasks)} introspection tasks...")
            for task in all_tasks:
                filename = f"{task['id']}.yaml"
                self.save_task(task, filename)

            # Log activity
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "agent": "SwarmIntrospector",
                "action": "introspection",
                "tasks_generated": len(all_tasks),
                "categories": {
                    "failure_patterns": len(failure_tasks),
                    "performance": len(perf_tasks),
                    "artifacts": len(artifact_tasks),
                    "health": len(health_tasks),
                }
            }

            log_file = self.logs_dir / "agent_runs.jsonl"
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

            print(f"\n🎯 Introspection complete: {len(all_tasks)} improvement tasks generated")
        else:
            print("\n✨ No introspection tasks needed - swarm is healthy!")

        return all_tasks


if __name__ == "__main__":
    introspector = SwarmIntrospector()
    introspector.run()
