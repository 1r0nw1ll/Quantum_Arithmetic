"""
Analyze Failure Cases from Inverse E8 Full Validation

Examines the 54/400 tasks where inverse E8 failed to rank correctly.

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


def load_validation_results() -> Dict:
    """Load full validation results."""
    results_file = '/home/player2/signal_experiments/qa_lab/inverse_e8_full_validation_results.json'
    with open(results_file) as f:
        return json.load(f)


def load_arc_task(task_name: str) -> Dict:
    """Load a specific ARC task by name."""
    task_file = f'/home/player2/signal_experiments/ARC-AGI/data/training/{task_name}.json'
    with open(task_file) as f:
        task_data = json.load(f)
        task_data['name'] = task_name
        return task_data


def analyze_failures():
    """Analyze patterns in failure cases."""
    print("=" * 80)
    print("INVERSE E8 FAILURE ANALYSIS")
    print("=" * 80)
    print()

    # Load results
    validation_results = load_validation_results()
    all_results = validation_results['results']

    # Separate successes and failures
    successes = [r for r in all_results if r['correct_ranked_first']]
    failures = [r for r in all_results if not r['correct_ranked_first']]

    print(f"Total tasks: {len(all_results)}")
    print(f"Successes: {len(successes)} ({100*len(successes)/len(all_results):.1f}%)")
    print(f"Failures: {len(failures)} ({100*len(failures)/len(all_results):.1f}%)")
    print()

    # E8 score analysis
    success_e8 = [r['correct_e8_score'] for r in successes]
    failure_e8 = [r['correct_e8_score'] for r in failures]

    print("=" * 80)
    print("E8 SCORE COMPARISON")
    print("=" * 80)
    print(f"Success cases (n={len(successes)}):")
    print(f"  Mean E8: {np.mean(success_e8):.6f}")
    print(f"  Std E8:  {np.std(success_e8):.6f}")
    print(f"  Median:  {np.median(success_e8):.6f}")
    print(f"  Range:   [{np.min(success_e8):.6f}, {np.max(success_e8):.6f}]")
    print()
    print(f"Failure cases (n={len(failures)}):")
    print(f"  Mean E8: {np.mean(failure_e8):.6f}")
    print(f"  Std E8:  {np.std(failure_e8):.6f}")
    print(f"  Median:  {np.median(failure_e8):.6f}")
    print(f"  Range:   [{np.min(failure_e8):.6f}, {np.max(failure_e8):.6f}]")
    print()

    # Statistical significance
    from scipy import stats
    t_stat, p_value = stats.ttest_ind(success_e8, failure_e8)
    print(f"T-test: t={t_stat:.3f}, p={p_value:.6f}")
    if p_value < 0.05:
        print("✅ Statistically significant difference (p < 0.05)")
    else:
        print("⚠️  Not statistically significant (p >= 0.05)")
    print()

    # Rank analysis
    print("=" * 80)
    print("RANK DISTRIBUTION IN FAILURES")
    print("=" * 80)
    failure_ranks = [r['correct_rank'] for r in failures]
    print(f"Average rank in failures: {np.mean(failure_ranks):.2f}")
    print(f"Rank distribution:")
    for rank in range(1, 11):
        count = sum(1 for r in failure_ranks if r == rank)
        if count > 0:
            print(f"  Rank {rank}: {count} tasks ({100*count/len(failures):.1f}%)")
    print()

    # Grid size analysis
    print("=" * 80)
    print("GRID SIZE ANALYSIS")
    print("=" * 80)

    def grid_area(shape_tuple):
        return shape_tuple[0] * shape_tuple[1]

    success_areas = [grid_area(r['grid_shape']) for r in successes]
    failure_areas = [grid_area(r['grid_shape']) for r in failures]

    print(f"Success cases:")
    print(f"  Mean area: {np.mean(success_areas):.1f} cells")
    print(f"  Median area: {np.median(success_areas):.1f} cells")
    print()
    print(f"Failure cases:")
    print(f"  Mean area: {np.mean(failure_areas):.1f} cells")
    print(f"  Median area: {np.median(failure_areas):.1f} cells")
    print()

    # Show specific failure examples
    print("=" * 80)
    print("TOP 10 WORST FAILURES (by rank)")
    print("=" * 80)
    failures_sorted = sorted(failures, key=lambda x: x['correct_rank'], reverse=True)

    for i, failure in enumerate(failures_sorted[:10]):
        print(f"\n{i+1}. Task: {failure['task_name']}")
        print(f"   Correct rank: {failure['correct_rank']}/10")
        print(f"   Correct E8: {failure['correct_e8_score']:.6f}")
        print(f"   Grid size: {failure['grid_shape']}")

        # Show E8 score distribution
        if 'e8_scores' in failure:
            e8_scores = failure['e8_scores']
            correct_e8 = e8_scores[0]
            other_e8 = e8_scores[1:]
            print(f"   E8 range: [{min(e8_scores):.6f}, {max(e8_scores):.6f}]")
            print(f"   Correct vs mean(wrong): {correct_e8:.6f} vs {np.mean(other_e8):.6f}")

            # Check if correct is actually HIGHER than wrong (opposite of expected)
            if correct_e8 > np.mean(other_e8):
                print(f"   ⚠️  ANOMALY: Correct E8 is HIGHER than wrong (expected inverse)")

    print("\n" + "=" * 80)
    print("FAILURE PATTERN SUMMARY")
    print("=" * 80)

    # Count how many failures have correct E8 > mean(wrong E8)
    anomalies = 0
    for failure in failures:
        if 'e8_scores' in failure:
            correct_e8 = failure['e8_scores'][0]
            other_e8 = failure['e8_scores'][1:]
            if correct_e8 > np.mean(other_e8):
                anomalies += 1

    print(f"\nFailures where correct E8 > mean(wrong E8): {anomalies}/{len(failures)}")
    print(f"This represents {100*anomalies/len(failures):.1f}% of failures")
    print()
    print("**Interpretation**: These are cases where correct solution is MORE regular")
    print("                    than wrong solutions (opposite of typical pattern).")
    print()

    return {
        'n_successes': len(successes),
        'n_failures': len(failures),
        'success_e8_mean': np.mean(success_e8),
        'success_e8_std': np.std(success_e8),
        'failure_e8_mean': np.mean(failure_e8),
        'failure_e8_std': np.std(failure_e8),
        't_statistic': t_stat,
        'p_value': p_value,
        'anomaly_count': anomalies
    }


if __name__ == "__main__":
    analysis_results = analyze_failures()

    # Save analysis
    output_file = '/home/player2/signal_experiments/qa_lab/inverse_e8_failure_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)

    print(f"Analysis saved to: {output_file}")
