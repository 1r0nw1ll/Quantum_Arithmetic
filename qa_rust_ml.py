"""
qa_rust_ml.py - Rust-based ML operations (torch-free)

This module provides ML functionality without requiring PyTorch. All operations
run through the Rust backend (qa_lab_rs) which uses pure Rust libraries:
- linfa (scikit-learn equivalent)
- ndarray (NumPy equivalent)
- nalgebra (SciPy linear algebra)

Use this module when you need ML operations but torch is unavailable.
"""

from typing import List, Tuple, Optional
import numpy as np

try:
    import qa_lab_rs
    _RUST_ML_AVAILABLE = True
except ImportError:
    _RUST_ML_AVAILABLE = False


def is_available() -> bool:
    """Check if Rust ML backend is available"""
    return _RUST_ML_AVAILABLE


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors using Rust.

    Args:
        a, b: NumPy arrays or lists of floats

    Returns:
        float: Cosine similarity in [-1, 1]

    Example:
        >>> a = np.array([1.0, 0.0, 0.0])
        >>> b = np.array([1.0, 0.0, 0.0])
        >>> cosine_similarity(a, b)
        1.0
    """
    if not _RUST_ML_AVAILABLE:
        raise RuntimeError("Rust ML backend not available")

    a_list = a.tolist() if isinstance(a, np.ndarray) else list(a)
    b_list = b.tolist() if isinstance(b, np.ndarray) else list(b)

    return qa_lab_rs.cosine_similarity_py(a_list, b_list)


def normalize(arr: np.ndarray) -> np.ndarray:
    """
    Normalize array to [0, 1] range using Rust.

    Args:
        arr: NumPy array or list of floats

    Returns:
        np.ndarray: Normalized array

    Example:
        >>> arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        >>> normalize(arr)
        array([0., 0.25, 0.5, 0.75, 1.])
    """
    if not _RUST_ML_AVAILABLE:
        raise RuntimeError("Rust ML backend not available")

    arr_list = arr.tolist() if isinstance(arr, np.ndarray) else list(arr)
    result = qa_lab_rs.normalize_py(arr_list)

    return np.array(result)


def random_qa_tuple() -> Tuple[float, float, float, float]:
    """
    Generate random QA tuple following closure laws using Rust.

    Returns:
        tuple: (b, e, d, a) where d = b + e and a = e + d

    Example:
        >>> b, e, d, a = random_qa_tuple()
        >>> abs(d - (b + e)) < 0.01
        True
    """
    if not _RUST_ML_AVAILABLE:
        raise RuntimeError("Rust ML backend not available")

    return qa_lab_rs.random_qa_tuple_py()


def extract_qa_patterns(text: str) -> List[Tuple[float, float, float, float]]:
    """
    Extract QA tuples from text using pattern matching (Rust).

    Args:
        text: String containing potential QA tuples

    Returns:
        list: List of valid (b, e, d, a) tuples found in text

    Example:
        >>> text = "The sequence 1.0 2.0 3.0 5.0 is valid"
        >>> extract_qa_patterns(text)
        [(1.0, 2.0, 3.0, 5.0)]
    """
    if not _RUST_ML_AVAILABLE:
        raise RuntimeError("Rust ML backend not available")

    return qa_lab_rs.extract_qa_patterns_py(text)


def compute_bundle(b: float, e: float, d: float, a: float) -> dict:
    """
    Compute full QA bundle (all invariants) using Rust.

    Args:
        b, e, d, a: QA tuple components

    Returns:
        dict: All QA invariants (J, K, X, W, Y, Z, C, F, G)

    Example:
        >>> bundle = compute_bundle(1.0, 2.0, 3.0, 5.0)
        >>> bundle['J']  # perigee
        3.0
    """
    if not _RUST_ML_AVAILABLE:
        raise RuntimeError("Rust ML backend not available")

    return qa_lab_rs.compute_bundle_py(b, e, d, a)


class RustMLHelper:
    """
    Torch-free ML helper using Rust backend.

    This class provides ML operations without requiring PyTorch,
    making it ideal for environments with dependency constraints.
    """

    def __init__(self):
        if not _RUST_ML_AVAILABLE:
            raise RuntimeError("Rust ML backend not available. Build with 'make rust-py-build'")

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between vectors"""
        return cosine_similarity(a, b)

    def normalize_array(self, arr: np.ndarray) -> np.ndarray:
        """Normalize to [0, 1]"""
        return normalize(arr)

    def generate_qa_data(self, n_samples: int) -> List[Tuple[float, float, float, float]]:
        """Generate random QA tuples for training"""
        return [random_qa_tuple() for _ in range(n_samples)]

    def find_qa_in_text(self, text: str) -> List[Tuple[float, float, float, float]]:
        """Extract QA patterns from text"""
        return extract_qa_patterns(text)

    def batch_compute_invariants(
        self, tuples: List[Tuple[float, float, float, float]]
    ) -> List[dict]:
        """Compute invariants for multiple QA tuples"""
        results = []
        for b, e, d, a in tuples:
            bundle = compute_bundle(b, e, d, a)
            results.append(bundle)
        return results


# Fallback implementations using NumPy (if Rust not available)
def _numpy_cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Fallback cosine similarity using NumPy"""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot / (norm_a * norm_b))


def _numpy_normalize(arr: np.ndarray) -> np.ndarray:
    """Fallback normalize using NumPy"""
    min_val = np.min(arr)
    max_val = np.max(arr)

    if abs(max_val - min_val) < 1e-10:
        return np.zeros_like(arr)

    return (arr - min_val) / (max_val - min_val)


# Auto-fallback wrappers
if not _RUST_ML_AVAILABLE:
    def cosine_similarity(a, b):
        """Fallback to NumPy"""
        a_arr = np.array(a) if not isinstance(a, np.ndarray) else a
        b_arr = np.array(b) if not isinstance(b, np.ndarray) else b
        return _numpy_cosine_similarity(a_arr, b_arr)

    def normalize(arr):
        """Fallback to NumPy"""
        arr_np = np.array(arr) if not isinstance(arr, np.ndarray) else arr
        return _numpy_normalize(arr_np)


if __name__ == "__main__":
    print("Testing Rust ML module...")
    print(f"Rust ML available: {is_available()}")

    if is_available():
        # Test all functions
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        print(f"Cosine similarity: {cosine_similarity(a, b)}")

        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        print(f"Normalized: {normalize(arr)}")

        b, e, d, a = random_qa_tuple()
        print(f"Random QA tuple: ({b:.2f}, {e:.2f}, {d:.2f}, {a:.2f})")

        text = "Sample 1.0 2.0 3.0 5.0 data"
        patterns = extract_qa_patterns(text)
        print(f"Extracted patterns: {patterns}")

        helper = RustMLHelper()
        data = helper.generate_qa_data(5)
        print(f"Generated {len(data)} QA tuples")
    else:
        print("Rust ML not available - using NumPy fallback")
