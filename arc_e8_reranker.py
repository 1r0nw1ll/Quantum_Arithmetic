"""
ARC E8 Re-Ranker

Re-ranks ARC solution candidates by E8 alignment score.
This is a quick-win experiment to validate QA on the ARC benchmark.

Expected improvement: 2-5% over baseline (54.5% → 56-59%)

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import numpy as np
from typing import List, Dict, Tuple
from qa_arc_grid_encoder import QAGridEncoder, compute_grid_e8_alignment


class ARCE8Reranker:
    """
    Re-rank ARC solution candidates using E8 alignment as quality metric.

    Hypothesis: High E8 alignment → Harmonically coherent patterns → Correct solutions
    """

    def __init__(self,
                 encoding_mode: str = 'position',
                 modulus: int = 24,
                 aggregation: str = 'mean',
                 inverse: bool = False):
        """
        Args:
            encoding_mode: How to encode grids ('position', 'color', 'patch')
            modulus: QA modulus (24 primary, 9 auxiliary)
            aggregation: How to aggregate E8 scores ('mean', 'median', 'max', 'min')
            inverse: If True, prefer LOW E8 (complexity detection)
                     If False, prefer HIGH E8 (harmony detection)
        """
        self.encoder = QAGridEncoder(encoding_mode=encoding_mode, modulus=modulus)
        self.aggregation = aggregation
        self.inverse = inverse

    def score_solution(self, solution_grid: np.ndarray) -> float:
        """
        Compute E8 alignment score for a single solution.

        Args:
            solution_grid: (H, W) grid with color values

        Returns:
            E8 score [0, 1], higher is better
        """
        return compute_grid_e8_alignment(solution_grid, self.encoder)

    def rerank_solutions(self,
                         candidates: List[np.ndarray],
                         baseline_scores: np.ndarray = None) -> Dict:
        """
        Re-rank solution candidates by E8 alignment.

        Args:
            candidates: List of candidate solution grids
            baseline_scores: Optional baseline model scores (e.g., ViT logits)

        Returns:
            Dictionary with:
                'e8_scores': E8 alignment for each candidate
                'e8_rankings': Indices sorted by E8 (best first)
                'baseline_rankings': Original rankings (if provided)
                'best_e8_idx': Index of best E8 solution
                'best_baseline_idx': Index of best baseline solution (if provided)
                'rank_agreement': Whether E8 and baseline agree on top-1
        """
        n_candidates = len(candidates)

        # Compute E8 scores
        e8_scores = np.array([self.score_solution(grid) for grid in candidates])

        # E8 ranking
        if self.inverse:
            # Inverse mode: prefer LOW E8 (complexity detection)
            e8_rankings = np.argsort(e8_scores)  # Ascending
        else:
            # Forward mode: prefer HIGH E8 (harmony detection)
            e8_rankings = np.argsort(e8_scores)[::-1]  # Descending

        result = {
            'e8_scores': e8_scores,
            'e8_rankings': e8_rankings,
            'best_e8_idx': e8_rankings[0],
            'n_candidates': n_candidates
        }

        # Compare with baseline if provided
        if baseline_scores is not None:
            baseline_rankings = np.argsort(baseline_scores)[::-1]
            result['baseline_scores'] = baseline_scores
            result['baseline_rankings'] = baseline_rankings
            result['best_baseline_idx'] = baseline_rankings[0]
            result['rank_agreement'] = (e8_rankings[0] == baseline_rankings[0])

        return result

    def hybrid_score(self,
                     candidates: List[np.ndarray],
                     baseline_scores: np.ndarray,
                     alpha: float = 0.5) -> Dict:
        """
        Hybrid scoring: Combine baseline and E8 scores.

        Score = alpha * baseline + (1-alpha) * E8

        Args:
            candidates: List of candidate grids
            baseline_scores: Baseline model scores (normalized [0,1])
            alpha: Weight for baseline (0=pure E8, 1=pure baseline)

        Returns:
            Dictionary with hybrid rankings
        """
        # Compute E8 scores
        e8_scores = np.array([self.score_solution(grid) for grid in candidates])

        # Normalize both to [0, 1]
        e8_norm = (e8_scores - e8_scores.min()) / (e8_scores.max() - e8_scores.min() + 1e-8)
        baseline_norm = (baseline_scores - baseline_scores.min()) / (baseline_scores.max() - baseline_scores.min() + 1e-8)

        # Hybrid score
        hybrid_scores = alpha * baseline_norm + (1 - alpha) * e8_norm
        hybrid_rankings = np.argsort(hybrid_scores)[::-1]

        return {
            'e8_scores': e8_scores,
            'baseline_scores': baseline_scores,
            'hybrid_scores': hybrid_scores,
            'e8_rankings': np.argsort(e8_scores)[::-1],
            'baseline_rankings': np.argsort(baseline_scores)[::-1],
            'hybrid_rankings': hybrid_rankings,
            'best_hybrid_idx': hybrid_rankings[0],
            'alpha': alpha
        }


def evaluate_reranking_on_task(task_data: Dict,
                                candidates: List[np.ndarray],
                                ground_truth: np.ndarray,
                                baseline_scores: np.ndarray = None) -> Dict:
    """
    Evaluate E8 re-ranking on a single ARC task.

    Args:
        task_data: Task metadata (name, etc.)
        candidates: List of N candidate solutions
        ground_truth: Correct solution
        baseline_scores: Optional baseline model scores

    Returns:
        Evaluation results with accuracy metrics
    """
    reranker = ARCE8Reranker(encoding_mode='position', modulus=24)

    # Re-rank candidates
    result = reranker.rerank_solutions(candidates, baseline_scores)

    # Check correctness
    def grid_matches(pred, target):
        """Check if prediction matches ground truth."""
        if pred.shape != target.shape:
            return False
        return np.all(pred == target)

    # E8-based accuracy
    e8_top1 = candidates[result['best_e8_idx']]
    e8_correct = grid_matches(e8_top1, ground_truth)

    eval_result = {
        'task_name': task_data.get('name', 'unknown'),
        'n_candidates': len(candidates),
        'e8_top1_correct': e8_correct,
        'e8_best_score': result['e8_scores'][result['best_e8_idx']],
        'e8_rankings': result['e8_rankings'].tolist(),
        'e8_scores': result['e8_scores'].tolist()
    }

    # Baseline comparison
    if baseline_scores is not None:
        baseline_top1 = candidates[result['best_baseline_idx']]
        baseline_correct = grid_matches(baseline_top1, ground_truth)

        eval_result.update({
            'baseline_top1_correct': baseline_correct,
            'rank_agreement': result['rank_agreement'],
            'improvement': e8_correct and not baseline_correct  # E8 fixes baseline error
        })

    return eval_result


def demo_reranking():
    """
    Demonstration of E8 re-ranking with synthetic examples.
    """
    print("=" * 60)
    print("ARC E8 Re-Ranker - Demonstration")
    print("=" * 60)

    # Create synthetic candidate solutions
    # Candidate 1: Chaotic/random (low E8 expected)
    np.random.seed(42)
    candidate_1 = np.random.randint(0, 10, size=(10, 10))

    # Candidate 2: Structured pattern (higher E8 expected)
    candidate_2 = np.zeros((10, 10), dtype=np.int32)
    candidate_2[2:8, 2:8] = 1
    candidate_2[4:6, 4:6] = 2

    # Candidate 3: Fibonacci-like progression (highest E8 expected)
    candidate_3 = np.zeros((10, 10), dtype=np.int32)
    fib = [1, 1, 2, 3, 5, 8]
    for i, val in enumerate(fib):
        if i < 6:
            candidate_3[i, :i+1] = val

    # Candidate 4: Symmetric (high E8 expected)
    candidate_4 = np.zeros((10, 10), dtype=np.int32)
    candidate_4[3:7, 3:7] = 1
    candidate_4[4:6, 4:6] = 3

    candidates = [candidate_1, candidate_2, candidate_3, candidate_4]

    # Synthetic baseline scores (suppose model prefers candidate 1)
    baseline_scores = np.array([0.9, 0.6, 0.4, 0.5])

    # Re-rank using E8
    reranker = ARCE8Reranker(encoding_mode='position', modulus=24)
    result = reranker.rerank_solutions(candidates, baseline_scores)

    print("\nCandidate E8 Scores:")
    for i, score in enumerate(result['e8_scores']):
        print(f"  Candidate {i+1}: E8 = {score:.6f}")

    print("\nBaseline Rankings (by model confidence):")
    print(f"  {result['baseline_rankings'] + 1}")  # +1 for 1-indexed

    print("\nE8 Re-Rankings:")
    print(f"  {result['e8_rankings'] + 1}")  # +1 for 1-indexed

    print(f"\nBaseline chooses: Candidate {result['best_baseline_idx'] + 1}")
    print(f"E8 chooses: Candidate {result['best_e8_idx'] + 1}")
    print(f"Rankings agree: {result['rank_agreement']}")

    # Hybrid scoring
    print("\n" + "-" * 60)
    print("Hybrid Scoring (alpha=0.3: 30% baseline, 70% E8)")
    hybrid_result = reranker.hybrid_score(candidates, baseline_scores, alpha=0.3)
    print(f"  Hybrid chooses: Candidate {hybrid_result['best_hybrid_idx'] + 1}")
    print(f"  Hybrid rankings: {hybrid_result['hybrid_rankings'] + 1}")

    print("\n" + "=" * 60)
    print("✅ E8 Re-Ranker ready for ARC validation")
    print("\nExpected workflow:")
    print("  1. Generate N candidates from ViT")
    print("  2. Compute E8 alignment for each")
    print("  3. Re-rank by E8 score")
    print("  4. Select top-K for final prediction")
    print("  5. Evaluate on ARC validation set")
    print("\nExpected improvement: 2-5% (54.5% → 56-59%)")
    print("=" * 60)


if __name__ == "__main__":
    demo_reranking()
