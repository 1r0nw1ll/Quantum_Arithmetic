"""Test if original inverse E8 reranker still works."""

import numpy as np
import sys
sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')

from arc_e8_reranker import ARCE8Reranker
import json
from pathlib import Path

# Load one task
task_file = Path('/home/player2/signal_experiments/ARC-AGI/data/training').glob('*.json').__next__()
with open(task_file) as f:
    task_data = json.load(f)

correct = np.array(task_data['test'][0]['output'], dtype=np.int32)

# Generate perturbations (same as validation script)
def generate_synthetic_candidates(correct_solution, n_candidates=10):
    candidates = [correct_solution.copy()]
    height, width = correct_solution.shape

    for i in range(1, n_candidates):
        wrong = correct_solution.copy()
        perturbation_type = i % 5

        if perturbation_type == 0:
            mask = np.random.random((height, width)) < 0.15
            wrong[mask] = np.random.randint(0, 10, size=mask.sum())
        elif perturbation_type == 1:
            colors = np.unique(wrong)
            if len(colors) >= 2:
                c1, c2 = np.random.choice(colors, 2, replace=False)
                mask1 = wrong == c1
                mask2 = wrong == c2
                wrong[mask1] = c2
                wrong[mask2] = c1
        elif perturbation_type == 2:
            shift_y = np.random.randint(-2, 3)
            shift_x = np.random.randint(-2, 3)
            wrong = np.roll(wrong, shift=(shift_y, shift_x), axis=(0, 1))
        elif perturbation_type == 3:
            non_zero_mask = wrong != 0
            if non_zero_mask.sum() > 0:
                wrong[non_zero_mask] = np.random.randint(1, 10, size=non_zero_mask.sum())
        else:
            y_start = np.random.randint(0, max(1, height - 3))
            x_start = np.random.randint(0, max(1, width - 3))
            y_end = min(height, y_start + 3)
            x_end = min(width, x_start + 3)
            wrong[y_start:y_end, x_start:x_end] = np.random.randint(0, 10,
                                                                      size=(y_end - y_start, x_end - x_start))

        candidates.append(wrong)

    return candidates

np.random.seed(42)
candidates = generate_synthetic_candidates(correct, 10)

# Test reranker
reranker = ARCE8Reranker(encoding_mode='patch', modulus=24, inverse=True)
result = reranker.rerank_solutions(candidates)

print("=" * 80)
print("ORIGINAL INVERSE E8 RERANKER TEST")
print("=" * 80)
print()

print(f"Task: {task_file.stem}")
print(f"Grid shape: {correct.shape}")
print()

print("E8 Scores:")
for i, score in enumerate(result['e8_scores']):
    label = "CORRECT" if i == 0 else f"wrong-{i}"
    print(f"  [{i}] {label:12s}: {score:.6f}")
print()

print("Rankings (best first):")
print(f"  {result['e8_rankings'][:5]}...")
print()

print(f"Best index: {result['best_e8_idx']} (should be 0)")
print()

if result['best_e8_idx'] == 0:
    print("✅ Original inverse E8 works correctly!")
else:
    print(f"❌ Original inverse E8 ranked {result['best_e8_idx']} instead of 0")
    print()
    print("E8 score analysis:")
    print(f"  Correct E8: {result['e8_scores'][0]:.6f}")
    print(f"  Mean wrong E8: {np.mean(result['e8_scores'][1:]):.6f}")
    print(f"  Min E8: {np.min(result['e8_scores']):.6f}")
    print(f"  Max E8: {np.max(result['e8_scores']):.6f}")
