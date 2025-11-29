"""
QA ARC Grid Encoder

Encodes ARC benchmark grids (30x30) as QA tuples for algebraic analysis.
Maps spatial positions and colors to (b,e,d,a) tuples satisfying QA constraints.

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-20
"""

import numpy as np
import torch
from typing import Tuple, Dict, List, Optional


class QAGridEncoder:
    """
    Encode ARC grids as QA tuple bundles.

    Encoding strategies:
    1. Position-based: (row, col) -> (b,e,d,a) with QA constraints
    2. Color-aware: Incorporate color values
    3. Patch-based: Encode 5x5 patches for efficiency
    """

    def __init__(self,
                 encoding_mode: str = 'position',
                 patch_size: int = 5,
                 modulus: int = 24):
        """
        Args:
            encoding_mode: 'position', 'color', or 'patch'
            patch_size: Size of patches (for patch mode)
            modulus: QA modulus (24 for primary system, 9 for auxiliary)
        """
        self.encoding_mode = encoding_mode
        self.patch_size = patch_size
        self.modulus = modulus

    def encode_grid(self, grid: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Encode a 30x30 ARC grid as QA tuples.

        Args:
            grid: (30, 30) array with integer color values 0-9

        Returns:
            Dictionary with QA tuple components and metadata:
            {
                'b': (N,) array,
                'e': (N,) array,
                'd': (N,) array,
                'a': (N,) array,
                'colors': (N,) array,
                'positions': (N, 2) array (row, col),
                'encoding_mode': str
            }
        """
        if self.encoding_mode == 'position':
            return self._encode_position_based(grid)
        elif self.encoding_mode == 'color':
            return self._encode_color_based(grid)
        elif self.encoding_mode == 'patch':
            return self._encode_patch_based(grid)
        else:
            raise ValueError(f"Unknown encoding mode: {self.encoding_mode}")

    def _encode_position_based(self, grid: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Position-based encoding: (row, col) -> (b, e, d, a)

        Mapping:
            b = row % modulus
            e = col % modulus
            d = (b + e) % modulus  (automatic QA constraint)
            a = (e + d) % modulus  (automatic QA constraint)

        This preserves spatial relationships algebraically.
        """
        height, width = grid.shape

        # Generate all positions
        rows, cols = np.mgrid[0:height, 0:width]
        rows_flat = rows.flatten()
        cols_flat = cols.flatten()
        colors_flat = grid.flatten()

        # Filter out background (color 0) for efficiency
        non_bg_mask = colors_flat != 0
        rows_active = rows_flat[non_bg_mask]
        cols_active = cols_flat[non_bg_mask]
        colors_active = colors_flat[non_bg_mask]

        # Encode as QA tuples
        b = rows_active % self.modulus
        e = cols_active % self.modulus
        d = (b + e) % self.modulus
        a = (e + d) % self.modulus

        return {
            'b': b.astype(np.int32),
            'e': e.astype(np.int32),
            'd': d.astype(np.int32),
            'a': a.astype(np.int32),
            'colors': colors_active.astype(np.int32),
            'positions': np.stack([rows_active, cols_active], axis=1),
            'encoding_mode': 'position',
            'n_tuples': len(b)
        }

    def _encode_color_based(self, grid: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Color-based encoding: (color, row) -> (b, e, d, a)

        Mapping:
            b = color % modulus
            e = row % modulus
            d = (b + e) % modulus
            a = (e + d) % modulus

        Emphasizes color structure over pure spatial position.
        """
        height, width = grid.shape

        rows, cols = np.mgrid[0:height, 0:width]
        rows_flat = rows.flatten()
        cols_flat = cols.flatten()
        colors_flat = grid.flatten()

        # Filter background
        non_bg_mask = colors_flat != 0
        rows_active = rows_flat[non_bg_mask]
        cols_active = cols_flat[non_bg_mask]
        colors_active = colors_flat[non_bg_mask]

        # Encode with color emphasis
        b = colors_active % self.modulus
        e = rows_active % self.modulus
        d = (b + e) % self.modulus
        a = (e + d) % self.modulus

        return {
            'b': b.astype(np.int32),
            'e': e.astype(np.int32),
            'd': d.astype(np.int32),
            'a': a.astype(np.int32),
            'colors': colors_active.astype(np.int32),
            'positions': np.stack([rows_active, cols_active], axis=1),
            'encoding_mode': 'color',
            'n_tuples': len(b)
        }

    def _encode_patch_based(self, grid: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Patch-based encoding: Encode 5x5 patches as single QA tuples.

        More efficient for large grids. Each patch gets one tuple:
            b = avg_row % modulus
            e = avg_col % modulus
            d = (b + e) % modulus
            a = (e + d) % modulus

        Color is dominant color in patch.
        """
        height, width = grid.shape
        ps = self.patch_size

        # Calculate number of patches
        n_patches_h = height // ps
        n_patches_w = width // ps

        b_list, e_list, d_list, a_list = [], [], [], []
        colors_list, positions_list = [], []

        for i in range(n_patches_h):
            for j in range(n_patches_w):
                # Extract patch
                patch = grid[i*ps:(i+1)*ps, j*ps:(j+1)*ps]

                # Skip if all background
                if np.all(patch == 0):
                    continue

                # Center position
                center_row = i * ps + ps // 2
                center_col = j * ps + ps // 2

                # Dominant color (most frequent non-zero)
                non_zero_colors = patch[patch != 0]
                if len(non_zero_colors) > 0:
                    dominant_color = np.bincount(non_zero_colors).argmax()
                else:
                    dominant_color = 0

                # Encode patch center
                b_val = center_row % self.modulus
                e_val = center_col % self.modulus
                d_val = (b_val + e_val) % self.modulus
                a_val = (e_val + d_val) % self.modulus

                b_list.append(b_val)
                e_list.append(e_val)
                d_list.append(d_val)
                a_list.append(a_val)
                colors_list.append(dominant_color)
                positions_list.append([center_row, center_col])

        return {
            'b': np.array(b_list, dtype=np.int32),
            'e': np.array(e_list, dtype=np.int32),
            'd': np.array(d_list, dtype=np.int32),
            'a': np.array(a_list, dtype=np.int32),
            'colors': np.array(colors_list, dtype=np.int32),
            'positions': np.array(positions_list, dtype=np.int32),
            'encoding_mode': 'patch',
            'n_tuples': len(b_list)
        }

    def decode_to_grid(self, qa_bundle: Dict[str, np.ndarray],
                       grid_shape: Tuple[int, int] = (30, 30)) -> np.ndarray:
        """
        Decode QA tuples back to a grid (best effort reconstruction).

        Args:
            qa_bundle: Dictionary with QA components
            grid_shape: Target grid shape

        Returns:
            Reconstructed grid
        """
        grid = np.zeros(grid_shape, dtype=np.int32)

        positions = qa_bundle['positions']
        colors = qa_bundle['colors']

        for pos, color in zip(positions, colors):
            row, col = pos
            if 0 <= row < grid_shape[0] and 0 <= col < grid_shape[1]:
                grid[row, col] = color

        return grid


def compute_grid_e8_alignment(grid: np.ndarray,
                               encoder: Optional[QAGridEncoder] = None) -> float:
    """
    Compute average E8 alignment for an entire ARC grid.

    Args:
        grid: (30, 30) ARC grid
        encoder: QAGridEncoder instance (creates default if None)

    Returns:
        Average E8 alignment score [0, 1]
    """
    if encoder is None:
        encoder = QAGridEncoder(encoding_mode='position', modulus=24)

    # Encode grid as QA tuples
    qa_bundle = encoder.encode_grid(grid)

    # Import E8 alignment function
    from qa_e8_alignment import e8_alignment_batch_numpy

    # Compute E8 alignment for all tuples
    e8_scores = e8_alignment_batch_numpy(
        qa_bundle['b'],
        qa_bundle['e'],
        qa_bundle['d'],
        qa_bundle['a']
    )

    # Return average (or could use median, max, etc.)
    if len(e8_scores) == 0:
        return 0.0

    return float(np.mean(e8_scores))


def batch_compute_e8_alignment(grids: List[np.ndarray],
                                encoder: Optional[QAGridEncoder] = None) -> np.ndarray:
    """
    Compute E8 alignment for a batch of grids.

    Args:
        grids: List of (30, 30) ARC grids
        encoder: QAGridEncoder instance

    Returns:
        Array of E8 scores, one per grid
    """
    if encoder is None:
        encoder = QAGridEncoder(encoding_mode='position', modulus=24)

    scores = []
    for grid in grids:
        score = compute_grid_e8_alignment(grid, encoder)
        scores.append(score)

    return np.array(scores)


# Example usage
if __name__ == "__main__":
    print("QA ARC Grid Encoder - Test")
    print("=" * 50)

    # Create a simple test grid (10x10 for demonstration)
    test_grid = np.array([
        [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 2, 2, 0],
        [0, 0, 0, 0, 0, 0, 0, 2, 2, 0],
        [0, 3, 3, 3, 0, 0, 0, 0, 0, 0],
        [0, 3, 0, 3, 0, 0, 0, 0, 0, 0],
        [0, 3, 3, 3, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ], dtype=np.int32)

    # Test position-based encoding
    encoder = QAGridEncoder(encoding_mode='position', modulus=24)
    qa_bundle = encoder.encode_grid(test_grid)

    print(f"\nPosition-Based Encoding:")
    print(f"  N tuples: {qa_bundle['n_tuples']}")
    print(f"  First 5 tuples:")
    for i in range(min(5, qa_bundle['n_tuples'])):
        print(f"    ({qa_bundle['b'][i]}, {qa_bundle['e'][i]}, "
              f"{qa_bundle['d'][i]}, {qa_bundle['a'][i]}) "
              f"color={qa_bundle['colors'][i]} "
              f"pos={qa_bundle['positions'][i]}")

    # Test E8 alignment
    e8_score = compute_grid_e8_alignment(test_grid, encoder)
    print(f"\n  Average E8 Alignment: {e8_score:.6f}")

    # Test reconstruction
    reconstructed = encoder.decode_to_grid(qa_bundle, grid_shape=(10, 10))
    match_ratio = np.mean(reconstructed == test_grid)
    print(f"  Reconstruction accuracy: {match_ratio*100:.1f}%")

    print("\n" + "=" * 50)
    print("✅ QA ARC Grid Encoder ready for use")
