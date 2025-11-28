#!/usr/bin/env python3
"""
QA Swarm Real-Time Dashboard
Generates comprehensive metrics and visualizations for autonomous swarm health
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add parent to path for imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class SwarmDashboard:
    """Real-time metrics and visualization for QA autonomous swarm"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.logs_dir = self.base_dir / "logs"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.plots_dir = self.base_dir / "plots"
        self.plots_dir.mkdir(exist_ok=True)

    def load_task(self, task_file: Path) -> dict:
        """Load a task from YAML or JSON"""
        try:
            text = task_file.read_text(encoding='utf-8')
            if YAML_OK:
                return yaml.safe_load(text)
            else:
                return json.loads(text)
        except Exception:
            return {}

    def collect_task_metrics(self) -> dict:
        """Collect comprehensive task statistics"""
        metrics = {
            'inbox': 0,
            'active': 0,
            'completed': 0,
            'rejected': 0,
            'by_state': Counter(),
            'by_assignee': Counter(),
            'by_priority': Counter(),
            'by_lane': Counter(),
            'retry_counts': [],
            'completion_times': [],
            'task_types': Counter(),
        }

        # Count tasks by directory
        for state in ['inbox', 'active', 'completed', 'rejected']:
            task_dir = self.tasks_dir / state
            if task_dir.exists():
                count = len(list(task_dir.glob("*.yaml")))
                metrics[state] = count

        # Detailed active task analysis
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                # State distribution
                state = task.get('state', 'unknown')
                metrics['by_state'][state] += 1

                # Assignee distribution
                assignee = task.get('assignee', 'unassigned')
                metrics['by_assignee'][assignee] += 1

                # Priority distribution
                priority = task.get('priority', 0)
                priority_bucket = f"P{int(priority)}" if priority else "P0"
                metrics['by_priority'][priority_bucket] += 1

                # Lane distribution
                lane = task.get('lane', 'unknown')
                metrics['by_lane'][lane] += 1

                # Retry tracking
                retry_count = task.get('retry_count', 0)
                if retry_count > 0:
                    metrics['retry_counts'].append(retry_count)

                # Task type classification
                title = task.get('title', '').lower()
                if 'ingest' in title:
                    metrics['task_types']['ingestion'] += 1
                elif 'exp-' in title or 'experiment' in title:
                    metrics['task_types']['experiment'] += 1
                elif 'port' in title or 'rust' in title:
                    metrics['task_types']['rust_port'] += 1
                elif 'train' in title or 'qalm' in title:
                    metrics['task_types']['training'] += 1
                else:
                    metrics['task_types']['other'] += 1

        # Analyze completion times from completed tasks
        completed_dir = self.tasks_dir / "completed"
        if completed_dir.exists():
            for task_file in list(completed_dir.glob("*.yaml"))[:100]:  # Sample last 100
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
                            metrics['completion_times'].append(duration)
                        except Exception:
                            pass

        return metrics

    def collect_artifact_metrics(self) -> dict:
        """Collect artifact generation statistics"""
        metrics = {
            'plots': 0,
            'csvs': 0,
            'evals': 0,
            'proofs': 0,
            'ingestion': 0,
            'total_size_mb': 0,
        }

        # Count artifacts by type
        if (self.plots_dir).exists():
            metrics['plots'] = len(list(self.plots_dir.glob("*.png")))

        target_dir = self.base_dir / "target"
        if target_dir.exists():
            metrics['csvs'] = len(list(target_dir.rglob("*.csv")))

        artifacts_evals = self.artifacts_dir / "evals"
        if artifacts_evals.exists():
            metrics['evals'] = len(list(artifacts_evals.glob("*.json")))

        artifacts_proofs = self.artifacts_dir / "proofs"
        if artifacts_proofs.exists():
            metrics['proofs'] = len(list(artifacts_proofs.glob("*.patch")))

        artifacts_ingestion = self.artifacts_dir / "ingestion"
        if artifacts_ingestion.exists():
            metrics['ingestion'] = len(list(artifacts_ingestion.glob("*.md")))

        # Calculate total artifact size
        try:
            total_size = 0
            for dir_path in [self.plots_dir, target_dir, self.artifacts_dir]:
                if dir_path.exists():
                    for file in dir_path.rglob("*"):
                        if file.is_file():
                            total_size += file.stat().st_size
            metrics['total_size_mb'] = total_size / (1024 * 1024)
        except Exception:
            pass

        return metrics

    def collect_performance_metrics(self) -> dict:
        """Collect performance and throughput metrics"""
        metrics = {
            'daemon_uptime_hours': 0,
            'tasks_per_hour': 0,
            'avg_completion_time_sec': 0,
            'success_rate': 0,
        }

        # Check daemon uptime
        pid_file = Path("/tmp/qa_swarm_daemon.pid")
        if pid_file.exists():
            try:
                import subprocess
                result = subprocess.run(
                    ['ps', '-p', pid_file.read_text().strip(), '-o', 'etime='],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    etime = result.stdout.strip()
                    # Parse elapsed time (formats: MM:SS, HH:MM:SS, or DD-HH:MM:SS)
                    if '-' in etime:
                        days, rest = etime.split('-')
                        hours, mins, secs = rest.split(':')
                        total_hours = int(days) * 24 + int(hours) + int(mins) / 60
                    elif etime.count(':') == 2:
                        hours, mins, secs = etime.split(':')
                        total_hours = int(hours) + int(mins) / 60
                    else:
                        mins, secs = etime.split(':')
                        total_hours = int(mins) / 60
                    metrics['daemon_uptime_hours'] = round(total_hours, 2)
            except Exception:
                pass

        # Calculate throughput
        completed_dir = self.tasks_dir / "completed"
        if completed_dir.exists():
            completed_count = len(list(completed_dir.glob("*.yaml")))
            if metrics['daemon_uptime_hours'] > 0:
                metrics['tasks_per_hour'] = round(completed_count / metrics['daemon_uptime_hours'], 1)

        # Calculate success rate
        total_tasks = metrics.get('tasks_per_hour', 0) * metrics['daemon_uptime_hours']
        rejected_count = len(list((self.tasks_dir / "rejected").glob("*.yaml"))) if (self.tasks_dir / "rejected").exists() else 0
        if total_tasks > 0:
            metrics['success_rate'] = round(100 * (1 - rejected_count / total_tasks), 1)

        return metrics

    def generate_dashboard(self):
        """Generate comprehensive swarm dashboard"""
        print("📊 Generating Swarm Dashboard...")

        task_metrics = self.collect_task_metrics()
        artifact_metrics = self.collect_artifact_metrics()
        perf_metrics = self.collect_performance_metrics()

        # Create multi-panel dashboard
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('QA Autonomous Swarm Dashboard', fontsize=16, fontweight='bold')

        # 1. Task Queue Status (top left)
        ax1 = plt.subplot(3, 3, 1)
        queue_counts = [task_metrics['inbox'], task_metrics['active'],
                       task_metrics['completed'], task_metrics['rejected']]
        queue_labels = ['Inbox', 'Active', 'Completed', 'Rejected']
        colors = ['#FFA500', '#4169E1', '#32CD32', '#DC143C']
        ax1.bar(queue_labels, queue_counts, color=colors, alpha=0.7)
        ax1.set_ylabel('Task Count')
        ax1.set_title('Task Queue Status')
        ax1.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for i, (label, count) in enumerate(zip(queue_labels, queue_counts)):
            ax1.text(i, count + max(queue_counts) * 0.02, str(count),
                    ha='center', va='bottom', fontweight='bold')

        # 2. Task State Distribution (top center)
        ax2 = plt.subplot(3, 3, 2)
        if task_metrics['by_state']:
            states = list(task_metrics['by_state'].keys())
            counts = list(task_metrics['by_state'].values())
            ax2.pie(counts, labels=states, autopct='%1.1f%%', startangle=90)
            ax2.set_title('Active Task States')
        else:
            ax2.text(0.5, 0.5, 'No active tasks', ha='center', va='center')
            ax2.set_title('Active Task States')

        # 3. Assignee Distribution (top right)
        ax3 = plt.subplot(3, 3, 3)
        if task_metrics['by_assignee']:
            top_assignees = dict(task_metrics['by_assignee'].most_common(8))
            ax3.barh(list(top_assignees.keys()), list(top_assignees.values()),
                    color='#4169E1', alpha=0.7)
            ax3.set_xlabel('Task Count')
            ax3.set_title('Top Assignees (Active)')
            ax3.grid(axis='x', alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No assignments', ha='center', va='center')
            ax3.set_title('Top Assignees (Active)')

        # 4. Task Types (middle left)
        ax4 = plt.subplot(3, 3, 4)
        if task_metrics['task_types']:
            types = list(task_metrics['task_types'].keys())
            type_counts = list(task_metrics['task_types'].values())
            ax4.pie(type_counts, labels=types, autopct='%1.1f%%', startangle=45)
            ax4.set_title('Task Types (Active)')
        else:
            ax4.text(0.5, 0.5, 'No active tasks', ha='center', va='center')
            ax4.set_title('Task Types (Active)')

        # 5. Performance Metrics (middle center)
        ax5 = plt.subplot(3, 3, 5)
        ax5.axis('off')
        perf_text = f"""
SWARM PERFORMANCE

Daemon Uptime:
    {perf_metrics['daemon_uptime_hours']:.1f} hours

Throughput:
    {perf_metrics['tasks_per_hour']:.1f} tasks/hour

Total Completed:
    {task_metrics['completed']} tasks

Success Rate:
    {perf_metrics.get('success_rate', 0):.1f}%

Active Queue:
    {task_metrics['active']} tasks
        """
        ax5.text(0.1, 0.5, perf_text, fontsize=10, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # 6. Artifact Status (middle right)
        ax6 = plt.subplot(3, 3, 6)
        artifact_types = ['Plots', 'CSVs', 'Evals', 'Proofs', 'Ingestion']
        artifact_counts = [artifact_metrics['plots'], artifact_metrics['csvs'],
                          artifact_metrics['evals'], artifact_metrics['proofs'],
                          artifact_metrics['ingestion']]
        ax6.bar(artifact_types, artifact_counts, color='#32CD32', alpha=0.7)
        ax6.set_ylabel('File Count')
        ax6.set_title('Research Artifacts')
        ax6.grid(axis='y', alpha=0.3)
        ax6.tick_params(axis='x', rotation=45)

        # Add value labels
        for i, count in enumerate(artifact_counts):
            if count > 0:
                ax6.text(i, count + max(artifact_counts) * 0.02, str(count),
                        ha='center', va='bottom', fontweight='bold')

        # 7. Priority Distribution (bottom left)
        ax7 = plt.subplot(3, 3, 7)
        if task_metrics['by_priority']:
            priorities = sorted(task_metrics['by_priority'].keys())
            priority_counts = [task_metrics['by_priority'][p] for p in priorities]
            ax7.bar(priorities, priority_counts, color='#FF6347', alpha=0.7)
            ax7.set_xlabel('Priority Level')
            ax7.set_ylabel('Task Count')
            ax7.set_title('Priority Distribution (Active)')
            ax7.grid(axis='y', alpha=0.3)
        else:
            ax7.text(0.5, 0.5, 'No priorities', ha='center', va='center')
            ax7.set_title('Priority Distribution (Active)')

        # 8. Retry Analysis (bottom center)
        ax8 = plt.subplot(3, 3, 8)
        if task_metrics['retry_counts']:
            retry_hist, bins = np.histogram(task_metrics['retry_counts'], bins=range(0, 5))
            ax8.bar(range(len(retry_hist)), retry_hist, color='#FFD700', alpha=0.7)
            ax8.set_xlabel('Retry Count')
            ax8.set_ylabel('Task Count')
            ax8.set_title('Task Retry Distribution')
            ax8.set_xticks(range(len(retry_hist)))
            ax8.set_xticklabels([f"{i}" for i in range(len(retry_hist))])
            ax8.grid(axis='y', alpha=0.3)
        else:
            ax8.text(0.5, 0.5, 'No retries tracked', ha='center', va='center')
            ax8.set_title('Task Retry Distribution')

        # 9. System Health Summary (bottom right)
        ax9 = plt.subplot(3, 3, 9)
        ax9.axis('off')

        # Calculate health score
        health_score = 100
        if task_metrics['active'] > 1000:
            health_score -= 20  # High backlog
        if task_metrics['rejected'] > task_metrics['completed'] * 0.1:
            health_score -= 15  # High rejection rate
        if perf_metrics['daemon_uptime_hours'] == 0:
            health_score -= 30  # Daemon not running
        if task_metrics['by_state'].get('failed', 0) > 100:
            health_score -= 15  # Many failed tasks

        health_emoji = '🟢' if health_score >= 80 else '🟡' if health_score >= 60 else '🔴'

        health_text = f"""
{health_emoji} SYSTEM HEALTH

Health Score: {health_score}/100

Artifacts Generated:
    {sum(artifact_counts)} files
    {artifact_metrics['total_size_mb']:.1f} MB

Failed Tasks:
    {task_metrics['by_state'].get('failed', 0)}

Queued Tasks:
    {task_metrics['by_state'].get('queued', 0)}

Status: {'EXCELLENT' if health_score >= 80 else 'GOOD' if health_score >= 60 else 'NEEDS ATTENTION'}
        """
        ax9.text(0.1, 0.5, health_text, fontsize=10, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round',
                facecolor='lightgreen' if health_score >= 80 else 'yellow' if health_score >= 60 else 'lightcoral',
                alpha=0.5))

        plt.tight_layout()

        # Save dashboard
        output_file = self.plots_dir / f"swarm_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✅ Dashboard saved: {output_file}")

        # Also save latest
        latest_file = self.plots_dir / "swarm_dashboard_latest.png"
        plt.savefig(latest_file, dpi=150, bbox_inches='tight')
        print(f"✅ Latest dashboard: {latest_file}")

        plt.close()

        # Save metrics JSON
        metrics_output = {
            'timestamp': datetime.now().isoformat(),
            'tasks': task_metrics,
            'artifacts': artifact_metrics,
            'performance': perf_metrics,
            'health_score': health_score,
        }

        metrics_file = self.artifacts_dir / "evals" / "swarm_metrics_latest.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, 'w') as f:
            json.dump(metrics_output, f, indent=2, default=str)
        print(f"✅ Metrics JSON: {metrics_file}")

        return metrics_output


if __name__ == "__main__":
    import numpy as np  # Import here for histogram

    dashboard = SwarmDashboard()
    metrics = dashboard.generate_dashboard()

    print("\n" + "="*60)
    print("📊 SWARM DASHBOARD SUMMARY")
    print("="*60)
    print(f"Daemon Uptime: {metrics['performance']['daemon_uptime_hours']:.1f} hours")
    print(f"Throughput: {metrics['performance']['tasks_per_hour']:.1f} tasks/hour")
    print(f"Health Score: {metrics['health_score']}/100")
    print(f"Active Tasks: {metrics['tasks']['active']}")
    print(f"Completed Tasks: {metrics['tasks']['completed']}")
    print(f"Artifacts: {sum([metrics['artifacts']['plots'], metrics['artifacts']['csvs'], metrics['artifacts']['evals']])} files")
    print("="*60)
