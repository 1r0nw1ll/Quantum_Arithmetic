#!/usr/bin/env python3
"""
QA System Architect
Analyzes and refactors the swarm's own architecture, schemas, and pipelines.

This agent ensures the system architecture scales cleanly as complexity grows,
identifying schema drift, agent overload, and pipeline inefficiencies.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from collections import Counter, defaultdict

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class QAArchitect:
    """Autonomous system architecture analyzer and refactorer"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.inbox = self.tasks_dir / "inbox"
        self.logs_dir = self.base_dir / "logs"
        self.metrics_file = self.base_dir / "artifacts" / "evals" / "swarm_metrics_latest.json"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def load_metrics(self) -> Dict[str, Any]:
        """Load latest swarm metrics"""
        if not self.metrics_file.exists():
            return {}
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

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

    def analyze_task_schema_health(self) -> Dict[str, Any]:
        """Analyze task schema consistency and identify drift"""
        schema_health = {
            'task_types': Counter(),
            'field_usage': defaultdict(int),
            'rare_types': [],
            'missing_fields': defaultdict(list),
            'inconsistent_schemas': [],
        }

        required_fields = {'id', 'project', 'title', 'description', 'source', 'priority',
                          'status', 'lane', 'assignee', 'created', 'tags', 'metadata'}

        # Scan all active tasks
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                # Track task types
                task_type = task.get('project', 'unknown')
                schema_health['task_types'][task_type] += 1

                # Track field usage
                for field in task.keys():
                    schema_health['field_usage'][field] += 1

                # Check for missing required fields
                missing = required_fields - set(task.keys())
                if missing:
                    schema_health['missing_fields'][task.get('id', 'unknown')] = list(missing)

        # Identify rare types (<=2 instances)
        schema_health['rare_types'] = [t for t, count in schema_health['task_types'].items() if count <= 2]

        # Identify field inconsistencies
        total_tasks = sum(schema_health['task_types'].values())
        if total_tasks > 0:
            for field, count in schema_health['field_usage'].items():
                coverage = count / total_tasks
                if 0.1 < coverage < 0.9:  # Fields that appear in 10-90% of tasks
                    schema_health['inconsistent_schemas'].append({
                        'field': field,
                        'coverage': coverage,
                        'count': count,
                        'total': total_tasks,
                    })

        return schema_health

    def analyze_agent_load_distribution(self) -> Dict[str, Any]:
        """Analyze agent workload distribution and identify imbalances"""
        load_analysis = {
            'by_assignee': Counter(),
            'overloaded_agents': [],
            'underutilized_agents': [],
            'unassigned_tasks': 0,
        }

        # Scan active tasks
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                if not task:
                    continue

                assignee = task.get('assignee', 'unassigned')
                state = task.get('state', 'unknown')

                if state in ('queued', 'assigned', 'pending'):
                    load_analysis['by_assignee'][assignee] += 1

                if assignee in ('unassigned', 'auto', 'manual'):
                    load_analysis['unassigned_tasks'] += 1

        # Identify overloaded agents (>100 tasks)
        for agent, count in load_analysis['by_assignee'].items():
            if count > 100:
                load_analysis['overloaded_agents'].append({
                    'agent': agent,
                    'task_count': count,
                    'severity': 'high' if count > 200 else 'medium',
                })

        # Identify underutilized agents (<5 tasks)
        for agent, count in load_analysis['by_assignee'].items():
            if count > 0 and count < 5 and agent not in ('unassigned', 'auto', 'manual'):
                load_analysis['underutilized_agents'].append({
                    'agent': agent,
                    'task_count': count,
                })

        return load_analysis

    def analyze_pipeline_efficiency(self) -> Dict[str, Any]:
        """Analyze task pipeline flow and identify bottlenecks"""
        pipeline_health = {
            'inbox_backlog': 0,
            'active_backlog': 0,
            'completion_rate': 0.0,
            'rejection_rate': 0.0,
            'avg_retry_count': 0.0,
            'bottlenecks': [],
        }

        # Count tasks in each state
        for state in ['inbox', 'active', 'completed', 'rejected']:
            state_dir = self.tasks_dir / state
            if state_dir.exists():
                count = len(list(state_dir.glob("*.yaml")))
                if state == 'inbox':
                    pipeline_health['inbox_backlog'] = count
                elif state == 'active':
                    pipeline_health['active_backlog'] = count
                elif state == 'completed':
                    completed = count
                elif state == 'rejected':
                    rejected = count

        # Calculate rates
        total_processed = completed + rejected if 'completed' in locals() and 'rejected' in locals() else 1
        if total_processed > 0:
            pipeline_health['completion_rate'] = completed / total_processed if 'completed' in locals() else 0
            pipeline_health['rejection_rate'] = rejected / total_processed if 'rejected' in locals() else 0

        # Analyze retry patterns
        retry_counts = []
        active_dir = self.tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("*.yaml"):
                task = self.load_task(task_file)
                retry_count = task.get('retry_count', 0)
                if retry_count > 0:
                    retry_counts.append(retry_count)

        if retry_counts:
            pipeline_health['avg_retry_count'] = sum(retry_counts) / len(retry_counts)

        # Identify bottlenecks
        if pipeline_health['inbox_backlog'] > 50:
            pipeline_health['bottlenecks'].append({
                'stage': 'inbox',
                'issue': 'High backlog - dispatch may be slow',
                'count': pipeline_health['inbox_backlog'],
            })

        if pipeline_health['active_backlog'] > 500:
            pipeline_health['bottlenecks'].append({
                'stage': 'execution',
                'issue': 'High active backlog - executor may be overloaded',
                'count': pipeline_health['active_backlog'],
            })

        if pipeline_health['rejection_rate'] > 0.2:
            pipeline_health['bottlenecks'].append({
                'stage': 'review',
                'issue': f'High rejection rate ({pipeline_health["rejection_rate"]:.1%})',
                'severity': 'high',
            })

        return pipeline_health

    def detect_architecture_issues(self, schema_health: Dict[str, Any],
                                   load_analysis: Dict[str, Any],
                                   pipeline_health: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify architecture issues requiring attention"""
        issues = []

        # Issue: Schema drift (too many rare types)
        if len(schema_health['rare_types']) > 10:
            issues.append({
                'type': 'schema_drift',
                'severity': 'medium',
                'description': f"{len(schema_health['rare_types'])} task types with <=2 instances",
                'rare_types': schema_health['rare_types'][:10],
                'recommendation': 'Consolidate rare types into broader categories',
            })

        # Issue: Field inconsistency
        if len(schema_health['inconsistent_schemas']) > 5:
            issues.append({
                'type': 'field_inconsistency',
                'severity': 'low',
                'description': f"{len(schema_health['inconsistent_schemas'])} fields with incomplete coverage",
                'fields': [f['field'] for f in schema_health['inconsistent_schemas'][:5]],
                'recommendation': 'Standardize required vs optional fields',
            })

        # Issue: Agent overload
        if load_analysis['overloaded_agents']:
            issues.append({
                'type': 'agent_overload',
                'severity': 'high',
                'description': f"{len(load_analysis['overloaded_agents'])} agents with >100 task backlog",
                'agents': load_analysis['overloaded_agents'],
                'recommendation': 'Implement load balancing or agent parallelization',
            })

        # Issue: Pipeline bottleneck
        if pipeline_health['bottlenecks']:
            issues.append({
                'type': 'pipeline_bottleneck',
                'severity': 'high',
                'description': f"{len(pipeline_health['bottlenecks'])} pipeline bottlenecks detected",
                'bottlenecks': pipeline_health['bottlenecks'],
                'recommendation': 'Optimize slow pipeline stages',
            })

        # Issue: High rejection rate
        if pipeline_health['rejection_rate'] > 0.15:
            issues.append({
                'type': 'high_rejection_rate',
                'severity': 'medium',
                'description': f"Rejection rate at {pipeline_health['rejection_rate']:.1%}",
                'rate': pipeline_health['rejection_rate'],
                'recommendation': 'Review and improve task quality gates',
            })

        return issues

    def build_architecture_tasks(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate architecture refactoring tasks"""
        tasks = []
        timestamp = datetime.now().strftime('%H%M%S')

        for issue in issues:
            if issue['type'] == 'schema_drift':
                task_id = f"arch-refactor-schema-{timestamp}"
                tasks.append({
                    'id': task_id,
                    'project': 'architecture',
                    'title': 'Refactor and consolidate task type schema',
                    'description': f'''
Schema drift detected: {len(issue['rare_types'])} task types with <=2 instances.

Rare types: {', '.join(issue['rare_types'][:10])}

Recommendation: {issue['recommendation']}

Steps:
1. Analyze task type usage patterns
2. Group related rare types into broader categories
3. Propose standardized schema
4. Generate migration plan
                    '''.strip(),
                    'source': 'qa_architect',
                    'priority': 3.0,
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'opencode',
                    'created': datetime.now().isoformat(),
                    'tags': ['architecture', 'refactor', 'schema'],
                    'metadata': {
                        'issue_type': 'schema_drift',
                        'affected_types': issue['rare_types'],
                    },
                })

            elif issue['type'] == 'agent_overload':
                task_id = f"arch-balance-agents-{timestamp}"
                overloaded = issue['agents'][0]  # Focus on most overloaded
                tasks.append({
                    'id': task_id,
                    'project': 'architecture',
                    'title': f'Load-balance {overloaded["agent"]} ({overloaded["task_count"]} tasks)',
                    'description': f'''
Agent overload detected: {overloaded["agent"]} has {overloaded["task_count"]} queued tasks.

Recommendation: {issue['recommendation']}

Options:
1. Implement parallel task processing
2. Split agent into specialized sub-agents
3. Redistribute tasks to underutilized agents
4. Optimize agent execution speed
                    '''.strip(),
                    'source': 'qa_architect',
                    'priority': 4.5,
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'opencode',
                    'created': datetime.now().isoformat(),
                    'tags': ['architecture', 'performance', 'load_balancing'],
                    'metadata': {
                        'issue_type': 'agent_overload',
                        'overloaded_agent': overloaded['agent'],
                        'task_count': overloaded['task_count'],
                    },
                })

            elif issue['type'] == 'pipeline_bottleneck':
                for bottleneck in issue['bottlenecks'][:2]:  # Top 2 bottlenecks
                    task_id = f"arch-optimize-{bottleneck['stage']}-{timestamp}"
                    tasks.append({
                        'id': task_id,
                        'project': 'architecture',
                        'title': f'Optimize {bottleneck["stage"]} pipeline stage',
                        'description': f'''
Pipeline bottleneck: {bottleneck['issue']}

Recommendation: {issue['recommendation']}

Analyze and optimize the {bottleneck['stage']} stage to improve throughput.
                        '''.strip(),
                        'source': 'qa_architect',
                        'priority': 4.0,
                        'status': 'pending',
                        'lane': 'green',
                        'assignee': 'opencode',
                        'created': datetime.now().isoformat(),
                        'tags': ['architecture', 'pipeline', 'optimization'],
                        'metadata': {
                            'issue_type': 'pipeline_bottleneck',
                            'stage': bottleneck['stage'],
                        },
                    })

        return tasks

    def save_task(self, task: Dict[str, Any]):
        """Save task to inbox"""
        task_file = self.inbox / f"{task['id']}.yaml"
        if YAML_OK:
            with open(task_file, 'w') as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
        print(f"  ✅ Created architecture task: {task['id']}")

    def run(self):
        """Main QA architect execution"""
        print("🏗️  QA Architect: Analyzing system architecture...")

        # Analyze architecture health
        print("\n📐 Analyzing task schema health...")
        schema_health = self.analyze_task_schema_health()
        print(f"  Task types: {len(schema_health['task_types'])}")
        print(f"  Rare types: {len(schema_health['rare_types'])}")
        print(f"  Inconsistent schemas: {len(schema_health['inconsistent_schemas'])}")

        print("\n⚖️  Analyzing agent load distribution...")
        load_analysis = self.analyze_agent_load_distribution()
        print(f"  Active agents: {len(load_analysis['by_assignee'])}")
        print(f"  Overloaded: {len(load_analysis['overloaded_agents'])}")
        print(f"  Underutilized: {len(load_analysis['underutilized_agents'])}")

        print("\n🔄 Analyzing pipeline efficiency...")
        pipeline_health = self.analyze_pipeline_efficiency()
        print(f"  Inbox backlog: {pipeline_health['inbox_backlog']}")
        print(f"  Active backlog: {pipeline_health['active_backlog']}")
        print(f"  Completion rate: {pipeline_health['completion_rate']:.1%}")
        print(f"  Rejection rate: {pipeline_health['rejection_rate']:.1%}")

        # Detect issues
        print("\n🔍 Detecting architecture issues...")
        issues = self.detect_architecture_issues(schema_health, load_analysis, pipeline_health)

        if not issues:
            print("✨ No architecture issues detected - system is well-structured!")
            return []

        print(f"  Found {len(issues)} architecture issues:")
        for issue in issues:
            print(f"    • {issue['type']} ({issue['severity']} severity)")

        # Generate tasks
        print("\n🏗️  Generating architecture tasks...")
        arch_tasks = self.build_architecture_tasks(issues)

        if not arch_tasks:
            print("  No architecture tasks generated")
            return []

        # Save tasks
        print(f"\n✅ Saving {len(arch_tasks)} architecture tasks...")
        for task in arch_tasks:
            self.save_task(task)

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "QAArchitect",
            "action": "architecture_analysis",
            "issues_detected": len(issues),
            "tasks_generated": len(arch_tasks),
            "issue_types": [i['type'] for i in issues],
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"\n🏗️  Architecture analysis complete: {len(arch_tasks)} refactoring tasks generated")
        return arch_tasks


if __name__ == "__main__":
    architect = QAArchitect()
    architect.run()
