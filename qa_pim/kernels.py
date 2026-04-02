"""PIM-style vectorized kernels for QA operations.

All kernels operate on NumPy arrays.  No torch dependency.

NOTE on QA Axiom A1 (No-Zero):
  RADD_m and RMUL_m use standard modular arithmetic (range 0..m-1).
  These are PIM-layer primitives operating on *coordinates*, not QA state.
  QA state-level operations (qa_step, qa_mod) enforce A1 at a higher layer.
"""

import numpy as np


def RESIDUE_SELECT(sector_ids: np.ndarray, mask: set) -> np.ndarray:
    """Select vertices whose sector IDs are in the mask."""
    return np.isin(sector_ids, list(mask))


def TORUS_SHIFT(arr: np.ndarray, delta: int, P: int) -> np.ndarray:
    """Shift array values on torus modulo P."""
    return (arr + delta) % P


def RADD_m(a, b, m: int):
    """Residue addition modulo m (coordinate-level, 0-indexed)."""
    return (a + b) % m


def RMUL_m(a, b, m: int):
    """Residue multiplication modulo m (coordinate-level, 0-indexed)."""
    return (a * b) % m


def MIRROR4(arr: np.ndarray) -> np.ndarray:
    """Mirror operation: fold q1/q3 with reversals (length must be divisible by 4)."""
    n = len(arr)
    if n % 4 != 0:
        raise ValueError(f"Array length {n} not divisible by 4")

    q = n // 4
    result = arr.copy()

    q1 = result[q : 2 * q]
    q3_reversed = result[3 * q : 4 * q][::-1]
    result[q : 2 * q] = (q1 + q3_reversed) // 2
    result[3 * q : 4 * q] = (q1 + q3_reversed)[::-1] // 2

    return result


def ROLLING_SUM_PHASE(
    values_by_phase: np.ndarray,
    width: int,
    m: int = None,
) -> np.ndarray:
    """Compute rolling sum over phase ring with given width.

    Wraps circularly (torus topology).
    """
    n = len(values_by_phase)
    if width >= n:
        return np.full(n, values_by_phase.sum())

    kernel = np.ones(width)
    padded = np.concatenate([values_by_phase, values_by_phase[: width - 1]])
    conv_result = np.convolve(padded, kernel, mode="valid")

    if m is not None:
        conv_result = conv_result % m

    return conv_result[:n]
