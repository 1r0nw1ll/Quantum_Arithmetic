"""
Validate QA Ensemble Re-Ranker on ARC

Tests if combining E8 with other QA invariants improves accuracy.

Expected: 86.5% (pure E8) → 88-92% (ensemble)

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import sys
from datetime import datetime

sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')

from arc_qa_ensemble_reranker import ARCQAEnsembleReranker


def load_arc_tasks(data_dir: str, max_tasks: int = None) -> List[Dict]:
    """Load ARC tasks."""
    data_path = Path(data_dir)
    task_files = sorted(list(data_path.glob('*.json')))

    if max_tasks:
        task_files = task_files[:max_tasks]

    tasks = []
    for task_file in task_files:
        with open(task_file) as f:
            task_data = json.load(f)
            task_data['name'] = task_file.stem
            tasks.append(task_data)

    return tasks


def generate_synthetic_candidates(correct_solution: np.ndarray,
                                   n_candidates: int = 10) -> List[np.ndarray]:
    """Generate synthetic candidates."""
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


def evaluate_task(task: Dict,
                  reranker: ARCQAEnsembleReranker,
                  n_candidates: int = 10) -> Dict:
    """Evaluate ensemble reranker on a single task."""
    test_example = task['test'][0]
    correct_solution = np.array(test_example['output'], dtype=np.int32)

    candidates = generate_synthetic_candidates(correct_solution, n_candidates)
    result = reranker.rerank_solutions(candidates)

    # Ensemble ranking
    ensemble_best_idx = result['best_ensemble_idx']
    ensemble_correct = (ensemble_best_idx == 0)

    ensemble_rankings = result['ensemble_rankings']
    ensemble_rank = np.where(ensemble_rankings == 0)[0][0] + 1

    # Pure E8 ranking
    e8_best_idx = result['best_inv_e8_idx']
    e8_correct = (e8_best_idx == 0)

    e8_rankings = result['inv_e8_rankings']
    e8_rank = np.where(e8_rankings == 0)[0][0] + 1

    return {
        'task_name': task['name'],
        'ensemble_correct': bool(ensemble_correct),
        'ensemble_rank': int(ensemble_rank),
        'e8_correct': bool(e8_correct),
        'e8_rank': int(e8_rank),
        'improved': ensemble_rank < e8_rank,  # Ensemble better than E8
        'ensemble_score': float(result['ensemble_scores'][0]),
        'e8_score': float(result['e8_scores'][0]),
        'grid_shape': correct_solution.shape
    }


def run_ensemble_validation(dataset: str = 'training',
                             n_tasks: int = None,
                             n_candidates: int = 10) -> Dict:
    """
    Run ensemble validation.

    Args:
        dataset: 'training' or 'evaluation'
        n_tasks: Number of tasks (None = all)
        n_candidates: Candidates per task

    Returns:
        Validation results
    """
    print("=" * 80)
    print(f"ENSEMBLE VALIDATION: ARC {dataset.upper()}")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Dataset: {dataset}")
    print(f"  Encoding: patch (5×5)")
    print(f"  Modulus: 24")
    print(f"  Method: Ensemble (E8 + W/Y/Z variance)")
    print(f"  Candidates per task: {n_candidates}")
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load tasks
    data_dir = f'/home/player2/signal_experiments/ARC-AGI/data/{dataset}'
    print(f"Loading tasks from {dataset} set...")
    tasks = load_arc_tasks(data_dir, max_tasks=n_tasks)
    n_total = len(tasks)
    print(f"  Loaded {n_total} tasks")

    # Create ensemble reranker
    reranker = ARCQAEnsembleReranker(
        encoding_mode='patch',
        modulus=24
    )

    # Evaluate
    print(f"\nEvaluating {n_total} tasks...")
    print("-" * 80)

    results = []
    ensemble_correct = 0
    e8_correct = 0
    total_ensemble_rank = 0
    total_e8_rank = 0
    n_improved = 0

    for i, task in enumerate(tasks):
        try:
            result = evaluate_task(task, reranker, n_candidates)
            results.append(result)

            if result['ensemble_correct']:
                ensemble_correct += 1

            if result['e8_correct']:
                e8_correct += 1

            if result['improved']:
                n_improved += 1

            total_ensemble_rank += result['ensemble_rank']
            total_e8_rank += result['e8_rank']

            if (i + 1) % 50 == 0 or (i + 1) == n_total:
                ens_acc = 100 * ensemble_correct / (i + 1)
                e8_acc = 100 * e8_correct / (i + 1)
                print(f"  {i+1:3d}/{n_total}: Ensemble={ens_acc:5.1f}%, E8={e8_acc:5.1f}%, Improved={n_improved}")

        except Exception as e:
            print(f"  ERROR on task {task['name']}: {e}")
            continue

    # Final results
    n_evaluated = len(results)
    ensemble_accuracy = 100 * ensemble_correct / n_evaluated
    e8_accuracy = 100 * e8_correct / n_evaluated
    avg_ensemble_rank = total_ensemble_rank / n_evaluated
    avg_e8_rank = total_e8_rank / n_evaluated
    improvement = ensemble_accuracy - e8_accuracy

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"\nTasks evaluated: {n_evaluated}")
    print()
    print("Ensemble Method:")
    print(f"  Accuracy: {ensemble_accuracy:.1f}% ({ensemble_correct}/{n_evaluated})")
    print(f"  Average rank: {avg_ensemble_rank:.2f}/10")
    print()
    print("Pure Inverse E8:")
    print(f"  Accuracy: {e8_accuracy:.1f}% ({e8_correct}/{n_evaluated})")
    print(f"  Average rank: {avg_e8_rank:.2f}/10")
    print()
    print("Comparison:")
    print(f"  Improvement: {improvement:+.1f}%")
    print(f"  Tasks improved: {n_improved}/{n_evaluated} ({100*n_improved/n_evaluated:.1f}%)")
    print()

    if improvement >= 2.0:
        print("✅ EXCELLENT: Ensemble significantly improves over E8!")
    elif improvement >= 0.5:
        print("✓ POSITIVE: Ensemble modestly improves over E8")
    elif improvement >= -0.5:
        print("≈ NEUTRAL: Ensemble similar to E8")
    else:
        print("⚠️  NEGATIVE: E8 alone is better")

    print("=" * 80)

    return {
        'timestamp': datetime.now().isoformat(),
        'dataset': dataset,
        'configuration': {
            'encoding_mode': 'patch',
            'modulus': 24,
            'n_candidates': n_candidates
        },
        'summary': {
            'n_tasks': n_evaluated,
            'ensemble_correct': ensemble_correct,
            'ensemble_accuracy': ensemble_accuracy,
            'ensemble_avg_rank': avg_ensemble_rank,
            'e8_correct': e8_correct,
            'e8_accuracy': e8_accuracy,
            'e8_avg_rank': avg_e8_rank,
            'improvement': improvement,
            'n_improved': n_improved,
            'improvement_rate': 100 * n_improved / n_evaluated
        },
        'results': results
    }


if __name__ == "__main__":
    np.random.seed(42)

    # Start with 100 tasks to test quickly
    print("Starting with 100 tasks for quick test...")
    print()

    validation_results = run_ensemble_validation(
        dataset='training',
        n_tasks=100,
        n_candidates=10
    )

    # Save results
    output_file = '/home/player2/signal_experiments/qa_lab/ensemble_validation_100tasks.json'
    with open(output_file, 'w') as f:
        json.dump(validation_results, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Decision point
    improvement = validation_results['summary']['improvement']
    print()
    print("=" * 80)
    print("NEXT STEP RECOMMENDATION")
    print("=" * 80)

    if improvement >= 1.0:
        print(f"\n✅ Ensemble shows {improvement:+.1f}% improvement!")
        print("   Recommended: Run on full 400 tasks to validate")
    elif improvement >= 0.0:
        print(f"\n✓ Ensemble shows modest {improvement:+.1f}% improvement")
        print("   Recommended: Consider weight tuning or try full dataset")
    else:
        print(f"\n⚠️  Ensemble shows {improvement:.1f}% (worse than E8)")
        print("   Recommended: Try weight tuning or different features")
