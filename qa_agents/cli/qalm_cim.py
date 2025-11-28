"""
Auto-refactor: normalize formatting for qalm_cim.py
"""

#!/usr/bin/env python3
"""
CIM-Enhanced QALM 2.0 Agent
Compute-in-Memory enhanced Markovian reasoning for knowledge base processing
"""

import torch
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import sys
import os
import numpy as np

# Import qa_markovian_integration dynamically
import importlib.util
qmi_path = Path(__file__).parent.parent.parent.parent / "qalm_2.0" / "qa_markovian_integration.py"
spec = importlib.util.spec_from_file_location("qa_markovian_integration", str(qmi_path))
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load qa_markovian_integration from {qmi_path}")
qmi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qmi)


class CIMQALMAgent:
    """CIM-Enhanced QALM 2.0 Agent for knowledge base processing"""

    def __init__(self, model_path: Optional[str] = None):
        self.base_dir = Path(__file__).parent.parent.parent
        self.qalm_dir = self.base_dir / "qalm_2.0"
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Initialize CIM components
        self.memory_manager = qmi.CIMMemoryManager()
        # Load existing knowledge base if available
        if Path(self.memory_manager.data_path).exists():
            try:
                self.memory_manager.mmap_file = open(self.memory_manager.data_path, "r+b")
                self.memory_manager.data_size = Path(self.memory_manager.data_path).stat().st_size
            except Exception as e:
                print(f"Warning: Could not load existing CIM data: {e}")
        self.pim_processor = qmi.PIMProcessor()
        self.vault_processor = qmi.ObsidianVaultProcessor()

        # Initialize QALM components
        self.policy = qmi.QAMarkovianPolicy()
        self.autoencoder = qmi.QAAutoencoder(latent_dim=64)  # Fallback implementation

        # Load trained model if available
        if model_path and Path(model_path).exists():
            checkpoint = torch.load(model_path, map_location='cpu')
            if 'policy' in checkpoint:
                self.policy.load_state_dict(checkpoint['policy'])
            if 'autoencoder' in checkpoint:
                self.autoencoder.load_state_dict(checkpoint['autoencoder'])
            print(f"Loaded CIM-QALM model from {model_path}")
        else:
            print("Using untrained CIM-QALM model (random weights)")

        self.policy.eval()
        if hasattr(self.autoencoder, 'eval'):
            self.autoencoder.eval()

    def process_knowledge_base(self, vault_paths: List[str], max_files: Optional[int] = None) -> Dict:
        """
        Process knowledge base files into QA representations
        """
        print(f"🔍 Processing knowledge base: {vault_paths}")

        # Update vault paths
        self.vault_processor.vault_paths = vault_paths

        # Process vault
        vault_data = self.vault_processor.process_vault_to_qa(max_files=max_files)

        # Store in CIM memory
        qa_tuples = [result['qa_tuple'] for result in vault_data]
        self.memory_manager.store_qa_tuples(qa_tuples)

        return {
            'files_processed': len(vault_data),
            'qa_tuples_stored': len(qa_tuples),
            'memory_path': str(self.memory_manager.data_path),
            'sample_files': [r['file'] for r in vault_data[:5]]
        }

    def reason_on_knowledge(self, query_tuple: List[float], context_tuples: Optional[List[List[float]]] = None) -> Dict:
        """
        Perform Markovian reasoning on knowledge base
        """
        # Load context from CIM memory if available
        if context_tuples is None:
            context_tuples = self.memory_manager.load_qa_tuples(100)  # Load up to 100 context tuples
            if not context_tuples:
                context_tuples = [[1, 1, 2, 3]]  # Default fallback

        # Initialize environment with loaded context
        env = qmi.QAMarkovianEnv(self.autoencoder, max_iters=min(24, len(context_tuples)))

        # Perform reasoning
        traces, rewards = env.rollout(query_tuple, lambda z: self.policy(z))

        # Extract final reasoning result
        final_tuple = traces[-1][1].detach().cpu().numpy() if traces else np.array(query_tuple)
        final_reward = float(rewards[-1]) if rewards else 0.0

        return {
            'query_tuple': query_tuple,
            'context_size': len(context_tuples),
            'reasoning_steps': len(traces),
            'final_tuple': final_tuple.tolist(),
            'final_reward': final_reward,
            'convergence': final_reward >= 0.99  # Perfect convergence
        }

    def analyze_qa_knowledge(self, analysis_type: str = "structure") -> Dict:
        """
        Analyze the knowledge base structure and patterns
        """
        # Load all stored QA tuples
        qa_tuples = self.memory_manager.load_qa_tuples(100)  # Load up to 100 tuples (stored amount)

        if not qa_tuples:
            return {'error': 'No knowledge base loaded'}

        tuples_array = np.array(qa_tuples)

        analysis = {
            'total_tuples': len(qa_tuples),
            'tuple_stats': {
                'mean': tuples_array.mean(axis=0).tolist(),
                'std': tuples_array.std(axis=0).tolist(),
                'min': tuples_array.min(axis=0).tolist(),
                'max': tuples_array.max(axis=0).tolist()
            }
        }

        if analysis_type == "invariants":
            # Check QA invariants across tuples
            invariants_satisfied = []
            for qa_tuple in qa_tuples[:100]:  # Check first 100
                b, e, d, a = qa_tuple
                invariant1 = abs(b + e - d) < 0.1  # Approximate check
                invariant2 = abs(b + 2*e - a) < 0.1
                invariants_satisfied.append(invariant1 and invariant2)

            analysis['invariant_compliance'] = {
                'checked_tuples': len(invariants_satisfied),
                'satisfied_count': sum(invariants_satisfied),
                'compliance_rate': sum(invariants_satisfied) / len(invariants_satisfied)
            }

        return analysis

    def generate_insights(self, focus_area: str = "mathematical") -> Dict:
        """
        Generate insights from learned knowledge patterns
        """
        # Load knowledge base
        qa_tuples = self.memory_manager.load_qa_tuples(100)

        if not qa_tuples:
            return {'error': 'No knowledge base available for insight generation'}

        # Perform reasoning on representative tuples
        insights = []

        # Sample diverse tuples for insight generation
        sample_indices = np.linspace(0, len(qa_tuples)-1, min(10, len(qa_tuples)), dtype=int)
        sample_tuples = [qa_tuples[i] for i in sample_indices]

        for i, qa_tuple in enumerate(sample_tuples):
            reasoning_result = self.reason_on_knowledge(qa_tuple, qa_tuples)

            insight = {
                'tuple_index': int(sample_indices[i]),
                'original_tuple': qa_tuple,
                'reasoned_tuple': reasoning_result['final_tuple'],
                'convergence_quality': reasoning_result['final_reward'],
                'insight_type': focus_area
            }

            if focus_area == "mathematical":
                # Analyze mathematical properties
                b, e, d, a = reasoning_result['final_tuple']
                insight['mathematical_properties'] = {
                    'sum_invariant': b + e,
                    'product_invariant': b * e,
                    'harmonic_mean': 2 / (1/b + 1/e) if b != 0 and e != 0 else 0,
                    'convergence': reasoning_result['convergence']
                }

            insights.append(insight)

        return {
            'focus_area': focus_area,
            'insights_generated': len(insights),
            'sample_insights': insights[:3],  # Return first 3 for brevity
            'overall_convergence_rate': sum(1 for i in insights if i.get('convergence_quality', 0) >= 0.99) / len(insights)
        }

    def run(self, task: Dict) -> Dict:
        """
        Main agent execution for task processing
        """
        print("🧠 CIM-QALM Agent: Processing task...")

        task_type = task.get('type', 'reasoning')
        content = task.get('content', {})
        qa_tuple = task.get('qa_tuple')

        result = {
            'agent': 'CIM-QALM',
            'task_id': task.get('id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'success': True
        }

        try:
            if task_type == 'process_knowledge_base':
                vault_paths = content.get('vault_paths', ['/home/player2/signal_experiments/QAnotes'])
                max_files = content.get('max_files')
                result['output'] = self.process_knowledge_base(vault_paths, max_files)

            elif task_type == 'reason_on_knowledge':
                query_tuple = qa_tuple or content.get('query_tuple', [1, 1, 2, 3])
                context_tuples = content.get('context_tuples')
                result['output'] = self.reason_on_knowledge(query_tuple, context_tuples)

            elif task_type == 'analyze_knowledge':
                analysis_type = content.get('analysis_type', 'structure')
                result['output'] = self.analyze_qa_knowledge(analysis_type)

            elif task_type == 'generate_insights':
                focus_area = content.get('focus_area', 'mathematical')
                result['output'] = self.generate_insights(focus_area)

            else:
                # General reasoning task
                query_tuple = qa_tuple or [1, 1, 2, 3]
                result['output'] = self.reason_on_knowledge(query_tuple)

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            print(f"❌ CIM-QALM Agent error: {e}")

        # Log the interaction
        log_entry = {
            'timestamp': result['timestamp'],
            'agent': 'CIM-QALM',
            'task_type': task_type,
            'success': result['success'],
            'output_length': len(str(result.get('output', '')))
        }

        log_file = self.logs_dir / "cim_qalm_agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"✅ CIM-QALM Agent completed task: {task_type}")
        return result


def main():
    """CLI interface for CIM-QALM agent"""
    import argparse

    parser = argparse.ArgumentParser(description='CIM-Enhanced QALM 2.0 Agent')
    parser.add_argument('--model-path', help='Path to trained model checkpoint')
    parser.add_argument('--task-file', help='YAML task file to process')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--vault-path', help='Path to knowledge base vault')

    args = parser.parse_args()

    # Initialize agent
    agent = CIMQALMAgent(args.model_path)

    if args.interactive:
        print("🧠 CIM-QALM Interactive Mode")
        print("Commands:")
        print("  process <vault_path> - Process knowledge base")
        print("  reason <b,e,d,a> - Reason on QA tuple")
        print("  analyze - Analyze knowledge structure")
        print("  insights - Generate mathematical insights")
        print("  quit - Exit")
        print()

        while True:
            try:
                cmd = input("> ").strip()

                if cmd.lower() in ['quit', 'exit', 'q']:
                    break

                if cmd.startswith('process '):
                    vault_path = cmd[8:].strip()
                    if vault_path:
                        result = agent.process_knowledge_base([vault_path])
                        print(f"Processed: {result}")
                    else:
                        print("Usage: process <vault_path>")

                elif cmd.startswith('reason '):
                    tuple_str = cmd[7:].strip()
                    try:
                        qa_tuple = [float(x.strip()) for x in tuple_str.split(',')]
                        result = agent.reason_on_knowledge(qa_tuple)
                        print(f"Reasoning result: {result}")
                    except:
                        print("Usage: reason <b,e,d,a> (comma-separated floats)")

                elif cmd == 'analyze':
                    result = agent.analyze_qa_knowledge()
                    print(f"Knowledge analysis: {json.dumps(result, indent=2)}")

                elif cmd == 'insights':
                    result = agent.generate_insights()
                    print(f"Generated insights: {json.dumps(result, indent=2)}")

                else:
                    print("Unknown command. Type 'help' for commands.")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

    elif args.task_file:
        # Process task file
        with open(args.task_file, 'r') as f:
            task = yaml.safe_load(f)

        result = agent.run(task)
        print(json.dumps(result, indent=2))

    else:
        # Demo mode
        print("🧠 CIM-QALM Agent Demo")

        # Test knowledge base processing
        print("1. Processing Obsidian vault...")
        vault_result = agent.process_knowledge_base(['/home/player2/signal_experiments/QAnotes'], max_files=50)
        print(f"   Result: {vault_result}")

        # Test reasoning
        print("\n2. Testing reasoning on QA tuple [1,1,2,3]...")
        reasoning_result = agent.reason_on_knowledge([1, 1, 2, 3])
        print(f"   Result: {reasoning_result}")

        # Test analysis
        print("\n3. Analyzing knowledge structure...")
        analysis_result = agent.analyze_qa_knowledge()
        print(f"   Result: {json.dumps(analysis_result, indent=2)}")


if __name__ == "__main__":
    main()
