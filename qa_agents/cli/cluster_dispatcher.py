#!/usr/bin/env python3
"""
QA Swarm Cluster Dispatcher
Intelligent task distribution across multi-node distributed swarm

This dispatcher:
- Detects all nodes in the cluster
- Analyzes node capabilities and current load
- Routes tasks to optimal nodes
- Balances workload across compute nodes
- Respects node specialization
- Tracks task execution across nodes
"""

import json
import sys
import socket
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class ClusterDispatcher:
    """Multi-node intelligent task dispatcher with load balancing"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.logs_dir = self.base_dir / "logs"

        # Detect cluster nodes
        self.nodes = self.detect_cluster_nodes()
        self.primary_node = self.detect_primary_node()

        # Node specialization mapping
        self.capability_map = {
            'executor': ['test-', 'exp-', 'campaign-'],
            'reviewer': ['review-'],
            'rust_benchmarks': ['port-rust-', 'benchmark-'],
            'metrics_generation': ['metrics-', 'eval-'],
            'coordinator': ['plan-', 'arch-', 'campaign-'],
            'all': ['*'],  # Can handle any task type
        }

    def detect_cluster_nodes(self) -> List[Dict[str, Any]]:
        """Detect all nodes in the cluster"""
        nodes = []

        # Check for node config files
        for config_file in self.base_dir.glob(".node_config*.json"):
            try:
                with open(config_file, 'r') as f:
                    node_config = json.load(f)
                    nodes.append(node_config)
            except Exception:
                continue

        # Add self (primary node)
        hostname = socket.gethostname()
        nodes.append({
            'node_type': 'primary',
            'node_id': hostname,
            'capabilities': ['coordinator', 'executor', 'reviewer', 'all'],
        })

        return nodes

    def detect_primary_node(self) -> str:
        """Identify which node is the primary coordinator"""
        for node in self.nodes:
            if node.get('node_type') == 'primary':
                return node.get('node_id', socket.gethostname())

        # Fallback to current hostname
        return socket.gethostname()

    def load_task(self, task_file: Path) -> Dict[str, Any]:
        """Load task from YAML/JSON"""
        try:
            text = task_file.read_text(encoding='utf-8')
            if YAML_OK:
                return yaml.safe_load(text)
            else:
                return json.loads(text)
        except Exception:
            return {}

    def save_task(self, task: Dict[str, Any], task_file: Path):
        """Save task to YAML/JSON"""
        try:
            if YAML_OK:
                with open(task_file, 'w') as f:
                    yaml.dump(task, f, default_flow_style=False, sort_keys=False)
            else:
                with open(task_file, 'w') as f:
                    json.dump(task, f, indent=2)
        except Exception as e:
            print(f"  ⚠️  Failed to save {task_file}: {e}")

    def analyze_node_load(self) -> Dict[str, Dict[str, Any]]:
        """Analyze current load on each node"""
        node_loads = {}

        for node in self.nodes:
            node_id = node.get('node_id', 'unknown')
            node_loads[node_id] = {
                'node_type': node.get('node_type', 'unknown'),
                'capabilities': node.get('capabilities', []),
                'active_tasks': 0,
                'completed_tasks': 0,
                'task_types': Counter(),
                'avg_execution_time': 0,
                'status': 'active',
            }

        # Count active tasks by node
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                # Check execution history for node assignment
                history = task.get('execution', {}).get('history', [])
                if history:
                    last_exec = history[-1]
                    executor_node = last_exec.get('node_id', self.primary_node)

                    if executor_node in node_loads:
                        node_loads[executor_node]['active_tasks'] += 1
                        task_id = task.get('task_id', '')
                        task_type = task_id.split('-')[0] if '-' in task_id else 'unknown'
                        node_loads[executor_node]['task_types'][task_type] += 1

        # Count completed tasks by node
        completed_dir = self.tasks_dir / "completed"
        if completed_dir.exists():
            for task_file in completed_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                history = task.get('execution', {}).get('history', [])
                if history:
                    last_exec = history[-1]
                    executor_node = last_exec.get('node_id', self.primary_node)

                    if executor_node in node_loads:
                        node_loads[executor_node]['completed_tasks'] += 1

        return node_loads

    def task_matches_capability(self, task_id: str, capabilities: List[str]) -> bool:
        """Check if task matches node capabilities"""
        # 'all' capability matches everything
        if 'all' in capabilities:
            return True

        # Check each capability
        for capability in capabilities:
            patterns = self.capability_map.get(capability, [])
            for pattern in patterns:
                if pattern == '*':
                    return True
                if task_id.startswith(pattern.rstrip('-')):
                    return True

        return False

    def select_optimal_node(self, task: Dict[str, Any], node_loads: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Select optimal node for task execution"""
        task_id = task.get('task_id', '')

        # Filter nodes by capability
        capable_nodes = []
        for node_id, load_info in node_loads.items():
            capabilities = load_info['capabilities']
            if self.task_matches_capability(task_id, capabilities):
                capable_nodes.append((node_id, load_info))

        if not capable_nodes:
            # Fallback to primary if no capable nodes
            return self.primary_node

        # Sort by load (prefer less loaded nodes)
        capable_nodes.sort(key=lambda x: x[1]['active_tasks'])

        # Select least loaded capable node
        selected_node = capable_nodes[0][0]
        return selected_node

    def dispatch_tasks(self) -> Dict[str, Any]:
        """Dispatch tasks across cluster with load balancing"""
        stats = {
            'scanned': 0,
            'dispatched': 0,
            'skipped': 0,
            'by_node': Counter(),
            'errors': [],
        }

        # Analyze current node loads
        node_loads = self.analyze_node_load()

        # Scan inbox for unassigned tasks
        inbox_dir = self.tasks_dir / "inbox"
        if not inbox_dir.exists():
            return stats

        for task_file in inbox_dir.glob("*.yaml"):
            stats['scanned'] += 1

            task = self.load_task(task_file)
            if not task:
                stats['skipped'] += 1
                continue

            # Skip if already has node assignment
            execution = task.get('execution', {})
            history = execution.get('history', [])
            if history:
                last_exec = history[-1]
                if 'node_id' in last_exec:
                    stats['skipped'] += 1
                    continue

            # Select optimal node
            optimal_node = self.select_optimal_node(task, node_loads)

            # Add node assignment to task
            if 'execution' not in task:
                task['execution'] = {}
            if 'history' not in task['execution']:
                task['execution']['history'] = []

            # Add dispatch entry
            dispatch_entry = {
                'stage': 'cluster_dispatch',
                'timestamp': datetime.now().isoformat(),
                'node_id': optimal_node,
                'dispatcher': 'cluster_dispatcher',
            }

            task['execution']['history'].append(dispatch_entry)

            # Update metadata
            if 'metadata' not in task:
                task['metadata'] = {}
            task['metadata']['target_node'] = optimal_node
            task['metadata']['cluster_dispatched'] = True

            # Save updated task
            self.save_task(task, task_file)

            # Update stats
            stats['dispatched'] += 1
            stats['by_node'][optimal_node] += 1

            # Update node load (for subsequent assignments in this run)
            if optimal_node in node_loads:
                node_loads[optimal_node]['active_tasks'] += 1

        return stats

    def generate_dispatch_report(self, stats: Dict[str, Any], node_loads: Dict[str, Dict[str, Any]]):
        """Generate cluster dispatch report"""
        print("\n📊 Cluster Dispatch Report")
        print("=" * 60)

        print(f"\n📥 Inbox Processing:")
        print(f"  Tasks scanned: {stats['scanned']}")
        print(f"  Tasks dispatched: {stats['dispatched']}")
        print(f"  Tasks skipped: {stats['skipped']}")

        if stats['dispatched'] > 0:
            print(f"\n🌐 Distribution Across Nodes:")
            for node_id, count in stats['by_node'].most_common():
                print(f"  {node_id}: {count} tasks")

        print(f"\n🖥️  Node Load Status:")
        for node_id, load_info in sorted(node_loads.items()):
            node_type = load_info['node_type']
            active = load_info['active_tasks']
            completed = load_info['completed_tasks']
            status_icon = '🟢' if active < 100 else '🟡' if active < 200 else '🔴'

            print(f"  {status_icon} {node_id} ({node_type})")
            print(f"     Active: {active} | Completed: {completed}")

            if load_info['task_types']:
                top_types = load_info['task_types'].most_common(3)
                types_str = ", ".join([f"{t}({c})" for t, c in top_types])
                print(f"     Top types: {types_str}")

        print(f"\n📈 Cluster Health:")
        total_active = sum(n['active_tasks'] for n in node_loads.values())
        total_completed = sum(n['completed_tasks'] for n in node_loads.values())
        avg_load = total_active / max(1, len(node_loads))

        print(f"  Total active tasks: {total_active}")
        print(f"  Total completed tasks: {total_completed}")
        print(f"  Average load per node: {avg_load:.1f}")

        # Detect imbalances
        max_load = max((n['active_tasks'] for n in node_loads.values()), default=0)
        min_load = min((n['active_tasks'] for n in node_loads.values()), default=0)

        if max_load > 0 and min_load > 0:
            imbalance_ratio = max_load / max(1, min_load)
            if imbalance_ratio > 2.0:
                print(f"\n⚠️  Load imbalance detected (ratio: {imbalance_ratio:.1f}×)")
            else:
                print(f"\n✅ Load is balanced (ratio: {imbalance_ratio:.1f}×)")

        if stats['errors']:
            print(f"\n❌ Errors:")
            for error in stats['errors'][:5]:
                print(f"  • {error}")

    def run(self):
        """Main cluster dispatcher execution"""
        print("🌐 QA Swarm Cluster Dispatcher")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")

        # Detect cluster
        print(f"🔍 Detecting cluster nodes...")
        print(f"  Found {len(self.nodes)} node(s)")
        for node in self.nodes:
            node_type = node.get('node_type', 'unknown')
            node_id = node.get('node_id', 'unknown')
            capabilities = ", ".join(node.get('capabilities', []))
            print(f"    • {node_id} ({node_type}) - {capabilities}")

        print("")

        # Analyze current loads
        print("📊 Analyzing node loads...")
        node_loads = self.analyze_node_load()

        print("")

        # Dispatch tasks
        print("🚀 Dispatching tasks across cluster...")
        stats = self.dispatch_tasks()

        print("")

        # Generate report
        self.generate_dispatch_report(stats, node_loads)

        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🌐 Cluster Dispatch Complete")
        print("")


if __name__ == "__main__":
    dispatcher = ClusterDispatcher()
    dispatcher.run()
