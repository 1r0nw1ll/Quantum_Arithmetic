"""QA Observer Core primitives.

These functions are the shared computational atoms of the topographic
observer pipeline.  They enforce QA axiom A1 (no-zero) at the state level.

Canonical source: 46_seismic_topographic_observer.py lines 34-45,
replicated in scripts 47-49 and finance scripts 30-33.
"""

from __future__ import annotations

QA_COMPLIANCE = "observer=core_library, state_alphabet=generic_topographic"

import numpy as np

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


# ---------------------------------------------------------------------------
# A1-compliant modular reduction
# ---------------------------------------------------------------------------

def qa_mod(x: int, m: int) -> int:
    """QA-compliant modular reduction: output in {1, ..., m}, never 0.

    Implements axiom A1 (No-Zero): states live in {1,...,N}.
    Formula: ((x - 1) % m) + 1
    """
    return ((int(x) - 1) % m) + 1


# ---------------------------------------------------------------------------
# T-operator coherence index (QCI)
# ---------------------------------------------------------------------------

def compute_qci(
    labels: np.ndarray | list,
    cmap: dict,
    m: int,
    window: int,
    default_state: int = 5,
):
    """Compute rolling QCI (T-operator coherence index).

    For each triple (t, t+1, t+2), predicts label[t+2] from
    qa_mod(cmap[label[t]] + cmap[label[t+1]], m) and checks match.
    Returns a rolling-mean Series (pandas) or ndarray of match fractions.

    Parameters
    ----------
    labels : array-like of cluster labels (integer)
    cmap : dict mapping cluster label -> QA state (int in {1..m})
    m : modulus (typically 24)
    window : rolling window size
    default_state : fallback QA state for unmapped labels
    """
    labels = np.asarray(labels)
    t_match = []
    for t in range(len(labels) - 2):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        actual = cmap.get(int(labels[t + 2]), default_state)
        pred = qa_mod(b + e, m)
        t_match.append(1 if pred == actual else 0)

    if _HAS_PANDAS:
        return pd.Series(t_match).rolling(window, min_periods=window // 2).mean()
    else:
        # Pure numpy fallback
        arr = np.array(t_match, dtype=float)
        out = np.full(len(arr), np.nan)
        min_p = window // 2
        for i in range(len(arr)):
            start = max(0, i - window + 1)
            chunk = arr[start : i + 1]
            if len(chunk) >= min_p:
                out[i] = np.mean(chunk)
        return out


# ---------------------------------------------------------------------------
# Orbit classification
# ---------------------------------------------------------------------------

# Standard orbit names for mod-24 QA
COSMOS_PERIOD = 24
SATELLITE_PERIOD = 8
SINGULARITY_PERIOD = 1


def classify_orbit(period: int) -> str:
    """Classify a QA orbit by its period length.

    Returns one of: 'cosmos' (24-cycle), 'satellite' (8-cycle),
    'singularity' (1-cycle/fixed point).
    """
    if period == SINGULARITY_PERIOD:
        return "singularity"
    elif period == SATELLITE_PERIOD:
        return "satellite"
    elif period == COSMOS_PERIOD:
        return "cosmos"
    else:
        return f"orbit_{period}"
