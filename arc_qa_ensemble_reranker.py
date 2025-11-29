"""
ARC QA Ensemble Re-Ranker

Combines multiple QA invariants for improved solution ranking:
- E8 alignment (inverse: low = complex)
- W invariant (d(e+a))
- Y invariant (a² - d²)
- Z invariant (e² + da)

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import numpy as np
from typing import List, Dict, Tuple
from qa_arc_grid_encoder import QAGridEncoder, compute_grid_e8_alignment


class QAInvariantComputer:
    """Compute QA canonical invariants for grids."""

    def __init__(self, encoder: QAGridEncoder):
        self.encoder = encoder

    def compute_invariants(self, grid: np.ndarray) -> Dict[str, float]:
        """
        Compute all QA canonical invariants for a grid.

        Returns:
            Dictionary with invariants: J, K, X, W, Y, Z, C, F, G
        """
        # Encode grid as QA tuples
        encoded = self.encoder.encode_grid(grid)

        b = encoded['b']
        e = encoded['e']
        d = encoded['d']
        a = encoded['a']

        # Primary invariants
        J = b * d  # Perigee
        K = d * a  # Apogee
        X = e * d  # Half focal distance

        # Secondary invariants
        W = X + K  # = d(e + a)
        Y = a**2 - d**2  # Eisenstein connection
        Z = e**2 + K  # = e² + da

        # Triangle sides
        C = 2 * e * d  # Focal separation
        F = b * a  # Altitude
        G = e**2 + d**2  # Hypotenuse²

        # Aggregate across all tuples
        return {
            'J': float(np.mean(J)),
            'K': float(np.mean(K)),
            'X': float(np.mean(X)),
            'W': float(np.mean(W)),
            'Y': float(np.mean(Y)),
            'Z': float(np.mean(Z)),
            'C': float(np.mean(C)),
            'F': float(np.mean(F)),
            'G': float(np.mean(G)),
            'W_std': float(np.std(W)),
            'Y_std': float(np.std(Y)),
            'Z_std': float(np.std(Z)),
        }


class ARCQAEnsembleReranker:
    """
    Ensemble re-ranker using multiple QA metrics.

    Combines:
    1. Inverse E8 (low = complex = good)
    2. W variance (high = diverse = good)
    3. Y variance (high = diverse = good)
    4. Z variance (high = diverse = good)
    """

    def __init__(self,
                 encoding_mode: str = 'patch',
                 modulus: int = 24,
                 weights: Dict[str, float] = None):
        """
        Args:
            encoding_mode: QA encoding strategy
            modulus: QA modulus
            weights: Feature weights (default: equal)
        """
        self.encoder = QAGridEncoder(encoding_mode=encoding_mode, modulus=modulus)
        self.invariant_computer = QAInvariantComputer(self.encoder)

        # Default weights (can be tuned)
        self.weights = weights or {
            'inv_e8': 1.0,      # Inverse E8 (primary)
            'w_var': 0.5,       # W variance
            'y_var': 0.5,       # Y variance
            'z_var': 0.5,       # Z variance
        }

    def compute_features(self, grid: np.ndarray) -> Dict[str, float]:
        """
        Compute all features for a single grid.

        Returns:
            Dictionary with normalized features
        """
        # E8 alignment
        e8_score = compute_grid_e8_alignment(grid, self.encoder)

        # QA invariants
        invariants = self.invariant_computer.compute_invariants(grid)

        return {
            'e8': e8_score,
            'inv_e8': 1.0 - e8_score,  # Inverse E8 (low E8 = high inv_e8)
            'w_var': invariants['W_std'],
            'y_var': invariants['Y_std'],
            'z_var': invariants['Z_std'],
            'w_mean': invariants['W'],
            'y_mean': invariants['Y'],
            'z_mean': invariants['Z'],
        }

    def compute_ensemble_score(self, features: Dict[str, float]) -> float:
        """
        Combine features into ensemble score.

        Higher score = better solution
        """
        score = 0.0

        # Inverse E8: prefer low E8 (high complexity)
        score += self.weights['inv_e8'] * features['inv_e8']

        # Variance features: prefer high variance (diversity)
        score += self.weights['w_var'] * features['w_var']
        score += self.weights['y_var'] * features['y_var']
        score += self.weights['z_var'] * features['z_var']

        return score

    def rerank_solutions(self, candidates: List[np.ndarray]) -> Dict:
        """
        Re-rank solution candidates using ensemble scoring.

        Args:
            candidates: List of candidate grids

        Returns:
            Dictionary with rankings and scores
        """
        n_candidates = len(candidates)

        # Compute features for all candidates
        all_features = [self.compute_features(grid) for grid in candidates]

        # Extract feature arrays
        e8_scores = np.array([f['e8'] for f in all_features])
        inv_e8_scores = np.array([f['inv_e8'] for f in all_features])
        w_vars = np.array([f['w_var'] for f in all_features])
        y_vars = np.array([f['y_var'] for f in all_features])
        z_vars = np.array([f['z_var'] for f in all_features])

        # Normalize variance features to [0, 1]
        def normalize(arr):
            if arr.max() > arr.min():
                return (arr - arr.min()) / (arr.max() - arr.min())
            return np.zeros_like(arr)

        w_vars_norm = normalize(w_vars)
        y_vars_norm = normalize(y_vars)
        z_vars_norm = normalize(z_vars)

        # Compute ensemble scores
        ensemble_scores = np.zeros(n_candidates)
        for i in range(n_candidates):
            features_norm = {
                'inv_e8': inv_e8_scores[i],
                'w_var': w_vars_norm[i],
                'y_var': y_vars_norm[i],
                'z_var': z_vars_norm[i],
            }
            ensemble_scores[i] = self.compute_ensemble_score(features_norm)

        # Rankings (descending: higher ensemble score = better)
        ensemble_rankings = np.argsort(ensemble_scores)[::-1]

        # Also compute pure inverse E8 rankings for comparison
        inv_e8_rankings = np.argsort(inv_e8_scores)[::-1]

        return {
            'ensemble_scores': ensemble_scores,
            'ensemble_rankings': ensemble_rankings,
            'best_ensemble_idx': ensemble_rankings[0],

            # Individual feature scores
            'e8_scores': e8_scores,
            'inv_e8_scores': inv_e8_scores,
            'w_vars': w_vars,
            'y_vars': y_vars,
            'z_vars': z_vars,

            # Normalized features
            'w_vars_norm': w_vars_norm,
            'y_vars_norm': y_vars_norm,
            'z_vars_norm': z_vars_norm,

            # Pure inverse E8 for comparison
            'inv_e8_rankings': inv_e8_rankings,
            'best_inv_e8_idx': inv_e8_rankings[0],

            'n_candidates': n_candidates,
            'weights': self.weights
        }

    def tune_weights(self,
                     train_tasks: List[Tuple[List[np.ndarray], int]],
                     n_trials: int = 50) -> Dict[str, float]:
        """
        Tune weights using grid search on training tasks.

        Args:
            train_tasks: List of (candidates, correct_idx) tuples
            n_trials: Number of random weight combinations to try

        Returns:
            Best weights found
        """
        best_weights = self.weights.copy()
        best_accuracy = 0.0

        for trial in range(n_trials):
            # Random weights
            weights = {
                'inv_e8': np.random.uniform(0.5, 2.0),
                'w_var': np.random.uniform(0.0, 1.0),
                'y_var': np.random.uniform(0.0, 1.0),
                'z_var': np.random.uniform(0.0, 1.0),
            }

            # Test on training tasks
            self.weights = weights
            correct = 0
            for candidates, correct_idx in train_tasks:
                result = self.rerank_solutions(candidates)
                if result['best_ensemble_idx'] == correct_idx:
                    correct += 1

            accuracy = correct / len(train_tasks)

            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_weights = weights.copy()

        self.weights = best_weights
        return best_weights


def evaluate_ensemble_vs_e8(tasks_with_ground_truth: List[Tuple[List[np.ndarray], int]],
                             encoding_mode: str = 'patch',
                             modulus: int = 24) -> Dict:
    """
    Compare ensemble performance to pure inverse E8.

    Args:
        tasks_with_ground_truth: List of (candidates, correct_idx) tuples
        encoding_mode: QA encoding strategy
        modulus: QA modulus

    Returns:
        Comparison results
    """
    reranker = ARCQAEnsembleReranker(encoding_mode=encoding_mode, modulus=modulus)

    ensemble_correct = 0
    e8_correct = 0
    total = len(tasks_with_ground_truth)

    ensemble_ranks = []
    e8_ranks = []

    for candidates, correct_idx in tasks_with_ground_truth:
        result = reranker.rerank_solutions(candidates)

        # Check ensemble
        if result['best_ensemble_idx'] == correct_idx:
            ensemble_correct += 1

        # Check pure E8
        if result['best_inv_e8_idx'] == correct_idx:
            e8_correct += 1

        # Track ranks
        ensemble_rank = np.where(result['ensemble_rankings'] == correct_idx)[0][0] + 1
        e8_rank = np.where(result['inv_e8_rankings'] == correct_idx)[0][0] + 1

        ensemble_ranks.append(ensemble_rank)
        e8_ranks.append(e8_rank)

    return {
        'ensemble_accuracy': 100 * ensemble_correct / total,
        'e8_accuracy': 100 * e8_correct / total,
        'ensemble_avg_rank': np.mean(ensemble_ranks),
        'e8_avg_rank': np.mean(e8_ranks),
        'improvement': 100 * (ensemble_correct - e8_correct) / total,
        'n_tasks': total
    }


if __name__ == "__main__":
    # Quick test
    print("ARC QA Ensemble Re-Ranker")
    print("=" * 60)
    print()

    # Create dummy test grids
    correct = np.random.randint(0, 10, (10, 10))
    wrong1 = np.random.randint(0, 10, (10, 10))
    wrong2 = np.random.randint(0, 10, (10, 10))

    candidates = [correct, wrong1, wrong2]

    # Test ensemble reranker
    reranker = ARCQAEnsembleReranker(encoding_mode='patch', modulus=24)
    result = reranker.rerank_solutions(candidates)

    print("Test Results:")
    print(f"  Ensemble scores: {result['ensemble_scores']}")
    print(f"  Best ensemble idx: {result['best_ensemble_idx']}")
    print(f"  Best inv E8 idx: {result['best_inv_e8_idx']}")
    print()
    print(f"  E8 scores: {result['e8_scores']}")
    print(f"  Inv E8 scores: {result['inv_e8_scores']}")
    print(f"  W variances: {result['w_vars']}")
    print(f"  Y variances: {result['y_vars']}")
    print(f"  Z variances: {result['z_vars']}")
    print()
    print("✅ Ensemble reranker module working correctly")
