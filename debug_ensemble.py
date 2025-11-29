"""Debug ensemble reranker."""

import numpy as np
import sys
sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')

from arc_qa_ensemble_reranker import ARCQAEnsembleReranker
import json
from pathlib import Path

# Load one task
task_file = Path('/home/player2/signal_experiments/ARC-AGI/data/training').glob('*.json').__next__()
with open(task_file) as f:
    task_data = json.load(f)

correct = np.array(task_data['test'][0]['output'], dtype=np.int32)

# Generate perturbations
def perturb(grid):
    wrong = grid.copy()
    mask = np.random.random(grid.shape) < 0.15
    wrong[mask] = np.random.randint(0, 10, size=mask.sum())
    return wrong

candidates = [correct] + [perturb(correct) for _ in range(9)]

# Test reranker
reranker = ARCQAEnsembleReranker(encoding_mode='patch', modulus=24)
result = reranker.rerank_solutions(candidates)

print("=" * 80)
print("ENSEMBLE DEBUG")
print("=" * 80)
print()

print("Feature Analysis:")
print(f"  E8 scores: {result['e8_scores']}")
print(f"  Inv E8 scores: {result['inv_e8_scores']}")
print(f"  W vars: {result['w_vars']}")
print(f"  Y vars: {result['y_vars']}")
print(f"  Z vars: {result['z_vars']}")
print()

print("Normalized features:")
print(f"  W vars norm: {result['w_vars_norm']}")
print(f"  Y vars norm: {result['y_vars_norm']}")
print(f"  Z vars norm: {result['z_vars_norm']}")
print()

print("Ensemble scores:")
print(f"  Scores: {result['ensemble_scores']}")
print(f"  Best idx: {result['best_ensemble_idx']} (should be 0)")
print()

print("Rankings:")
print(f"  Ensemble rankings: {result['ensemble_rankings'][:3]}...")
print(f"  E8 rankings: {result['inv_e8_rankings'][:3]}...")
print()

print("Weights:")
print(f"  {result['weights']}")
print()

# Check if correct is ranked first
if result['best_ensemble_idx'] == 0:
    print("✅ Ensemble correctly ranked!")
else:
    print(f"❌ Ensemble ranked {result['best_ensemble_idx']} instead of 0")

if result['best_inv_e8_idx'] == 0:
    print("✅ Inverse E8 correctly ranked!")
else:
    print(f"❌ Inverse E8 ranked {result['best_inv_e8_idx']} instead of 0")
