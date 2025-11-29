"""
Evaluation Set Validation: Inverse E8 on ARC Evaluation Set

Tests optimized inverse E8 on 400 held-out evaluation tasks.

This confirms generalization to unseen data.

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict
import sys
from datetime import datetime

# Add qa_lab to path
sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')

from arc_e8_reranker import ARCE8Reranker


def load_arc_tasks(data_dir: str = '/home/player2/signal_experiments/ARC-AGI/data/evaluation',
                   max_tasks: int = None) -> List[Dict]:
    """Load ARC evaluation tasks."""
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
    """Generate synthetic candidates: correct + perturbations."""
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
                  reranker: ARCE8Reranker,
                  n_candidates: int = 10) -> Dict:
    """Evaluate inverse E8 on a single task."""
    test_example = task['test'][0]
    correct_solution = np.array(test_example['output'], dtype=np.int32)

    candidates = generate_synthetic_candidates(correct_solution, n_candidates)
    result = reranker.rerank_solutions(candidates)

    best_idx = result['best_e8_idx']
    correct_ranked_first = (best_idx == 0)

    e8_rankings = result['e8_rankings']
    correct_position_in_ranking = np.where(e8_rankings == 0)[0][0]
    correct_rank = correct_position_in_ranking + 1

    return {
        'task_name': task['name'],
        'correct_ranked_first': bool(correct_ranked_first),
        'correct_rank': int(correct_rank),
        'correct_e8_score': float(result['e8_scores'][0]),
        'n_candidates': n_candidates,
        'grid_shape': correct_solution.shape,
        'e8_scores': [float(s) for s in result['e8_scores']]
    }


def run_evaluation_validation():
    """Run validation on ARC evaluation set."""
    print("=" * 80)
    print("INVERSE E8 - EVALUATION SET VALIDATION")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Dataset: ARC Evaluation (held-out)")
    print(f"  Encoding: patch (5×5)")
    print(f"  Modulus: 24")
    print(f"  Mode: INVERSE (Low E8 = Good)")
    print(f"  Candidates per task: 10")
    print(f"  Baseline (random): 10.0%")
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load tasks
    print("Loading ARC evaluation tasks...")
    tasks = load_arc_tasks()
    n_total = len(tasks)
    print(f"  Loaded {n_total} evaluation tasks")

    # Create reranker with optimal settings
    reranker = ARCE8Reranker(
        encoding_mode='patch',
        modulus=24,
        inverse=True
    )

    # Evaluate
    print(f"\nEvaluating {n_total} tasks...")
    print("-" * 80)

    results = []
    n_correct_top1 = 0
    total_rank = 0

    correct_e8_scores = []
    wrong_e8_scores = []

    for i, task in enumerate(tasks):
        try:
            result = evaluate_task(task, reranker, n_candidates=10)
            results.append(result)

            if result['correct_ranked_first']:
                n_correct_top1 += 1

            total_rank += result['correct_rank']

            correct_e8_scores.append(result['correct_e8_score'])
            wrong_e8_scores.extend([s for j, s in enumerate(result['e8_scores']) if j != 0])

            if (i + 1) % 50 == 0 or (i + 1) == n_total:
                current_acc = 100 * n_correct_top1 / (i + 1)
                avg_rank = total_rank / (i + 1)
                print(f"  {i+1:3d}/{n_total}: Accuracy={current_acc:5.1f}%, Avg Rank={avg_rank:.2f}")

        except Exception as e:
            print(f"  ERROR on task {task['name']}: {e}")
            continue

    # Results
    n_evaluated = len(results)
    accuracy = 100 * n_correct_top1 / n_evaluated if n_evaluated > 0 else 0
    avg_rank = total_rank / n_evaluated if n_evaluated > 0 else 0
    baseline_accuracy = 10.0
    improvement = accuracy - baseline_accuracy
    performance_ratio = accuracy / baseline_accuracy if baseline_accuracy > 0 else 0

    correct_e8_mean = np.mean(correct_e8_scores)
    correct_e8_std = np.std(correct_e8_scores)
    wrong_e8_mean = np.mean(wrong_e8_scores)
    wrong_e8_std = np.std(wrong_e8_scores)

    print("\n" + "=" * 80)
    print("EVALUATION SET RESULTS")
    print("=" * 80)
    print(f"\nTasks evaluated: {n_evaluated}/{n_total}")
    print(f"Correct ranked #1: {n_correct_top1}")
    print(f"Accuracy: {accuracy:.1f}% ({n_correct_top1}/{n_evaluated} correct)")
    print(f"Average rank: {avg_rank:.2f}/10")
    print(f"Baseline (random): {baseline_accuracy:.1f}%")
    print(f"Improvement: {improvement:+.1f}%")
    print(f"Performance ratio: {performance_ratio:.1f}x better than random")
    print()

    print("E8 Score Statistics:")
    print(f"  Correct solutions:  {correct_e8_mean:.6f} ± {correct_e8_std:.6f}")
    print(f"  Wrong solutions:    {wrong_e8_mean:.6f} ± {wrong_e8_std:.6f}")
    print(f"  Discrimination gap: {wrong_e8_mean - correct_e8_mean:.6f}")
    print()

    # Compare to training set
    print("=" * 80)
    print("COMPARISON: Training vs Evaluation")
    print("=" * 80)
    print(f"Training set (400 tasks):   86.5% accuracy")
    print(f"Evaluation set ({n_evaluated} tasks): {accuracy:.1f}% accuracy")
    diff = accuracy - 86.5
    print(f"Difference: {diff:+.1f}%")
    print()

    if abs(diff) <= 2.0:
        print("✅ EXCELLENT: Evaluation matches training (generalization confirmed)")
    elif abs(diff) <= 5.0:
        print("✓ GOOD: Evaluation close to training (acceptable generalization)")
    else:
        print("⚠️  WARNING: Significant difference (potential overfitting or dataset shift)")

    print("=" * 80)

    return {
        'timestamp': datetime.now().isoformat(),
        'dataset': 'evaluation',
        'configuration': {
            'encoding_mode': 'patch',
            'modulus': 24,
            'inverse': True,
            'n_candidates': 10
        },
        'summary': {
            'n_tasks': n_evaluated,
            'n_correct_top1': n_correct_top1,
            'accuracy': accuracy,
            'avg_rank': avg_rank,
            'baseline_accuracy': baseline_accuracy,
            'improvement': improvement,
            'performance_ratio': performance_ratio,
            'training_accuracy': 86.5,
            'difference_from_training': diff
        },
        'e8_statistics': {
            'correct_mean': correct_e8_mean,
            'correct_std': correct_e8_std,
            'wrong_mean': wrong_e8_mean,
            'wrong_std': wrong_e8_std,
            'discrimination_gap': wrong_e8_mean - correct_e8_mean
        },
        'results': results
    }


if __name__ == "__main__":
    np.random.seed(42)

    validation_results = run_evaluation_validation()

    # Save results
    output_file = '/home/player2/signal_experiments/qa_lab/inverse_e8_evaluation_results.json'
    with open(output_file, 'w') as f:
        json.dump(validation_results, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Quick summary report
    summary_file = '/home/player2/signal_experiments/qa_lab/INVERSE_E8_EVALUATION_SUMMARY.md'
    with open(summary_file, 'w') as f:
        f.write("# Inverse E8 - Evaluation Set Summary\n\n")
        f.write(f"**Date**: {validation_results['timestamp']}\n")
        f.write(f"**Status**: ✅ COMPLETE\n\n")
        f.write("---\n\n")
        f.write("## Results\n\n")
        s = validation_results['summary']
        f.write(f"**Evaluation accuracy**: {s['accuracy']:.1f}% ({s['n_correct_top1']}/{s['n_tasks']})\n")
        f.write(f"**Training accuracy**: {s['training_accuracy']:.1f}% (346/400)\n")
        f.write(f"**Difference**: {s['difference_from_training']:+.1f}%\n\n")
        f.write(f"**Average rank**: {s['avg_rank']:.2f}/10\n")
        f.write(f"**Performance ratio**: {s['performance_ratio']:.1f}x better than random\n\n")
        f.write("---\n\n")
        f.write("## Generalization Assessment\n\n")
        if abs(s['difference_from_training']) <= 2.0:
            f.write("✅ **EXCELLENT**: Evaluation matches training within 2%\n\n")
            f.write("**Conclusion**: Inverse E8 generalizes perfectly to held-out data.\n")
        elif abs(s['difference_from_training']) <= 5.0:
            f.write("✓ **GOOD**: Evaluation close to training (within 5%)\n\n")
            f.write("**Conclusion**: Inverse E8 generalizes well to held-out data.\n")
        else:
            f.write("⚠️  **CAUTION**: Significant difference from training\n\n")
            f.write("**Conclusion**: May indicate dataset shift or overfitting.\n")

    print(f"Summary saved to: {summary_file}")
