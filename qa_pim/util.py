"""Utilities for timing, RNG, and statistics."""

import time
import numpy as np
from typing import List


class _Timer:
    """Simple timing context manager."""

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start


def timing_context():
    """Return a timing context manager."""
    return _Timer()


def percentile_stats(durations: List[float]) -> dict:
    """Calculate P50 and P99 statistics from duration list."""
    if not durations:
        return {"p50": 0.0, "p99": 0.0, "mean": 0.0}
    arr = np.array(durations)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p99": float(np.percentile(arr, 99)),
        "mean": float(np.mean(arr)),
    }


def seed_rng(seed: int = 42) -> np.random.RandomState:
    """Create seeded random number generator."""
    return np.random.RandomState(seed)
