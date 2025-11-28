"""
Auto-refactor: normalize formatting for qalm.py
"""

#!/usr/bin/env python3
"""
QA Language Model Agent v1.0
Local QA-specialized language model for mathematical reasoning
"""

import torch
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import sys
import os

# Add the qa_lab directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_model_architecture import QALanguageModel, QAConfig
from qa_training_pipeline import QADataset


class QALMAgent:
    """QA Language Model agent for local mathematical reasoning"""

    def __init__(self, model_path: Optional[str] = None):
        self.base_dir = Path(__file__).parent.parent.parent
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Load trained model if path provided (SELF-IMPROVEMENT!)
        if model_path and Path(model_path).exists():
            # Trust our own trained models (self-improvement loop!)
            checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)

            # Use the config saved in checkpoint if available
            if 'config' in checkpoint:
                self.config = checkpoint['config']
                print(f"✅ Loaded config from checkpoint: {self.config.hidden_size}D hidden, {self.config.num_hidden_layers} layers")
            else:
                # Fallback to default config for old checkpoints
                self.config = QAConfig(
                    vocab_size=10000,
                    hidden_size=256,
                    num_hidden_layers=4,
                    num_attention_heads=4,
                    intermediate_size=512,
                )
                print("⚠️ No config in checkpoint, using default")

            # Create model with loaded config
            self.model = QALanguageModel(self.config)
            self.model.to(self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])

            # Load vocabulary from checkpoint if available
            if 'token_to_id' in checkpoint and 'id_to_token' in checkpoint:
                self.token_to_id = checkpoint['token_to_id']
                self.id_to_token = checkpoint['id_to_token']
                print(f"✅ Loaded self-improved QALM model from {Path(model_path).name} (vocab: {len(self.token_to_id)})")
            else:
                # Fallback to dataset vocab
                dummy_dataset = QADataset(self.base_dir / "qa_data" / "qa_training_dataset.json")
                self.token_to_id = dummy_dataset.token_to_id
                self.id_to_token = dummy_dataset.id_to_token
                print(f"✅ Loaded model from {Path(model_path).name}, using dataset vocab")
        else:
            # No checkpoint - initialize with default config
            self.config = QAConfig(
                vocab_size=10000,  # Smaller vocab for testing
                hidden_size=256,   # Smaller model for local inference
                num_hidden_layers=4,
                num_attention_heads=4,
                intermediate_size=512,
            )
            self.model = QALanguageModel(self.config)
            self.model.to(self.device)
            print("Using untrained QALM model (random weights)")

            # Setup vocabulary (same as training)
            dummy_dataset = QADataset(self.base_dir / "qa_data" / "qa_training_dataset.json")
            self.token_to_id = dummy_dataset.token_to_id
            self.id_to_token = dummy_dataset.id_to_token

        self.model.eval()

    def tokenize(self, text: str, max_length: int = None) -> torch.Tensor:
        """Tokenize text input"""
        # Use model's max position embeddings if not specified
        if max_length is None:
            max_length = getattr(self.config, 'max_position_embeddings', 512)

        tokens = ['<bos>'] + text.split()[:max_length-2] + ['<eos>']
        token_ids = [self.token_to_id.get(token, self.token_to_id['<unk>']) for token in tokens]

        # Pad to max_length
        attention_mask = [1] * len(token_ids) + [0] * (max_length - len(token_ids))
        token_ids += [self.token_to_id['<pad>']] * (max_length - len(token_ids))

        return torch.tensor(token_ids, dtype=torch.long), torch.tensor(attention_mask, dtype=torch.long)

    def generate_response(self, prompt: str, qa_tuple: Optional[List[float]] = None, max_length: int = 100) -> str:
        """
        Generate response using QALM
        """
        # Tokenize input (uses model's max_position_embeddings)
        input_ids, attention_mask = self.tokenize(prompt)
        input_ids = input_ids.unsqueeze(0).to(self.device)  # Add batch dimension
        attention_mask = attention_mask.unsqueeze(0).to(self.device)

        # Prepare QA tuple if provided
        qa_tuples = None
        if qa_tuple:
            qa_tensor = torch.tensor(qa_tuple, dtype=torch.float).unsqueeze(0).unsqueeze(0)  # (1, 1, 4)
            qa_tuples = qa_tensor.expand(1, input_ids.size(1), -1).to(self.device)  # Broadcast to actual sequence length

        # Generate response
        with torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                qa_tuples=qa_tuples,
                attention_mask=attention_mask
            )

            logits = outputs[0]  # (batch, seq, vocab)
            # Simple greedy decoding for now
            predicted_tokens = torch.argmax(logits, dim=-1)[0]  # (seq,)

            # Convert back to text
            response_tokens = []
            for token_id in predicted_tokens:
                token = self.id_to_token.get(token_id.item(), '<unk>')
                if token == '<eos>':
                    break
                if token not in ['<bos>', '<pad>']:
                    response_tokens.append(token)

            response = ' '.join(response_tokens)

        return response if response else "QALM generated response (model needs training for meaningful output)"

    def analyze_qa_tuple(self, qa_tuple: List[float]) -> Dict:
        """
        Analyze a QA tuple using the model
        """
        b, e, d, a = qa_tuple

        # Check invariants
        invariants = {
            'closure_b_e_d': abs((b + e) - d) < 1e-6,
            'closure_e_d_a': abs((e + d) - a) < 1e-6,
            'invariant_J': abs(b * d - (b + e) * d + e * d) < 1e-6,  # J = b·d
            'invariant_K': abs(d * a - d * (e + d) + e * d) < 1e-6,  # K = d·a
            'invariant_X': abs(e * d - e * d) < 1e-6,  # X = e·d (should be 0)
        }

        # Generate analysis prompt
        prompt = f"Analyze QA tuple ({b}, {e}, {d}, {a}) for mathematical properties and invariants."

        analysis = self.generate_response(prompt, qa_tuple)

        return {
            'qa_tuple': qa_tuple,
            'invariants_satisfied': invariants,
            'model_analysis': analysis,
            'is_valid_qa_tuple': all(invariants.values())
        }

    def generate_theorem(self, qa_tuple: List[float]) -> Dict:
        """
        Generate a mathematical theorem from QA tuple
        """
        prompt = f"Generate a mathematical theorem based on QA tuple structure and invariants."

        theorem_text = self.generate_response(prompt, qa_tuple)

        return {
            'qa_tuple': qa_tuple,
            'theorem': theorem_text,
            'generated_at': datetime.now().isoformat()
        }

    def verify_proof(self, proof_text: str, qa_tuple: Optional[List[float]] = None) -> Dict:
        """
        Verify a mathematical proof
        """
        prompt = f"Verify the correctness of this mathematical proof: {proof_text}"

        verification = self.generate_response(prompt, qa_tuple)

        return {
            'proof_text': proof_text,
            'qa_tuple': qa_tuple,
            'verification': verification,
            'is_valid': 'correct' in verification.lower() or 'valid' in verification.lower()
        }

    def run(self, task: Dict) -> Dict:
        """
        Main agent execution for task processing
        """
        print("🤖 QALM Agent: Processing task...")

        task_type = task.get('type', 'analysis')
        content = task.get('content', '')
        qa_tuple = task.get('qa_tuple')

        result = {
            'agent': 'QALM',
            'task_id': task.get('id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'success': True
        }

        try:
            if task_type == 'analyze_qa_tuple' and qa_tuple:
                result['output'] = self.analyze_qa_tuple(qa_tuple)

            elif task_type == 'generate_theorem' and qa_tuple:
                result['output'] = self.generate_theorem(qa_tuple)

            elif task_type == 'verify_proof':
                result['output'] = self.verify_proof(content, qa_tuple)

            else:
                # General QA reasoning task
                response = self.generate_response(content, qa_tuple)
                result['output'] = {'response': response}

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            print(f"❌ QALM Agent error: {e}")

        # Log the interaction
        log_entry = {
            'timestamp': result['timestamp'],
            'agent': 'QALM',
            'task_type': task_type,
            'success': result['success'],
            'output_length': len(str(result.get('output', '')))
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"✅ QALM Agent completed task: {task_type}")
        return result


def main():
    """CLI interface for QALM agent"""
    import argparse

    parser = argparse.ArgumentParser(description='QA Language Model Agent')
    parser.add_argument('--model-path', help='Path to trained model checkpoint')
    parser.add_argument('--task-file', help='YAML task file to process')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')

    args = parser.parse_args()

    # Initialize agent
    agent = QALMAgent(args.model_path)

    if args.interactive:
        print("🤖 QALM Interactive Mode")
        print("Enter prompts (or 'quit' to exit):")

        while True:
            try:
                prompt = input("> ")
                if prompt.lower() in ['quit', 'exit', 'q']:
                    break

                # Check if QA tuple is provided
                qa_tuple = None
                if '[' in prompt and ']' in prompt:
                    # Extract QA tuple from prompt like "Analyze [1,1,2,3]"
                    import re
                    tuple_match = re.search(r'\[([0-9,\.\s]+)\]', prompt)
                    if tuple_match:
                        try:
                            qa_tuple = [float(x.strip()) for x in tuple_match.group(1).split(',')]
                            prompt = prompt.replace(tuple_match.group(0), '').strip()
                        except:
                            pass

                response = agent.generate_response(prompt, qa_tuple)
                print(f"QALM: {response}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

    elif args.task_file:
        # Process task file
        with open(args.task_file, 'r') as f:
            task = yaml.safe_load(f)

        result = agent.run(task)

        # Output result
        print(json.dumps(result, indent=2))

    else:
        # Demo mode
        print("🤖 QALM Agent Demo")

        # Test QA tuple analysis
        test_tuple = [1.0, 1.0, 2.0, 3.0]  # Fibonacci QA tuple
        analysis = agent.analyze_qa_tuple(test_tuple)
        print(f"QA Tuple Analysis: {json.dumps(analysis, indent=2)}")

        # Test theorem generation
        theorem = agent.generate_theorem(test_tuple)
        print(f"Generated Theorem: {theorem['theorem']}")


if __name__ == "__main__":
    main()
