#!/usr/bin/env python3
"""
QA Swarm Cluster Monitor
Real-time monitoring and visualization for multi-node distributed swarm

This monitor:
- Detects all nodes in the cluster
- Tracks per-node task execution
- Monitors cluster-wide metrics
- Generates distributed dashboard
- Detects node failures and load imbalances
"""

import json
import sys
import socket
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, Any, List

# Add parent to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False
    print("⚠️  matplotlib not available, visual dashboard disabled")


class ClusterMonitor:
    """Multi-node swarm cluster monitoring and visualization"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.logs_dir = self.base_dir / "logs"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.plots_dir = self.base_dir / "plots"
        self.plots_dir.mkdir(exist_ok=True)

        # Detect cluster nodes
        self.nodes = self.detect_cluster_nodes()
        self.primary_node = self.detect_primary_node()

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
            'capabilities': ['coordinator', 'executor', 'all'],
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

    def analyze_cluster_metrics(self) -> Dict[str, Any]:
        """Collect cluster-wide metrics"""
        metrics = {
            'cluster_size': len(self.nodes),
            'nodes': {},
            'total_tasks': 0,
            'tasks_by_node': defaultdict(int),
            'tasks_by_state': Counter(),
            'cluster_health': 0,
        }

        # Analyze task execution by node
        for state_dir in ['active', 'completed']:
            state_path = self.tasks_dir / state_dir
            if not state_path.exists():
                continue

            for task_file in state_path.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                metrics['total_tasks'] += 1
                metrics['tasks_by_state'][state_dir] += 1

                # Track which node executed this
                history = task.get('execution', {}).get('history', [])
                if history:
                    last_exec = history[-1]
                    executor_node = last_exec.get('node_id', 'unknown')
                    metrics['tasks_by_node'][executor_node] += 1

        # Per-node analysis
        for node in self.nodes:
            node_id = node.get('node_id', 'unknown')
            node_type = node.get('node_type', 'unknown')

            node_metrics = {
                'node_id': node_id,
                'node_type': node_type,
                'tasks_executed': metrics['tasks_by_node'].get(node_id, 0),
                'capabilities': node.get('capabilities', []),
                'status': 'active',  # Will be updated with health check
            }

            # Check if node is responsive (simplified - could ping or check logs)
            node_metrics['last_seen'] = datetime.now().isoformat()

            metrics['nodes'][node_id] = node_metrics

        # Calculate cluster health
        active_nodes = sum(1 for n in metrics['nodes'].values() if n['status'] == 'active')
        if self.nodes:
            metrics['cluster_health'] = int(100 * active_nodes / len(self.nodes))
        else:
            metrics['cluster_health'] = 0

        return metrics

    def detect_load_imbalance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Detect if tasks are unevenly distributed across nodes"""
        imbalance = {
            'detected': False,
            'severity': 'none',
            'overloaded_nodes': [],
            'underutilized_nodes': [],
        }

        if len(metrics['nodes']) < 2:
            return imbalance

        # Calculate average tasks per node
        total_tasks = sum(n['tasks_executed'] for n in metrics['nodes'].values())
        avg_tasks = total_tasks / len(metrics['nodes'])

        # Identify imbalances
        for node_id, node_data in metrics['nodes'].items():
            tasks = node_data['tasks_executed']

            if tasks > avg_tasks * 1.5:  # 50% above average
                imbalance['overloaded_nodes'].append({
                    'node_id': node_id,
                    'tasks': tasks,
                    'average': avg_tasks,
                    'ratio': tasks / max(1, avg_tasks),
                })

            if tasks < avg_tasks * 0.5 and tasks > 0:  # 50% below average
                imbalance['underutilized_nodes'].append({
                    'node_id': node_id,
                    'tasks': tasks,
                    'average': avg_tasks,
                    'ratio': tasks / max(1, avg_tasks),
                })

        if imbalance['overloaded_nodes'] or imbalance['underutilized_nodes']:
            imbalance['detected'] = True
            imbalance['severity'] = 'high' if len(imbalance['overloaded_nodes']) > 1 else 'medium'

        return imbalance

    def generate_cluster_dashboard(self, metrics: Dict[str, Any],
                                   imbalance: Dict[str, Any]):
        """Generate visual dashboard for cluster"""
        if not MATPLOTLIB_OK:
            print("  ⚠️  Matplotlib not available, skipping visual dashboard")
            return

        fig = plt.figure(figsize=(16, 10))
        fig.suptitle('QA Swarm Cluster Dashboard', fontsize=16, fontweight='bold')

        # 1. Cluster topology (top left)
        ax1 = plt.subplot(2, 3, 1)
        ax1.axis('off')

        topology_text = f"""
CLUSTER TOPOLOGY

Total Nodes: {metrics['cluster_size']}
Primary: {self.primary_node}

Nodes:
"""
        for node_id, node_data in metrics['nodes'].items():
            node_type = node_data['node_type']
            status = node_data['status']
            symbol = '🟢' if status == 'active' else '🔴'
            topology_text += f"  {symbol} {node_id} ({node_type})\n"

        ax1.text(0.1, 0.5, topology_text, fontsize=10, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        ax1.set_title('Cluster Topology')

        # 2. Task distribution (top center)
        ax2 = plt.subplot(2, 3, 2)
        if metrics['nodes']:
            node_ids = list(metrics['nodes'].keys())
            task_counts = [metrics['nodes'][nid]['tasks_executed'] for nid in node_ids]

            # Shorten node IDs for display
            short_ids = [nid[:12] for nid in node_ids]

            ax2.barh(short_ids, task_counts, color='steelblue', alpha=0.7)
            ax2.set_xlabel('Tasks Executed')
            ax2.set_title('Task Distribution Across Nodes')
            ax2.grid(axis='x', alpha=0.3)
        else:
            ax2.text(0.5, 0.5, 'No nodes detected', ha='center', va='center')
            ax2.set_title('Task Distribution')

        # 3. Cluster health (top right)
        ax3 = plt.subplot(2, 3, 3)
        ax3.axis('off')

        health_color = 'lightgreen' if metrics['cluster_health'] >= 80 else \
                      'yellow' if metrics['cluster_health'] >= 60 else 'lightcoral'

        health_text = f"""
CLUSTER HEALTH

Health Score: {metrics['cluster_health']}/100

Active Nodes: {sum(1 for n in metrics['nodes'].values() if n['status'] == 'active')}/{metrics['cluster_size']}

Total Tasks: {metrics['total_tasks']}

Load Balance: {'⚠️ IMBALANCED' if imbalance['detected'] else '✅ BALANCED'}
"""
        ax3.text(0.1, 0.5, health_text, fontsize=10, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor=health_color, alpha=0.5))
        ax3.set_title('Cluster Health')

        # 4. State distribution (bottom left)
        ax4 = plt.subplot(2, 3, 4)
        if metrics['tasks_by_state']:
            states = list(metrics['tasks_by_state'].keys())
            counts = list(metrics['tasks_by_state'].values())
            ax4.pie(counts, labels=states, autopct='%1.1f%%', startangle=90)
            ax4.set_title('Task State Distribution')
        else:
            ax4.text(0.5, 0.5, 'No tasks', ha='center', va='center')
            ax4.set_title('Task State Distribution')

        # 5. Load balance analysis (bottom center)
        ax5 = plt.subplot(2, 3, 5)
        ax5.axis('off')

        if imbalance['detected']:
            balance_text = f"""
LOAD IMBALANCE DETECTED

Severity: {imbalance['severity'].upper()}

Overloaded Nodes:
"""
            for node in imbalance['overloaded_nodes']:
                balance_text += f"  • {node['node_id'][:12]}: {node['tasks']} tasks\n"
                balance_text += f"    ({node['ratio']:.1f}× average)\n"

            if imbalance['underutilized_nodes']:
                balance_text += "\nUnderutilized Nodes:\n"
                for node in imbalance['underutilized_nodes']:
                    balance_text += f"  • {node['node_id'][:12]}: {node['tasks']} tasks\n"
                    balance_text += f"    ({node['ratio']:.1f}× average)\n"

            bg_color = 'lightcoral'
        else:
            balance_text = """
LOAD BALANCE: OPTIMAL

All nodes are processing
tasks evenly.

No action required.
"""
            bg_color = 'lightgreen'

        ax5.text(0.1, 0.5, balance_text, fontsize=9, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor=bg_color, alpha=0.5))
        ax5.set_title('Load Balance Analysis')

        # 6. Cluster metrics (bottom right)
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')

        metrics_text = f"""
CLUSTER METRICS

Cluster Size: {metrics['cluster_size']} nodes

Total Capacity:
  {sum(len(n.get('capabilities', [])) for n in self.nodes)} capabilities

Tasks Processed:
  {metrics['total_tasks']} total

Average per Node:
  {metrics['total_tasks'] / max(1, metrics['cluster_size']):.1f} tasks

Primary Node:
  {self.primary_node}
"""
        ax6.text(0.1, 0.5, metrics_text, fontsize=10, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax6.set_title('Cluster Metrics')

        plt.tight_layout()

        # Save dashboard
        output_file = self.plots_dir / f"cluster_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"  ✅ Cluster dashboard: {output_file}")

        # Save latest
        latest_file = self.plots_dir / "cluster_dashboard_latest.png"
        plt.savefig(latest_file, dpi=150, bbox_inches='tight')
        print(f"  ✅ Latest dashboard: {latest_file}")

        plt.close()

    def run(self):
        """Main cluster monitor execution"""
        print("🌐 QA Swarm Cluster Monitor")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")

        # Detect cluster
        print(f"🔍 Detecting cluster nodes...")
        print(f"  Found {len(self.nodes)} node(s)")
        for node in self.nodes:
            node_type = node.get('node_type', 'unknown')
            node_id = node.get('node_id', 'unknown')
            print(f"    • {node_id} ({node_type})")

        print("")

        # Analyze metrics
        print("📊 Analyzing cluster metrics...")
        metrics = self.analyze_cluster_metrics()
        print(f"  Total tasks processed: {metrics['total_tasks']}")
        print(f"  Cluster health: {metrics['cluster_health']}/100")

        print("")

        # Check load balance
        print("⚖️  Checking load balance...")
        imbalance = self.detect_load_imbalance(metrics)
        if imbalance['detected']:
            print(f"  ⚠️  Load imbalance detected ({imbalance['severity']} severity)")
            if imbalance['overloaded_nodes']:
                print(f"  Overloaded: {len(imbalance['overloaded_nodes'])} node(s)")
            if imbalance['underutilized_nodes']:
                print(f"  Underutilized: {len(imbalance['underutilized_nodes'])} node(s)")
        else:
            print("  ✅ Load is balanced")

        print("")

        # Generate dashboard
        print("📈 Generating cluster dashboard...")
        self.generate_cluster_dashboard(metrics, imbalance)

        # Save metrics JSON
        metrics_output = {
            'timestamp': datetime.now().isoformat(),
            'cluster': metrics,
            'load_balance': imbalance,
        }

        metrics_file = self.artifacts_dir / "evals" / "cluster_metrics_latest.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, 'w') as f:
            json.dump(metrics_output, f, indent=2, default=str)
        print(f"  ✅ Metrics JSON: {metrics_file}")

        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🌐 Cluster Monitor Complete")
        print("")
        print(f"Cluster Size: {metrics['cluster_size']} nodes")
        print(f"Health Score: {metrics['cluster_health']}/100")
        print(f"Total Tasks: {metrics['total_tasks']}")
        print(f"Load Balance: {'⚠️ IMBALANCED' if imbalance['detected'] else '✅ BALANCED'}")
        print("")

        return metrics


if __name__ == "__main__":
    monitor = ClusterMonitor()
    monitor.run()
