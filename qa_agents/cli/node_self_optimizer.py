#!/usr/bin/env python3
"""
QA Swarm Node Self-Optimizer
Detects local hardware and optimizes node configuration automatically

Each node runs this to:
- Detect CPU cores, RAM, GPU availability
- Optimize parallel execution settings
- Tune batch sizes for local memory
- Specialize based on hardware strengths
- Update node capabilities dynamically
"""

import os
import sys
import json
import psutil
import multiprocessing
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None

try:
    import torch
    TORCH_OK = True
except ImportError:
    TORCH_OK = False
    torch = None


class NodeSelfOptimizer:
    """Detects hardware and optimizes node configuration"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.config_file = self.base_dir / ".node_config.json"
        self.optimization_file = self.base_dir / ".node_optimization.json"

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect all hardware capabilities"""
        hardware = {
            'cpu_cores_physical': psutil.cpu_count(logical=False) or multiprocessing.cpu_count(),
            'cpu_cores_logical': psutil.cpu_count(logical=True) or multiprocessing.cpu_count(),
            'cpu_freq_mhz': None,
            'ram_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'ram_available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
            'disk_total_gb': round(psutil.disk_usage('/').total / (1024**3), 2),
            'disk_free_gb': round(psutil.disk_usage('/').free / (1024**3), 2),
            'gpu_available': False,
            'gpu_count': 0,
            'gpu_info': [],
        }

        # CPU frequency
        try:
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                hardware['cpu_freq_mhz'] = round(cpu_freq.max, 0)
        except Exception:
            pass

        # GPU detection
        if TORCH_OK:
            try:
                if torch.cuda.is_available():
                    hardware['gpu_available'] = True
                    hardware['gpu_count'] = torch.cuda.device_count()
                    for i in range(hardware['gpu_count']):
                        gpu_props = torch.cuda.get_device_properties(i)
                        hardware['gpu_info'].append({
                            'name': gpu_props.name,
                            'memory_gb': round(gpu_props.total_memory / (1024**3), 2),
                            'compute_capability': f"{gpu_props.major}.{gpu_props.minor}",
                        })
            except Exception:
                pass

        return hardware

    def calculate_optimal_settings(self, hardware: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate optimal execution settings based on hardware"""
        settings = {
            'parallel_workers': None,
            'batch_size': None,
            'memory_limit_gb': None,
            'use_gpu': False,
            'rust_enabled': True,
            'specializations': [],
            'optimization_level': 'auto',
        }

        # Parallel workers: Use 75% of logical cores, leave some for system
        cpu_cores = hardware['cpu_cores_logical']
        settings['parallel_workers'] = max(1, int(cpu_cores * 0.75))

        # Batch size: Scale with available RAM
        ram_gb = hardware['ram_available_gb']
        if ram_gb > 64:
            settings['batch_size'] = 256
        elif ram_gb > 32:
            settings['batch_size'] = 128
        elif ram_gb > 16:
            settings['batch_size'] = 64
        elif ram_gb > 8:
            settings['batch_size'] = 32
        else:
            settings['batch_size'] = 16

        # Memory limit: Use 80% of available RAM
        settings['memory_limit_gb'] = round(ram_gb * 0.8, 2)

        # GPU settings
        if hardware['gpu_available']:
            settings['use_gpu'] = True
            settings['specializations'].append('gpu_compute')
            settings['specializations'].append('deep_learning')
            settings['optimization_level'] = 'gpu'

        # CPU-based specializations
        if cpu_cores >= 24:
            settings['specializations'].append('high_parallelism')
            settings['specializations'].append('batch_processing')
        elif cpu_cores >= 12:
            settings['specializations'].append('parallel_compute')

        # Memory-based specializations
        if ram_gb >= 64:
            settings['specializations'].append('large_memory')
            settings['specializations'].append('data_intensive')
        elif ram_gb >= 32:
            settings['specializations'].append('memory_intensive')

        # Rust optimization
        if cpu_cores >= 8:
            settings['rust_enabled'] = True
            settings['specializations'].append('rust_benchmarks')

        return settings

    def update_node_config(self, hardware: Dict[str, Any], settings: Dict[str, Any]):
        """Update node configuration with hardware info and optimal settings"""
        config = {}

        # Load existing config if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except Exception:
                pass

        # Update hardware section
        config['hardware'] = hardware
        config['optimization'] = settings
        config['last_optimized'] = datetime.now().isoformat()

        # Update capabilities based on specializations
        if 'capabilities' not in config:
            config['capabilities'] = []

        # Add hardware-specific capabilities
        for spec in settings['specializations']:
            capability = spec.replace('_', '-')
            if capability not in config['capabilities']:
                config['capabilities'].append(capability)

        # Save updated config
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✅ Updated node config: {self.config_file}")

    def generate_environment_variables(self, settings: Dict[str, Any]) -> str:
        """Generate environment variable exports for optimal execution"""
        env_vars = []

        # Parallel execution
        env_vars.append(f"export OMP_NUM_THREADS={settings['parallel_workers']}")
        env_vars.append(f"export MKL_NUM_THREADS={settings['parallel_workers']}")
        env_vars.append(f"export OPENBLAS_NUM_THREADS={settings['parallel_workers']}")
        env_vars.append(f"export NUMEXPR_NUM_THREADS={settings['parallel_workers']}")

        # PyTorch settings
        env_vars.append(f"export TORCH_NUM_THREADS={settings['parallel_workers']}")
        if settings['use_gpu']:
            env_vars.append("export CUDA_VISIBLE_DEVICES=0")

        # Batch size
        env_vars.append(f"export QA_BATCH_SIZE={settings['batch_size']}")

        # Memory limit
        env_vars.append(f"export QA_MEMORY_LIMIT_GB={settings['memory_limit_gb']}")

        # Rust enable
        if settings['rust_enabled']:
            env_vars.append("export QA_USE_RUST=1")

        return "\n".join(env_vars)

    def create_optimized_makefile_override(self, hardware: Dict[str, Any], settings: Dict[str, Any]):
        """Create optimized Makefile override for this node"""
        makefile_path = self.base_dir / "Makefile.node.optimized"

        parallel_jobs = settings['parallel_workers']

        makefile_content = f"""# Auto-generated Optimized Makefile for this Node
# Generated: {datetime.now().isoformat()}
# Hardware: {hardware['cpu_cores_logical']} cores, {hardware['ram_total_gb']}GB RAM

VENV := qa_venv
PYTHON := $(VENV)/bin/python
PARALLEL_JOBS := {parallel_jobs}
BATCH_SIZE := {settings['batch_size']}
MEMORY_LIMIT := {settings['memory_limit_gb']}

# Environment optimization
export OMP_NUM_THREADS={parallel_jobs}
export MKL_NUM_THREADS={parallel_jobs}
export TORCH_NUM_THREADS={parallel_jobs}
export QA_BATCH_SIZE={settings['batch_size']}
export QA_MEMORY_LIMIT_GB={settings['memory_limit_gb']}
"""

        if settings['use_gpu']:
            makefile_content += """export CUDA_VISIBLE_DEVICES=0
export QA_USE_GPU=1
"""

        if settings['rust_enabled']:
            makefile_content += """export QA_USE_RUST=1
"""

        makefile_content += """
.PHONY: node-agent-loop-optimized

# Optimized agent loop with parallel execution
node-agent-loop-optimized:
\t@echo "🖥️  Optimized QA Compute Node ($(PARALLEL_JOBS) workers, batch=$(BATCH_SIZE))"
\t@echo "📥 Checking for assigned tasks..."
\t$(PYTHON) qa_agents/cli/executor.py --parallel=$(PARALLEL_JOBS) || true
\t@echo "👀 Reviewing completed work..."
\t$(PYTHON) qa_agents/cli/reviewer.py || true
"""

        if settings['rust_enabled']:
            makefile_content += """\t@echo "🦀 Running Rust benchmarks..."
\t$(MAKE) port-rust-all || true
"""

        if settings['use_gpu']:
            makefile_content += """\t@echo "🎮 Running GPU-accelerated tasks..."
\t$(PYTHON) qa_agents/cli/gpu_executor.py || true
"""

        makefile_content += """\t@echo "📊 Generating local metrics..."
\t$(PYTHON) qa_fast_eval.py || true
\t@echo "✅ Optimized compute node cycle complete"

# Optimized daemon (uses optimized loop)
node-daemon-optimized:
\t@echo "🔁 Starting optimized compute node daemon..."
\t@while true; do \\
\t\t$(MAKE) -f Makefile.node.optimized node-agent-loop-optimized || true; \\
\t\tsleep 3600; \\
\tdone
"""

        with open(makefile_path, 'w') as f:
            f.write(makefile_content)

        print(f"✅ Created optimized Makefile: {makefile_path}")

    def generate_optimization_report(self, hardware: Dict[str, Any], settings: Dict[str, Any]):
        """Generate human-readable optimization report"""
        report = []
        report.append("=" * 60)
        report.append("🔧 NODE SELF-OPTIMIZATION REPORT")
        report.append("=" * 60)
        report.append("")

        report.append("📊 HARDWARE DETECTED:")
        report.append(f"  CPU Cores: {hardware['cpu_cores_physical']} physical, {hardware['cpu_cores_logical']} logical")
        if hardware['cpu_freq_mhz']:
            report.append(f"  CPU Frequency: {hardware['cpu_freq_mhz']} MHz")
        report.append(f"  RAM: {hardware['ram_total_gb']} GB total, {hardware['ram_available_gb']} GB available")
        report.append(f"  Disk: {hardware['disk_free_gb']} GB free / {hardware['disk_total_gb']} GB total")

        if hardware['gpu_available']:
            report.append(f"  GPU: {hardware['gpu_count']} device(s) detected")
            for i, gpu in enumerate(hardware['gpu_info']):
                report.append(f"    GPU {i}: {gpu['name']} ({gpu['memory_gb']} GB)")
        else:
            report.append("  GPU: None detected")

        report.append("")
        report.append("⚙️  OPTIMAL SETTINGS:")
        report.append(f"  Parallel Workers: {settings['parallel_workers']}")
        report.append(f"  Batch Size: {settings['batch_size']}")
        report.append(f"  Memory Limit: {settings['memory_limit_gb']} GB")
        report.append(f"  GPU Enabled: {'Yes' if settings['use_gpu'] else 'No'}")
        report.append(f"  Rust Enabled: {'Yes' if settings['rust_enabled'] else 'No'}")
        report.append(f"  Optimization Level: {settings['optimization_level']}")

        report.append("")
        report.append("🎯 SPECIALIZATIONS:")
        if settings['specializations']:
            for spec in settings['specializations']:
                report.append(f"  • {spec}")
        else:
            report.append("  • general-purpose")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    def run(self):
        """Main self-optimization execution"""
        print("🔧 QA Swarm Node Self-Optimizer")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")

        # Step 1: Detect hardware
        print("1️⃣  Detecting hardware capabilities...")
        hardware = self.detect_hardware()
        print(f"  ✅ Detected: {hardware['cpu_cores_logical']} cores, {hardware['ram_total_gb']} GB RAM")
        if hardware['gpu_available']:
            print(f"  ✅ GPU detected: {hardware['gpu_count']} device(s)")
        print("")

        # Step 2: Calculate optimal settings
        print("2️⃣  Calculating optimal settings...")
        settings = self.calculate_optimal_settings(hardware)
        print(f"  ✅ Parallel workers: {settings['parallel_workers']}")
        print(f"  ✅ Batch size: {settings['batch_size']}")
        print(f"  ✅ Specializations: {len(settings['specializations'])}")
        print("")

        # Step 3: Update node configuration
        print("3️⃣  Updating node configuration...")
        self.update_node_config(hardware, settings)
        print("")

        # Step 4: Generate environment variables
        print("4️⃣  Generating environment variables...")
        env_vars = self.generate_environment_variables(settings)
        env_file = self.base_dir / ".node_env"
        with open(env_file, 'w') as f:
            f.write(env_vars)
        print(f"  ✅ Created: {env_file}")
        print("")

        # Step 5: Create optimized Makefile
        print("5️⃣  Creating optimized Makefile...")
        self.create_optimized_makefile_override(hardware, settings)
        print("")

        # Step 6: Generate report
        print("6️⃣  Generating optimization report...")
        report = self.generate_optimization_report(hardware, settings)
        print("")
        print(report)
        print("")

        # Save report
        report_file = self.base_dir / "node_optimization_report.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"  ✅ Report saved: {report_file}")
        print("")

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🎉 Node Self-Optimization Complete!")
        print("")
        print("To use optimized settings:")
        print("  source .node_env")
        print("  make -f Makefile.node.optimized node-daemon-optimized")
        print("")


if __name__ == "__main__":
    optimizer = NodeSelfOptimizer()
    optimizer.run()
