"""
Phase 1 Validation: E8 Re-Ranking on ARC

Tests if E8 alignment can correctly rank ARC solutions.

Methodology:
1. Load ARC tasks
2. For each task, create synthetic candidates:
   - Candidate 0: Correct solution (ground truth)
   - Candidates 1-9: Wrong solutions (perturbations)
3. Rank by E8 alignment
4. Measure: How often does E8 rank correct solution as #1?

Expected: >60% ranking accuracy (vs 10% random baseline)

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict
import sys

# Add qa_lab to path
sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')

from arc_e8_reranker import ARCE8Reranker


def load_arc_tasks(data_dir: str = '/home/player2/signal_experiments/ARC-AGI/data/training',
                   n_tasks: int = 50) -> List[Dict]:
    """
    Load ARC tasks from JSON files.

    Args:
        data_dir: Path to ARC data directory
        n_tasks: Number of tasks to load (for quick testing)

    Returns:
        List of task dictionaries
    """
    data_path = Path(data_dir)
    task_files = sorted(list(data_path.glob('*.json')))[:n_tasks]

    tasks = []
    for task_file in task_files:
        with open(task_file) as f:
            task_data = json.load(f)
            task_data['name'] = task_file.stem
            tasks.append(task_data)

    return tasks


def generate_synthetic_candidates(correct_solution: np.ndarray,
                                   n_candidates: int = 10) -> List[np.ndarray]:
    """
    Generate synthetic candidates: correct + perturbations.

    Args:
        correct_solution: Ground truth output
        n_candidates: Total number of candidates (including correct)

    Returns:
        List of candidate grids (first one is correct)
    """
    candidates = [correct_solution.copy()]  # Index 0 = correct

    height, width = correct_solution.shape

    for i in range(1, n_candidates):
        # Create wrong solutions via different perturbation strategies
        wrong = correct_solution.copy()

        perturbation_type = i % 5

        if perturbation_type == 0:
            # Random noise: flip 10-20% of cells
            mask = np.random.random((height, width)) < 0.15
            wrong[mask] = np.random.randint(0, 10, size=mask.sum())

        elif perturbation_type == 1:
            # Color swap: swap two colors
            colors = np.unique(wrong)
            if len(colors) >= 2:
                c1, c2 = np.random.choice(colors, 2, replace=False)
                mask1 = wrong == c1
                mask2 = wrong == c2
                wrong[mask1] = c2
                wrong[mask2] = c1

        elif perturbation_type == 2:
            # Shift: circular shift by 1-3 pixels
            shift_y = np.random.randint(-2, 3)
            shift_x = np.random.randint(-2, 3)
            wrong = np.roll(wrong, shift=(shift_y, shift_x), axis=(0, 1))

        elif perturbation_type == 3:
            # Invert: replace all non-zero with random colors
            non_zero_mask = wrong != 0
            wrong[non_zero_mask] = np.random.randint(1, 10, size=non_zero_mask.sum())

        else:  # perturbation_type == 4
            # Partial corruption: corrupt a region
            y_start = np.random.randint(0, max(1, height - 3))
            x_start = np.random.randint(0, max(1, width - 3))
            y_end = min(height, y_start + 3)
            x_end = min(width, x_start + 3)
            wrong[y_start:y_end, x_start:x_end] = np.random.randint(0, 10,
                                                                      size=(y_end - y_start, x_end - x_start))

        candidates.append(wrong)

    return candidates


def evaluate_task(task: Dict,
                  reranker: ARCE8Reranker,
                  n_candidates: int = 10) -> Dict:
    """
    Evaluate E8 re-ranking on a single ARC task.

    Args:
        task: ARC task dictionary
        reranker: ARCE8Reranker instance
        n_candidates: Number of synthetic candidates to generate

    Returns:
        Evaluation results
    """
    # Get ground truth from first test example
    test_example = task['test'][0]
    correct_solution = np.array(test_example['output'], dtype=np.int32)

    # Generate synthetic candidates (index 0 = correct)
    candidates = generate_synthetic_candidates(correct_solution, n_candidates)

    # Re-rank by E8
    result = reranker.rerank_solutions(candidates)

    # Check if correct solution ranked #1
    e8_top1_idx = result['best_e8_idx']
    correct_ranked_first = (e8_top1_idx == 0)

    # Find rank of correct solution
    e8_rankings = result['e8_rankings']
    correct_rank = np.where(e8_rankings == 0)[0][0] + 1  # 1-indexed

    return {
        'task_name': task['name'],
        'correct_ranked_first': correct_ranked_first,
        'correct_rank': int(correct_rank),
        'correct_e8_score': float(result['e8_scores'][0]),
        'best_e8_score': float(result['e8_scores'][e8_top1_idx]),
        'n_candidates': n_candidates,
        'grid_shape': correct_solution.shape
    }


def run_validation(n_tasks: int = 50,
                   n_candidates: int = 10,
                   encoding_mode: str = 'patch') -> Dict:
    """
    Run Phase 1 validation on ARC tasks.

    Args:
        n_tasks: Number of tasks to evaluate
        n_candidates: Synthetic candidates per task
        encoding_mode: QA encoding strategy

    Returns:
        Validation results
    """
    print("=" * 70)
    print("Phase 1 Validation: E8 Re-Ranking on ARC")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Tasks: {n_tasks}")
    print(f"  Candidates per task: {n_candidates}")
    print(f"  Encoding mode: {encoding_mode}")
    print(f"  Baseline (random): {100/n_candidates:.1f}% accuracy")
    print()

    # Load tasks
    print("Loading ARC tasks...")
    tasks = load_arc_tasks(n_tasks=n_tasks)
    print(f"  Loaded {len(tasks)} tasks")

    # Create reranker
    reranker = ARCE8Reranker(encoding_mode=encoding_mode, modulus=24)

    # Evaluate each task
    print("\nEvaluating...")
    results = []
    n_correct_top1 = 0
    total_rank = 0

    for i, task in enumerate(tasks):
        try:
            result = evaluate_task(task, reranker, n_candidates)
            results.append(result)

            if result['correct_ranked_first']:
                n_correct_top1 += 1

            total_rank += result['correct_rank']

            # Progress
            if (i + 1) % 10 == 0:
                current_acc = 100 * n_correct_top1 / (i + 1)
                avg_rank = total_rank / (i + 1)
                print(f"  {i+1}/{n_tasks}: Accuracy={current_acc:.1f}%, Avg Rank={avg_rank:.2f}")

        except Exception as e:
            print(f"  Error on task {task['name']}: {e}")
            continue

    # Final results
    n_evaluated = len(results)
    accuracy = 100 * n_correct_top1 / n_evaluated if n_evaluated > 0 else 0
    avg_rank = total_rank / n_evaluated if n_evaluated > 0 else 0
    baseline_accuracy = 100 / n_candidates

    print("\n" + "=" * 70)
    print("Results:")
    print("=" * 70)
    print(f"  Tasks evaluated: {n_evaluated}/{n_tasks}")
    print(f"  Correct ranked #1: {n_correct_top1}")
    print(f"  Accuracy: {accuracy:.2f}%")
    print(f"  Average rank of correct: {avg_rank:.2f}")
    print(f"  Baseline (random): {baseline_accuracy:.2f}%")
    print(f"  Improvement: {accuracy - baseline_accuracy:+.2f}%")
    print()

    if accuracy > baseline_accuracy * 1.5:
        print("✅ SUCCESS: E8 significantly outperforms random baseline!")
    elif accuracy > baseline_accuracy:
        print("✓ POSITIVE: E8 beats random baseline")
    else:
        print("⚠️  NEUTRAL: E8 similar to random baseline")

    print("=" * 70)

    return {
        'n_tasks': n_evaluated,
        'n_correct_top1': n_correct_top1,
        'accuracy': accuracy,
        'avg_rank': avg_rank,
        'baseline_accuracy': baseline_accuracy,
        'improvement': accuracy - baseline_accuracy,
        'results': results
    }


if __name__ == "__main__":
    # Run validation
    validation_results = run_validation(
        n_tasks=50,  # Start with 50 tasks (quick test)
        n_candidates=10,
        encoding_mode='patch'  # Fast mode
    )

    # Save results
    output_file = '/home/player2/signal_experiments/qa_lab/e8_arc_validation_phase1_results.json'
    with open(output_file, 'w') as f:
        json.dump(validation_results, f, indent=2)

    print(f"\nResults saved to: {output_file}")
