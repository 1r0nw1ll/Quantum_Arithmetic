"""QA coordinate mapping and data generation.

Maps (key, time) pairs to quantum coordinates (sector, ring, phase)
using modular arithmetic.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple


@dataclass
class QAParams:
    """Quantum Arithmetic parameters."""
    m: int = 24               # sectors (mod-24)
    RING_QUANTUM: int = 1000  # ring quantization
    P: int = 1024             # phase modulus
    HASH_MULT: int = 11400714819323198485  # phase hash multiplier


def schema_map(
    keys: np.ndarray,
    times: np.ndarray,
    params: QAParams,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map (key, time) pairs to QA coordinates (sector, ring, phase)."""
    sectors = keys % params.m
    rings = times // params.RING_QUANTUM

    # Phase hash: ((key * HASH_MULT) ^ (time >> 12)) % P
    phase_hash = (
        (keys.astype(np.uint64) * params.HASH_MULT)
        ^ (times.astype(np.uint64) >> 12)
    )
    phases = phase_hash % params.P

    return (
        sectors.astype(np.int32),
        rings.astype(np.int32),
        phases.astype(np.int32),
    )


def generate_graph_data(
    N: int = 100000,
    E: int = 500000,
    seed: int = 42,
    params: QAParams = None,
) -> dict:
    """Generate random graph data with QA coordinates."""
    if params is None:
        params = QAParams()

    rng = np.random.RandomState(seed)

    keys = rng.randint(0, 2**20, size=N, dtype=np.int32)
    times = rng.randint(0, 10000000, size=N, dtype=np.int32)
    values = rng.randint(-1000, 1000, size=N, dtype=np.int64)

    sectors, rings, phases = schema_map(keys, times, params)

    edges = rng.randint(0, N, size=(E, 2), dtype=np.int32)

    return {
        "N": N,
        "E": E,
        "keys": keys,
        "times": times,
        "values": values,
        "sectors": sectors,
        "rings": rings,
        "phases": phases,
        "edges": edges,
        "params": params,
    }
