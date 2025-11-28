#!/usr/bin/env python3
"""
QA Research Director
Sets the research agenda by analyzing global metrics and generating high-level campaign tasks.

This agent determines *what the swarm should work on* at the research-program level,
not just reacting to incoming tasks but proactively directing scientific effort.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class ResearchDirector:
    """Autonomous research agenda setter and campaign generator"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.metrics_file = self.base_dir / "artifacts" / "evals" / "swarm_metrics_latest.json"
        self.tasks_dir = self.base_dir / "tasks"
        self.inbox = self.tasks_dir / "inbox"
        self.ingestion_dir = self.base_dir / "artifacts" / "ingestion"
        self.evals_dir = self.base_dir / "artifacts" / "evals"
        self.logs_dir = self.base_dir / "logs"
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

    def analyze_ingestion_status(self) -> Dict[str, Any]:
        """Analyze ingestion paper processing status"""
        status = {
            'total_papers': 0,
            'extracted': 0,
            'analyzed': 0,
            'pending': 0,
            'papers_by_topic': defaultdict(int),
        }

        # Check ingestion candidates directory
        candidates_dir = self.base_dir.parent / "ingestion candidates"
        if candidates_dir.exists():
            status['total_papers'] = len(list(candidates_dir.glob("*.odt")))

        # Check processed ingestion artifacts
        if self.ingestion_dir.exists():
            status['extracted'] = len(list(self.ingestion_dir.glob("*_ANALYSIS.md")))

        status['pending'] = status['total_papers'] - status['extracted']

        # Categorize papers by topic (from filenames)
        if candidates_dir.exists():
            for paper in candidates_dir.glob("*.odt"):
                name = paper.stem.lower()
                if 'jepa' in name or 'vision' in name:
                    status['papers_by_topic']['vision_ai'] += 1
                elif 'raman' in name or 'quantum' in name:
                    status['papers_by_topic']['quantum'] += 1
                elif 'jit' in name or 'compiler' in name:
                    status['papers_by_topic']['compilation'] += 1
                elif 'statistical' in name or 'mechanics' in name:
                    status['papers_by_topic']['statistical_physics'] += 1
                else:
                    status['papers_by_topic']['other'] += 1

        return status

    def analyze_experiment_coverage(self) -> Dict[str, Any]:
        """Analyze which experiments have been run vs planned"""
        coverage = {
            'jepa_completed': False,
            'arc_completed': False,
            'stat_mech_completed': False,
            'rust_speedup_avg': 1.0,
            'hgd_vs_sgd_ratio': 0.0,
        }

        # Check completed tasks for experiment types
        completed_dir = self.tasks_dir / "completed"
        if completed_dir.exists():
            for task_file in completed_dir.glob("*.yaml"):
                try:
                    if YAML_OK:
                        task = yaml.safe_load(task_file.read_text())
                    else:
                        task = json.loads(task_file.read_text())

                    title = task.get('title', '').lower()
                    if 'jepa' in title:
                        coverage['jepa_completed'] = True
                    if 'arc' in title:
                        coverage['arc_completed'] = True
                    if 'statistical' in title and 'mechanic' in title:
                        coverage['stat_mech_completed'] = True
                except Exception:
                    continue

        # Check for HGD speedup metrics
        qa_paper = self.base_dir / "artifacts" / "overleaf" / "qa_paper.json"
        if qa_paper.exists():
            try:
                data = json.loads(qa_paper.read_text())
                metrics = data.get('metrics', {})
                coverage['hgd_vs_sgd_ratio'] = metrics.get('step_speedup', 0.0)
            except Exception:
                pass

        # Check Rust speedup from benchmarks
        if self.evals_dir.exists():
            speedups = []
            for bench_file in self.evals_dir.glob("bench_*.json"):
                try:
                    data = json.loads(bench_file.read_text())
                    speedup = data.get('speedup_vs_baseline', 1.0)
                    if speedup > 1.0:
                        speedups.append(speedup)
                except Exception:
                    continue
            if speedups:
                coverage['rust_speedup_avg'] = sum(speedups) / len(speedups)

        return coverage

    def detect_research_gaps(self, metrics: Dict[str, Any],
                            ingestion: Dict[str, Any],
                            experiments: Dict[str, Any]) -> Dict[str, Any]:
        """Identify high-level research gaps and opportunities"""
        gaps = {}

        # 1. Ingestion backlog
        if ingestion.get('pending', 0) > 5:
            gaps['ingestion_backlog'] = {
                'count': ingestion['pending'],
                'priority': 'high',
                'reason': 'Multiple unprocessed research papers',
            }

        # 2. Missing JEPA integration
        if not experiments.get('jepa_completed'):
            gaps['jepa_missing'] = {
                'priority': 'high',
                'reason': 'JEPA-MNIST integration not yet in production',
                'expected_impact': 'Foundation for vision-based QA experiments',
            }

        # 3. Rust speedup below target
        if experiments.get('rust_speedup_avg', 1.0) < 2.0:
            gaps['rust_speedup_needed'] = {
                'current': experiments['rust_speedup_avg'],
                'target': 2.0,
                'priority': 'high',
                'reason': 'Rust kernels not achieving 2× target speedup',
            }

        # 4. HGD validation needed
        if experiments.get('hgd_vs_sgd_ratio', 0.0) > 0 and experiments['hgd_vs_sgd_ratio'] < 2.5:
            gaps['hgd_validation'] = {
                'current_speedup': experiments['hgd_vs_sgd_ratio'],
                'priority': 'medium',
                'reason': 'Need more HGD validation across datasets',
            }

        # 5. Cross-domain QA experiments missing
        topics = ingestion.get('papers_by_topic', {})
        if len(topics) > 2 and not any('cross' in str(task) for task in []):
            gaps['cross_domain_qa'] = {
                'available_domains': list(topics.keys()),
                'priority': 'medium',
                'reason': 'Opportunity for cross-domain QA validation',
            }

        # 6. Task throughput optimization
        perf = metrics.get('performance', {})
        if perf.get('tasks_per_hour', 0) > 0 and perf['tasks_per_hour'] < 200:
            gaps['throughput_optimization'] = {
                'current': perf['tasks_per_hour'],
                'target': 250,
                'priority': 'low',
                'reason': 'Throughput can be improved',
            }

        return gaps

    def build_campaign_tasks(self, gaps: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate high-level campaign tasks from research gaps"""
        tasks = []
        timestamp = datetime.now().strftime('%H%M%S')

        # Campaign: JEPA Bootstrap
        if 'jepa_missing' in gaps:
            task_id = f"campaign-qa_jepa-bootstrap-{timestamp}"
            tasks.append({
                'id': task_id,
                'project': 'research_campaigns',
                'title': 'QA-JEPA Production Integration Campaign',
                'description': '''
Complete end-to-end integration of JEPA with QA framework for MNIST.

This is a multi-phase campaign to bring JEPA (Joint-Embedding Predictive Architecture)
into production with HGD optimizer and QA modular arithmetic.

Expected outcomes:
- qa_jepa_core.py with full QA tuple integration
- HGD optimizer connected to JEPA latent space
- Benchmarks showing convergence speedup vs baseline
- Ablation studies on QA modular arithmetic impact
                '''.strip(),
                'source': 'research_director',
                'priority': 5.0,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'qalm',
                'created': datetime.now().isoformat(),
                'tags': ['campaign', 'jepa', 'vision', 'high_impact'],
                'metadata': {
                    'campaign_type': 'integration',
                    'expected_duration': '3-5 cycles',
                    'success_criteria': [
                        'qa_jepa_core.py implemented',
                        'HGD optimizer integration tested',
                        'Convergence benchmarks >baseline',
                        'Ablation study completed',
                    ],
                    'subtask_template': [
                        'Design QA-JEPA architecture',
                        'Implement core components',
                        'Integrate HGD optimizer',
                        'Run convergence benchmarks',
                        'Perform ablation studies',
                    ],
                },
                'plan': {
                    'steps': [
                        {
                            'description': 'Design QA-JEPA architecture with modular arithmetic',
                            'acceptance': 'Architecture diagram and API spec',
                            'effort': 120,
                        },
                        {
                            'description': 'Implement qa_jepa_core.py with QA tuple integration',
                            'acceptance': 'Core implementation with tests',
                            'effort': 240,
                        },
                        {
                            'description': 'Connect HGD optimizer to JEPA latent space',
                            'acceptance': 'HGD optimizer working with JEPA',
                            'effort': 180,
                        },
                        {
                            'description': 'Run convergence benchmarks and ablations',
                            'acceptance': 'Benchmark results showing speedup',
                            'effort': 120,
                        },
                    ],
                    'risks': [
                        'JEPA latent space may not benefit from modular arithmetic',
                        'Integration complexity higher than estimated',
                    ],
                    'dependencies': ['HGD optimizer stable', 'MNIST data available'],
                }
            })

        # Campaign: Rust Speedup Core
        if 'rust_speedup_needed' in gaps:
            gap_data = gaps['rust_speedup_needed']
            task_id = f"campaign-rust-speedup-core-{timestamp}"
            tasks.append({
                'id': task_id,
                'project': 'research_campaigns',
                'title': 'Rust Kernel Speedup Campaign (Target: 2×)',
                'description': f'''
Achieve consistent 2× speedup on core QA/HGD kernels through Rust optimization.

Current average speedup: {gap_data['current']:.2f}×
Target: {gap_data['target']}×

This campaign focuses on identifying, porting, and optimizing the hottest code paths
in the QA system to Rust with PyO3 bindings.
                '''.strip(),
                'source': 'research_director',
                'priority': 4.5,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'opencode',
                'created': datetime.now().isoformat(),
                'tags': ['campaign', 'rust', 'performance', 'optimization'],
                'metadata': {
                    'campaign_type': 'optimization',
                    'current_speedup': gap_data['current'],
                    'target_speedup': gap_data['target'],
                    'expected_duration': '2-4 cycles',
                    'success_criteria': [
                        'Identify top 5 slowest kernels',
                        'Port at least 3 to Rust',
                        'Achieve >=2× speedup on each',
                        'Update Python code to use Rust paths',
                    ],
                },
                'plan': {
                    'steps': [
                        {
                            'description': 'Profile Python code and identify top 5 hotspots',
                            'acceptance': 'Profiling report with timing data',
                            'effort': 60,
                        },
                        {
                            'description': 'Port identified hotspots to Rust',
                            'acceptance': '3+ Rust implementations with PyO3',
                            'effort': 180,
                        },
                        {
                            'description': 'Benchmark Rust vs Python versions',
                            'acceptance': 'Benchmark showing >=2× speedup',
                            'effort': 60,
                        },
                    ],
                    'risks': ['PyO3 overhead may limit speedup for small arrays'],
                    'dependencies': ['Rust toolchain', 'maturin build working'],
                }
            })

        # Campaign: Cross-Domain QA Validation
        if 'cross_domain_qa' in gaps:
            gap_data = gaps['cross_domain_qa']
            task_id = f"campaign-cross-domain-qa-{timestamp}"
            tasks.append({
                'id': task_id,
                'project': 'research_campaigns',
                'title': 'Cross-Domain QA Validation Campaign',
                'description': f'''
Validate QA framework across multiple domains to establish generality.

Available domains: {', '.join(gap_data['available_domains'])}

This campaign tests whether QA modular arithmetic and HGD optimizer
show consistent benefits across vision, quantum, compilation, and statistical domains.
                '''.strip(),
                'source': 'research_director',
                'priority': 3.5,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'qalm',
                'created': datetime.now().isoformat(),
                'tags': ['campaign', 'validation', 'cross_domain'],
                'metadata': {
                    'campaign_type': 'validation',
                    'domains': gap_data['available_domains'],
                    'expected_duration': '4-6 cycles',
                    'success_criteria': [
                        'Run QA experiments in 3+ domains',
                        'Document QA invariants per domain',
                        'Compare HGD vs baseline per domain',
                        'Identify domain-specific patterns',
                    ],
                },
            })

        # Campaign: Ingestion Processing
        if 'ingestion_backlog' in gaps:
            gap_data = gaps['ingestion_backlog']
            task_id = f"campaign-ingestion-sprint-{timestamp}"
            tasks.append({
                'id': task_id,
                'project': 'research_campaigns',
                'title': f'Ingestion Sprint: Process {gap_data["count"]} Pending Papers',
                'description': f'''
Process backlog of {gap_data["count"]} unprocessed research papers.

This sprint focuses on extracting, analyzing, and mapping all pending ingestion
papers to QA framework concepts, generating follow-up experiment tasks.
                '''.strip(),
                'source': 'research_director',
                'priority': 4.0,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'qalm',
                'created': datetime.now().isoformat(),
                'tags': ['campaign', 'ingestion', 'knowledge_base'],
                'metadata': {
                    'campaign_type': 'ingestion',
                    'paper_count': gap_data['count'],
                    'expected_duration': '2-3 cycles',
                    'success_criteria': [
                        f'Process {gap_data["count"]} papers',
                        'Create analysis scaffolds',
                        'Map concepts to QA framework',
                        'Generate experiment tasks',
                    ],
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
        print(f"  ✅ Created campaign: {task['id']}")

    def run(self):
        """Main research director execution"""
        print("🎯 QA Research Director: Analyzing research agenda...")

        # Load current state
        print("\n📊 Loading metrics...")
        metrics = self.load_metrics()

        print("📚 Analyzing ingestion status...")
        ingestion = self.analyze_ingestion_status()
        print(f"  Papers: {ingestion['total_papers']} total, {ingestion['extracted']} extracted, {ingestion['pending']} pending")

        print("🧪 Analyzing experiment coverage...")
        experiments = self.analyze_experiment_coverage()
        print(f"  JEPA: {'✅' if experiments['jepa_completed'] else '❌'}")
        print(f"  Rust speedup: {experiments['rust_speedup_avg']:.2f}×")
        print(f"  HGD vs SGD: {experiments['hgd_vs_sgd_ratio']:.2f}×")

        # Detect gaps
        print("\n🔍 Detecting research gaps...")
        gaps = self.detect_research_gaps(metrics, ingestion, experiments)

        if not gaps:
            print("✨ No significant research gaps detected - agenda is on track!")
            return []

        print(f"  Found {len(gaps)} research gaps:")
        for gap_name, gap_data in gaps.items():
            priority = gap_data.get('priority', 'unknown') if isinstance(gap_data, dict) else 'unknown'
            print(f"    • {gap_name} (priority: {priority})")

        # Generate campaigns
        print("\n🚀 Generating research campaigns...")
        campaigns = self.build_campaign_tasks(gaps)

        if not campaigns:
            print("  No campaigns generated")
            return []

        # Save campaigns
        print(f"\n✅ Saving {len(campaigns)} campaign tasks...")
        for campaign in campaigns:
            self.save_task(campaign)

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "ResearchDirector",
            "action": "research_agenda",
            "gaps_detected": len(gaps),
            "campaigns_generated": len(campaigns),
            "gap_types": list(gaps.keys()),
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"\n🎯 Research direction complete: {len(campaigns)} campaigns generated")
        return campaigns


if __name__ == "__main__":
    director = ResearchDirector()
    director.run()
