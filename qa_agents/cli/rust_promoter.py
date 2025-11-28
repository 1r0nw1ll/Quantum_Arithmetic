#!/usr/bin/env python3
"""
QA Rust Kernel Promotion Engine
Automatically detects slow Python code and generates Rust port tasks

This agent profiles Python functions, identifies performance bottlenecks,
and creates tasks to port hot paths to Rust with PyO3.
"""

import json
import sys
import re
import ast
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
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


class RustPromoter:
    """Automatic Rust kernel promotion based on performance profiling"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.tasks_dir = self.base_dir / "tasks"
        self.inbox = self.tasks_dir / "inbox"
        self.logs_dir = self.base_dir / "logs"
        self.src_dir = self.base_dir
        self.inbox.mkdir(parents=True, exist_ok=True)

        # Profiling data (simulated - in production would use cProfile)
        self.hotspots = []

    def save_task(self, task: dict, filename: str):
        """Save task to inbox"""
        task_file = self.inbox / filename
        if YAML_OK:
            with open(task_file, 'w') as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
        print(f"  ✅ Created Rust port task: {filename}")

    def scan_for_compute_hotspots(self) -> List[Dict]:
        """Scan Python codebase for computational hotspots"""
        hotspots = []

        # Target patterns that are good Rust candidates
        rust_candidates = [
            # Numerical kernels
            r'def\s+(e8_scores|qa_rank|harmonic_index|compute_.*_matrix)',
            # Inner loops with numpy
            r'for\s+\w+\s+in\s+range.*np\.',
            # Matrix operations
            r'np\.(dot|matmul|einsum|inner)',
            # Statistical computations
            r'def\s+(compute_stats|calculate_.*|score_.*)',
        ]

        python_files = [
            'qa_fast_eval.py',
            'qa_tuple_engine.py',
            'qa_inner_product_matrix.py',
            'harmonic_loss.py',
            'harmonic_index.py',
            'qa_rank.py',
        ]

        for py_file in python_files:
            file_path = self.base_dir / py_file
            if not file_path.exists():
                continue

            try:
                source = file_path.read_text(encoding='utf-8')

                # Find function definitions
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_name = node.name
                        func_start = node.lineno

                        # Get function source
                        func_lines = source.split('\n')[func_start-1:func_start+20]
                        func_snippet = '\n'.join(func_lines[:10])

                        # Check if matches Rust candidate patterns
                        for pattern in rust_candidates:
                            if re.search(pattern, func_snippet, re.MULTILINE):
                                hotspots.append({
                                    'file': str(file_path),
                                    'function': func_name,
                                    'line': func_start,
                                    'snippet': func_snippet,
                                    'pattern_matched': pattern,
                                })
                                break

            except Exception as e:
                print(f"  ⚠️  Error scanning {py_file}: {e}")
                continue

        return hotspots

    def check_existing_rust_ports(self) -> set:
        """Check which functions already have Rust implementations"""
        rust_lib = self.base_dir / "src" / "lib.rs"
        ported_functions = set()

        if rust_lib.exists():
            try:
                rust_source = rust_lib.read_text(encoding='utf-8')

                # Find PyO3 function exports
                pyo3_funcs = re.findall(r'#\[pyfunction\]\s*(?:pub\s+)?fn\s+(\w+)', rust_source)
                ported_functions.update(pyo3_funcs)

                # Find modules
                rust_modules = re.findall(r'#\[pymodule\]\s*fn\s+(\w+)', rust_source)
                ported_functions.update(rust_modules)

            except Exception as e:
                print(f"  ⚠️  Error reading Rust lib: {e}")

        return ported_functions

    def generate_rust_port_tasks(self) -> List[Dict]:
        """Generate tasks to port Python hotspots to Rust"""
        tasks = []

        print("  🔍 Scanning for compute hotspots...")
        hotspots = self.scan_for_compute_hotspots()
        print(f"  Found {len(hotspots)} potential Rust candidates")

        print("  📦 Checking existing Rust ports...")
        ported = self.check_existing_rust_ports()
        print(f"  Already ported: {len(ported)} functions")

        # Filter out already-ported functions
        new_hotspots = [h for h in hotspots if h['function'] not in ported]

        print(f"  🎯 Identified {len(new_hotspots)} new port opportunities")

        # Generate tasks for top candidates
        for hotspot in new_hotspots[:5]:  # Limit to top 5
            task_id = f"rust-port-{hotspot['function']}-{datetime.now().strftime('%H%M%S')}"

            task = {
                'id': task_id,
                'project': 'rust_optimization',
                'title': f"Port {hotspot['function']} to Rust for performance",
                'description': f"""
Port Python function '{hotspot['function']}' to Rust with PyO3 bindings.

Source: {Path(hotspot['file']).name}:{hotspot['line']}
Pattern: {hotspot['pattern_matched']}

Expected speedup: 2-10x for numerical kernels.

Implementation steps:
1. Create Rust function in src/lib.rs
2. Add PyO3 bindings with numpy support
3. Write Rust unit tests
4. Create Python wrapper in {Path(hotspot['file']).name}
5. Benchmark Python vs Rust versions
6. Update imports to use Rust when available
                """.strip(),
                'source': 'rust_promoter',
                'priority': 4.5,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'opencode',
                'created': datetime.now().isoformat(),
                'tags': ['rust', 'optimization', 'performance', 'auto_generated'],
                'metadata': {
                    'target_file': hotspot['file'],
                    'target_function': hotspot['function'],
                    'target_line': hotspot['line'],
                    'pattern_matched': hotspot['pattern_matched'],
                    'promotion_type': 'rust_port',
                    'expected_speedup': '2-10x',
                },
                'plan': {
                    'steps': [
                        {
                            'description': 'Implement Rust kernel in src/lib.rs',
                            'acceptance': 'Rust function compiles with PyO3 bindings',
                            'tools': ['rust', 'cargo', 'pyo3'],
                            'effort': 60,
                        },
                        {
                            'description': 'Write benchmarks comparing Python vs Rust',
                            'acceptance': 'Benchmark shows >2x speedup',
                            'tools': ['criterion', 'pytest-benchmark'],
                            'effort': 30,
                        },
                        {
                            'description': 'Integrate Rust kernel into Python codebase',
                            'acceptance': 'Python imports Rust, tests pass',
                            'tools': ['maturin', 'pytest'],
                            'effort': 30,
                        },
                    ],
                    'risks': [
                        'Rust implementation may not be faster for small inputs',
                        'PyO3 overhead may dominate for simple operations',
                    ],
                    'dependencies': ['Rust toolchain installed', 'maturin configured'],
                }
            }
            tasks.append(task)

        return tasks

    def analyze_benchmark_results(self) -> List[Dict]:
        """Analyze existing benchmarks to identify promotion opportunities"""
        tasks = []

        # Check for benchmark results in artifacts/evals
        evals_dir = self.base_dir / "artifacts" / "evals"
        if not evals_dir.exists():
            return tasks

        # Look for benchmark JSONs
        benchmark_files = list(evals_dir.glob("bench_*.json"))

        for bench_file in benchmark_files:
            try:
                with open(bench_file, 'r') as f:
                    data = json.load(f)

                # Check if benchmark shows slow performance
                # Different benchmark formats have different structures
                if isinstance(data, dict):
                    # Look for timing data
                    time_sec = data.get('time_sec') or data.get('time_sec_baseline') or data.get('elapsed_sec')

                    if time_sec and time_sec > 1.0:  # > 1 second is slow
                        # Generate optimization task
                        task_id = f"optimize-{bench_file.stem}-{datetime.now().strftime('%H%M%S')}"

                        task = {
                            'id': task_id,
                            'project': 'rust_optimization',
                            'title': f'Optimize slow benchmark: {bench_file.stem}',
                            'description': f"""
Benchmark '{bench_file.stem}' shows slow performance ({time_sec:.2f}s).

Consider:
1. Port to Rust
2. Add caching/memoization
3. Parallelize with rayon
4. Optimize algorithm complexity

Benchmark file: {bench_file}
                            """.strip(),
                            'source': 'rust_promoter',
                            'priority': 4.0,
                            'status': 'pending',
                            'lane': 'green',
                            'assignee': 'opencode',
                            'created': datetime.now().isoformat(),
                            'tags': ['optimization', 'benchmark', 'performance'],
                            'metadata': {
                                'benchmark_file': str(bench_file),
                                'current_time_sec': time_sec,
                                'promotion_type': 'benchmark_optimization',
                                'target_speedup': '2-5x',
                            }
                        }
                        tasks.append(task)

            except Exception as e:
                print(f"  ⚠️  Error reading benchmark {bench_file}: {e}")
                continue

        return tasks

    def check_rust_build_health(self) -> List[Dict]:
        """Verify Rust build infrastructure is healthy"""
        tasks = []

        cargo_toml = self.base_dir / "Cargo.toml"
        src_lib = self.base_dir / "src" / "lib.rs"

        if not cargo_toml.exists():
            task_id = f"rust-setup-{datetime.now().strftime('%H%M%S')}"
            task = {
                'id': task_id,
                'project': 'rust_infrastructure',
                'title': 'Initialize Rust project infrastructure',
                'description': 'Set up Cargo.toml, src/lib.rs, and PyO3 configuration for Rust kernels.',
                'source': 'rust_promoter',
                'priority': 5.0,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'opencode',
                'created': datetime.now().isoformat(),
                'tags': ['rust', 'infrastructure', 'setup'],
                'metadata': {
                    'promotion_type': 'rust_setup',
                }
            }
            tasks.append(task)

        return tasks

    def run(self):
        """Main Rust promotion execution"""
        print("🦀 QA Rust Kernel Promoter: Analyzing optimization opportunities...")

        all_tasks = []

        # Check infrastructure
        print("\n🔧 Checking Rust infrastructure...")
        infra_tasks = self.check_rust_build_health()
        all_tasks.extend(infra_tasks)
        print(f"  Generated {len(infra_tasks)} infrastructure tasks")

        # Only proceed with porting if infrastructure exists
        if not infra_tasks:
            print("\n📊 Analyzing benchmarks...")
            bench_tasks = self.analyze_benchmark_results()
            all_tasks.extend(bench_tasks)
            print(f"  Generated {len(bench_tasks)} benchmark optimization tasks")

            print("\n🔥 Scanning for hotspots...")
            port_tasks = self.generate_rust_port_tasks()
            all_tasks.extend(port_tasks)
            print(f"  Generated {len(port_tasks)} Rust port tasks")

        # Save all generated tasks
        if all_tasks:
            print(f"\n✅ Generating {len(all_tasks)} Rust promotion tasks...")
            for task in all_tasks:
                filename = f"{task['id']}.yaml"
                self.save_task(task, filename)

            # Log activity
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "agent": "RustPromoter",
                "action": "rust_promotion",
                "tasks_generated": len(all_tasks),
                "categories": {
                    "infrastructure": len(infra_tasks),
                    "benchmark_opts": len(bench_tasks) if not infra_tasks else 0,
                    "hotspot_ports": len(port_tasks) if not infra_tasks else 0,
                }
            }

            log_file = self.logs_dir / "agent_runs.jsonl"
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

            print(f"\n🦀 Rust promotion complete: {len(all_tasks)} optimization tasks generated")
        else:
            print("\n✨ No Rust promotion tasks needed - codebase is optimized!")

        return all_tasks


if __name__ == "__main__":
    promoter = RustPromoter()
    promoter.run()
