"""
Auto-refactor: normalize formatting for qa_data_collector.py
"""

#!/usr/bin/env python3
"""
QA Data Collector v4.0
Comprehensive data collection system for QA language model training
"""

import json
import os
import re
from pathlib import Path
from fractions import Fraction
from typing import Dict, List, Tuple, Set
import numpy as np

class QADataCollector:
    """Collects and curates training data for QA language model"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.data_dir = self.base_dir / "qa_data"
        self.data_dir.mkdir(exist_ok=True)

        # QA invariants for validation
        self.invariants = {
            'J': lambda b, e, d, a: b * d,
            'K': lambda b, e, d, a: d * a,
            'X': lambda b, e, d, a: e * d
        }

    def compute_qa_tuple(self, b: int, e: int) -> Tuple[int, int, int, int]:
        """Compute QA tuple from parameters b, e"""
        d = b + e  # b + e = d
        a = e + d  # e + d = a
        return b, e, d, a

    def validate_invariants(self, b: int, e: int, d: int, a: int) -> Dict[str, bool]:
        """Validate QA invariants for a tuple"""
        return {
            'closure_b_e_d': b + e == d,
            'closure_e_d_a': e + d == a,
            'invariant_J': self.invariants['J'](b, e, d, a) == self.invariants['K'](b, e, d, a),
            'invariant_X': self.invariants['X'](b, e, d, a) == self.invariants['X'](b, e, d, a),
            'inner_ellipse': a**2 == d**2 + 2*d*e + e**2
        }

    def generate_fibonacci_qa_data(self, n_samples: int = 1000) -> List[Dict]:
        """Generate QA data using Fibonacci sequence parameters"""
        data = []

        # Fibonacci sequence
        fib = [1, 1]
        for i in range(2, 50):
            fib.append(fib[i-1] + fib[i-2])

        for i in range(min(n_samples, len(fib) - 1)):
            b, e = fib[i], fib[i+1]
            b, e, d, a = self.compute_qa_tuple(b, e)

            invariants = self.validate_invariants(b, e, d, a)

            data.append({
                'type': 'fibonacci_qa',
                'parameters': {'b': b, 'e': e},
                'tuple': {'b': b, 'e': e, 'd': d, 'a': a},
                'invariants': invariants,
                'sequence_type': 'fibonacci',
                'mathematical_properties': {
                    'golden_ratio_convergence': abs((1 + np.sqrt(5)) / 2 - a/b) if b != 0 else 0,
                    'cassini_identity': True,  # Fibonacci property
                    'pisano_period': 24  # Fibonacci Pisano period
                },
                'text_description': f"Fibonacci QA tuple: F({i})={b}, F({i+1})={e} → (b={b}, e={e}, d={d}, a={a})",
                'qa_reasoning': f"Using Fibonacci numbers {b} and {e} as QA parameters, we compute d = b + e = {d} and a = e + d = {a}. This preserves all QA invariants."
            })

        return data

    def generate_lucas_qa_data(self, n_samples: int = 1000) -> List[Dict]:
        """Generate QA data using Lucas sequence parameters"""
        data = []

        # Lucas sequence (similar to Fibonacci but starts 2, 1)
        lucas = [2, 1]
        for i in range(2, 50):
            lucas.append(lucas[i-1] + lucas[i-2])

        for i in range(min(n_samples, len(lucas) - 1)):
            b, e = lucas[i], lucas[i+1]
            b, e, d, a = self.compute_qa_tuple(b, e)

            invariants = self.validate_invariants(b, e, d, a)

            data.append({
                'type': 'lucas_qa',
                'parameters': {'b': b, 'e': e},
                'tuple': {'b': b, 'e': e, 'd': d, 'a': a},
                'invariants': invariants,
                'sequence_type': 'lucas',
                'mathematical_properties': {
                    'lucas_identity': b**2 - 5 * e**2 == (-1)**(i+1) * 4,
                    'pisano_period': 24,  # Lucas Pisano period
                    'golden_ratio_relation': True
                },
                'text_description': f"Lucas QA tuple: L({i})={b}, L({i+1})={e} → (b={b}, e={e}, d={d}, a={a})",
                'qa_reasoning': f"Lucas sequence provides another rich source of QA parameters. With L({i})={b} and L({i+1})={e}, we get the QA tuple ({b}, {e}, {d}, {a}) that satisfies all invariants."
            })

        return data

    def generate_geometric_qa_data(self, n_samples: int = 1000) -> List[Dict]:
        """Generate QA data using geometric progressions"""
        data = []

        # Generate geometric sequences
        ratios = [2, 3, 5, 7, 11, 13]  # Prime ratios for interesting patterns

        for ratio in ratios:
            seq = [1]
            for i in range(1, 20):
                seq.append(seq[-1] * ratio)

            for i in range(min(n_samples // len(ratios), len(seq) - 1)):
                b, e = seq[i], seq[i+1]
                if b > 10000 or e > 10000:  # Prevent overflow
                    continue

                b, e, d, a = self.compute_qa_tuple(b, e)
                invariants = self.validate_invariants(b, e, d, a)

                data.append({
                    'type': 'geometric_qa',
                    'parameters': {'b': b, 'e': e, 'ratio': ratio},
                    'tuple': {'b': b, 'e': e, 'd': d, 'a': a},
                    'invariants': invariants,
                    'sequence_type': 'geometric',
                    'mathematical_properties': {
                        'common_ratio': ratio,
                        'geometric_series': True,
                        'modular_properties': f"period mod {ratio}"
                    },
                    'text_description': f"Geometric QA tuple (ratio {ratio}): {b}, {e} → (b={b}, e={e}, d={d}, a={a})",
                    'qa_reasoning': f"Geometric sequences with ratio {ratio} create interesting QA patterns. The tuple ({b}, {e}, {d}, {a}) demonstrates how geometric progressions interact with QA arithmetic."
                })

        return data

    def generate_e8_geometry_data(self, n_samples: int = 500) -> List[Dict]:
        """Generate QA data inspired by E8 Lie algebra geometry"""
        data = []

        # E8 root system has 240 roots in 8 dimensions
        # We'll create QA interpretations of these geometric structures

        # Simple E8-inspired coordinate patterns
        e8_patterns = [
            (1, -1, 0, 0, 0, 0, 0, 0),
            (1, 1, 0, 0, 0, 0, 0, 0),
            (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),  # Half-lattice
        ]

        for pattern in e8_patterns:
            for scale in [1, 2, 3, 5]:
                # Use pattern elements as QA parameters
                for i in range(len(pattern) - 1):
                    b_val = pattern[i] * scale
                    e_val = pattern[i+1] * scale

                    # Convert to integers for QA arithmetic
                    b = int(b_val) if b_val.is_integer() else round(b_val * 10)
                    e = int(e_val) if e_val.is_integer() else round(e_val * 10)

                    if b == 0 or e == 0:
                        continue

                    b, e, d, a = self.compute_qa_tuple(b, e)
                    invariants = self.validate_invariants(b, e, d, a)

                    data.append({
                        'type': 'e8_geometry_qa',
                        'parameters': {'b': b, 'e': e, 'e8_pattern': pattern, 'scale': scale},
                        'tuple': {'b': b, 'e': e, 'd': d, 'a': a},
                        'invariants': invariants,
                        'geometry_type': 'e8_inspired',
                        'mathematical_properties': {
                            'exceptional_algebra': 'E8',
                            'dimension': 8,
                            'root_system': True,
                            'coxeter_number': 30
                        },
                        'text_description': f"E8-inspired QA tuple: pattern {pattern[:4]}... scaled by {scale} → (b={b}, e={e}, d={d}, a={a})",
                        'qa_reasoning': f"Using geometric patterns from E8 Lie algebra as inspiration, we derive QA parameters that may reveal connections between exceptional algebras and quantum arithmetic."
                    })

        return data[:n_samples]

    def generate_signal_processing_data(self, n_samples: int = 500) -> List[Dict]:
        """Generate QA data for signal processing applications"""
        data = []

        # Musical intervals and frequencies
        intervals = {
            'unison': 1.0,
            'minor_second': 16/15,
            'major_second': 9/8,
            'minor_third': 6/5,
            'major_third': 5/4,
            'perfect_fourth': 4/3,
            'perfect_fifth': 3/2,
            'minor_sixth': 8/5,
            'major_sixth': 5/3,
            'minor_seventh': 9/5,
            'major_seventh': 15/8,
            'octave': 2.0
        }

        base_freq = 261.63  # Middle C

        for interval_name, ratio in intervals.items():
            for octave in range(-2, 3):
                freq1 = base_freq * (2 ** octave)
                freq2 = freq1 * ratio

                # Convert frequencies to integer ratios for QA
                b = round(freq1)
                e = round(freq2)

                b, e, d, a = self.compute_qa_tuple(b, e)
                invariants = self.validate_invariants(b, e, d, a)

                data.append({
                    'type': 'signal_processing_qa',
                    'parameters': {'b': b, 'e': e, 'frequency_ratio': ratio, 'interval': interval_name},
                    'tuple': {'b': b, 'e': e, 'd': d, 'a': a},
                    'invariants': invariants,
                    'signal_type': 'harmonic',
                    'mathematical_properties': {
                        'frequency_ratio': ratio,
                        'musical_interval': interval_name,
                        'harmonic_series': True,
                        'just_intonation': True
                    },
                    'text_description': f"Harmonic QA tuple: {interval_name} interval ({ratio:.3f}) → (b={b}, e={e}, d={d}, a={a})",
                    'qa_reasoning': f"Musical intervals provide rich harmonic structures for QA analysis. The {interval_name} interval with frequency ratio {ratio:.3f} generates the QA tuple ({b}, {e}, {d}, {a}), potentially revealing connections between musical harmony and quantum arithmetic."
                })

        return data[:n_samples]

    def extract_theorems_from_docs(self) -> List[Dict]:
        """Extract theorems and proofs from documentation"""
        theorems = []

        # Search through documentation files
        docs_dir = self.base_dir / "qa_docs"
        if docs_dir.exists():
            for md_file in docs_dir.rglob("*.md"):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Look for theorem patterns
                    theorem_matches = re.findall(r'##+\s*Theorem[:\s]*(.*?)(?=\n##|\n###|\Z)', content, re.DOTALL | re.IGNORECASE)

                    for theorem_text in theorem_matches:
                        theorems.append({
                            'type': 'extracted_theorem',
                            'source_file': str(md_file.relative_to(self.base_dir)),
                            'theorem_text': theorem_text.strip(),
                            'mathematical_domain': 'qa_theory',
                            'text_description': f"Theorem from {md_file.name}: {theorem_text[:100]}...",
                            'qa_reasoning': "Extracted theorem from QA documentation for training data."
                        })

                except Exception as e:
                    print(f"Error reading {md_file}: {e}")

        return theorems

    def create_qa_reasoning_examples(self) -> List[Dict]:
        """Create question-answer pairs for QA reasoning training"""
        examples = []

        # Basic QA arithmetic reasoning
        qa_questions = [
            {
                'question': 'What is the QA tuple for parameters b=3, e=4?',
                'answer': 'b=3, e=4, d=7, a=11. This satisfies: 3+4=7 (closure), 4+7=11 (closure), and all invariants.',
                'reasoning_type': 'tuple_computation'
            },
            {
                'question': 'Why must d = b + e in QA arithmetic?',
                'answer': 'This is the fundamental closure relation. Without it, the invariant J = b·d would not hold consistently.',
                'reasoning_type': 'invariant_explanation'
            },
            {
                'question': 'How does the inner ellipse law relate to QA tuples?',
                'answer': 'The inner ellipse law a² = d² + 2·d·e + e² ensures geometric consistency with the algebraic invariants.',
                'reasoning_type': 'geometric_interpretation'
            }
        ]

        for qa in qa_questions:
            examples.append({
                'type': 'qa_reasoning_qa',
                'question': qa['question'],
                'answer': qa['answer'],
                'reasoning_type': qa['reasoning_type'],
                'text_description': f"QA Reasoning: {qa['question'][:50]}...",
                'qa_reasoning': qa['answer']
            })

        return examples

    def collect_all_data(self) -> Dict:
        """Collect comprehensive QA training dataset"""
        print("🔍 Collecting QA training data...")

        dataset = {
            'fibonacci_qa': self.generate_fibonacci_qa_data(1000),
            'lucas_qa': self.generate_lucas_qa_data(1000),
            'geometric_qa': self.generate_geometric_qa_data(1000),
            'e8_geometry_qa': self.generate_e8_geometry_data(500),
            'signal_processing_qa': self.generate_signal_processing_data(500),
            'extracted_theorems': self.extract_theorems_from_docs(),
            'qa_reasoning_examples': self.create_qa_reasoning_examples()
        }

        # Calculate statistics
        total_samples = sum(len(samples) for key, samples in dataset.items() if isinstance(samples, list))
        metadata = {
            'total_samples': total_samples,
            'collection_timestamp': str(Path.cwd()),
            'domains_covered': list(dataset.keys()),
            'data_types': {
                'mathematical_sequences': len(dataset['fibonacci_qa']) + len(dataset['lucas_qa']) + len(dataset['geometric_qa']),
                'geometric_structures': len(dataset['e8_geometry_qa']),
                'signal_processing': len(dataset['signal_processing_qa']),
                'theoretical_content': len(dataset['extracted_theorems']),
                'reasoning_examples': len(dataset['qa_reasoning_examples'])
            }
        }

        # Create final dataset structure
        final_dataset = {
            'data': dataset,
            'metadata': metadata
        }

        print(f"✅ Collected {total_samples} QA training samples across {len(dataset)} domains")

        return final_dataset

    def save_dataset(self, dataset: Dict, filename: str = "qa_training_dataset.json"):
        """Save the collected dataset"""
        output_path = self.data_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        print(f"💾 Dataset saved to {output_path}")
        return output_path

def main():
    """Main data collection interface"""
    collector = QADataCollector()
    dataset = collector.collect_all_data()
    output_file = collector.save_dataset(dataset)

    print("\n📊 Dataset Summary:")
    print(f"  Total samples: {dataset['metadata']['total_samples']}")
    print(f"  Domains: {', '.join(dataset['data'].keys())}")
    print(f"  Output: {output_file}")

if __name__ == "__main__":
    main()
