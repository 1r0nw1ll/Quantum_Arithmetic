#!/usr/bin/env python3
"""
qa_svp_validation_harness.py

General-purpose QA ↔ SVP cross-domain validation harness.

Takes any time-series signal and runs the full pipeline:
  Signal → Standardize → Cluster → QA States → QCI → Orbits → Toroidal Flow → JSON

The output is a structured result ready for SVP harmonic analysis comparison.
D.A.N. / Lady J can run SVP classification on the same signal and compare.

Usage:
  # With built-in demo signals:
  python qa_svp_validation_harness.py

  # As a library:
  from qa_svp_validation_harness import QASVPHarness, HarnessConfig
  harness = QASVPHarness(HarnessConfig(modulus=24, n_clusters=6))
  result = harness.run(signal_array, name="my_signal")

Pipeline stages:
  1. Standardize: rolling z-score (window configurable)
  2. Cluster: K-means on standardized signal → discrete labels
  3. QA project: cluster labels → QA states via cmap (evenly spaced in {1,...,m})
  4. QCI: T-operator coherence index (rolling match fraction)
  5. Orbit analysis: classify each (state[t], state[t+1]) pair into orbit family
  6. Toroidal flow: map orbit-level torus dynamics to SVP flow types
  7. Package: structured JSON with all metrics + SVP comparison scaffold
"""

from __future__ import annotations

import json
import math
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

QA_COMPLIANCE = "observer=svp_validation_harness, state_alphabet=generic_topographic"

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

try:
    from sklearn.cluster import KMeans
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

np.random.seed(42)


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HarnessConfig:
    """Pipeline configuration.  All QA hyperparameters in one place."""
    modulus: int = 24                  # QA modulus (9 theoretical, 24 applied)
    n_clusters: int = 6                # K-means clusters
    qci_window: int = 63              # Rolling QCI window
    standardize_window: int = 63      # Rolling z-score window
    seed: int = 42                    # RNG seed for reproducibility
    train_fraction: float = 0.5       # Train/test split for clustering
    cmap: Optional[Dict[int, int]] = None  # Custom cluster→QA state map
    sample_rate: float = 1.0          # Samples per second (for reporting)
    default_state: int = 5            # Fallback QA state for unmapped labels

    def build_cmap(self) -> Dict[int, int]:
        """Construct evenly-spaced cluster→QA state mapping if none provided."""
        if self.cmap is not None:
            return self.cmap
        # Evenly space K states across {1,...,m}
        m = self.modulus
        k = self.n_clusters
        step = max(1, m // k)
        return {i: min(((i + 1) * step), m) for i in range(k)}


# ═══════════════════════════════════════════════════════════════════════════
# QA Arithmetic (A1-compliant, S1-compliant: b*b not b**2)
# ═══════════════════════════════════════════════════════════════════════════

def qa_mod(x: int, m: int) -> int:
    """A1-compliant modular reduction: output in {1,...,m}, never 0."""
    return ((int(x) - 1) % m) + 1


def qa_step(b: int, e: int, m: int) -> Tuple[int, int]:
    """Q: (b, e) -> (e, ((b+e-1)%m)+1).  A1-compliant."""
    return e, ((b + e - 1) % m) + 1


def qa_tuple_full(b: int, e: int, m: int) -> Tuple[int, int, int, int]:
    """Full 4-tuple (b, e, d, a).  d, a derived per A2."""
    d = ((b + e - 1) % m) + 1
    a = ((b + 2 * e - 1) % m) + 1
    return b, e, d, a


def orbit_length(b: int, e: int, m: int) -> int:
    """Cycle length of (b, e) under Q mod m."""
    cur = (qa_mod(b, m), qa_mod(e, m))
    start = cur
    length = 0
    while True:
        cur = qa_step(cur[0], cur[1], m)
        length += 1
        if cur == start:
            return length


_max_orbit_cache: Dict[int, int] = {}

def max_orbit_len(m: int) -> int:
    """Largest orbit length for modulus m (cached)."""
    if m not in _max_orbit_cache:
        best = 1
        for b in range(1, m + 1):
            for e in range(1, m + 1):
                ol = orbit_length(b, e, m)
                if ol > best:
                    best = ol
        _max_orbit_cache[m] = best
    return _max_orbit_cache[m]


def classify_orbit_family(b: int, e: int, m: int) -> str:
    """Classify (b, e) into orbit family."""
    ol = orbit_length(b, e, m)
    if ol == 1:
        return "singularity"
    if ol == max_orbit_len(m):
        return "cosmos"
    return "satellite"


# ═══════════════════════════════════════════════════════════════════════════
# Toroidal Geometry (from qa_svp_toroidal_flow_experiment.py)
# ═══════════════════════════════════════════════════════════════════════════

def torus_params_from_tuple(b: int, e: int, m: int) -> Dict[str, float]:
    """Compute toroidal parameters for a QA state.  S1-compliant."""
    _, _, d, a = qa_tuple_full(b, e, m)
    C = 2.0 * e * d
    F = float(b * a)
    G = (b * b + a * a) / 2.0
    R = G
    r = F
    aspect = R / r if r != 0 else float("inf")
    k = C / F if F != 0 else float("inf")
    C24 = int(round(C)) % 24
    F24 = int(round(F)) % 24
    m0 = C24 or 24
    n0 = F24 or 24
    g = math.gcd(m0, n0)
    m_knot, n_knot = m0 // g, n0 // g
    degenerate = (C == 0 and F == 0 and G == 0)
    return {
        "C": C, "F": F, "G": G,
        "R": R, "r": r, "aspect": aspect, "k": k,
        "m_knot": m_knot, "n_knot": n_knot,
        "degenerate": degenerate,
    }


def orbit_torus_flow_score(b: int, e: int, m: int) -> Tuple[float, str]:
    """Compute orbit-level torus diversity → SVP flow score and classification.

    Walks the full orbit, collects torus params at each step, computes
    flow_score = torus_diversity × log(unique_knots + 1).
    Returns (flow_score, svp_flow_type).
    """
    cur = (qa_mod(b, m), qa_mod(e, m))
    start = cur
    R_vals = []
    knots = set()
    n_degen = 0
    states = []

    while True:
        states.append(cur)
        tp = torus_params_from_tuple(cur[0], cur[1], m)
        R_vals.append(tp["R"])
        knots.add((tp["m_knot"], tp["n_knot"]))
        if tp["degenerate"]:
            n_degen += 1
        cur = qa_step(cur[0], cur[1], m)
        if cur == start:
            break

    ol = len(states)
    if ol == 1 or n_degen == ol:
        return -1.0, "inward"

    R_arr = np.array(R_vals)
    R_mean = float(np.mean(R_arr))
    torus_div = float(np.std(R_arr) / R_mean) if R_mean > 0 else 0.0
    flow_score = torus_div * math.log(len(knots) + 1)

    # Use modulus-appropriate threshold (from experiment results)
    # mod 9: threshold ~1.0, mod 24: threshold ~0.84
    # Default: 0.9 works well across both
    threshold = 0.9
    svp_flow = "outward" if flow_score > threshold else "equilibrium"

    return flow_score, svp_flow


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Stages
# ═══════════════════════════════════════════════════════════════════════════

def standardize(signal: np.ndarray, window: int) -> np.ndarray:
    """Rolling z-score standardization.  signal shape: (T,) or (T, D)."""
    if signal.ndim == 1:
        signal = signal.reshape(-1, 1)

    T, D = signal.shape
    result = np.zeros_like(signal, dtype=float)

    for d in range(D):
        col = signal[:, d].astype(float)
        for t in range(T):
            start = max(0, t - window + 1)
            chunk = col[start:t + 1]
            mu = np.mean(chunk)
            sigma = np.std(chunk)
            result[t, d] = (col[t] - mu) / (sigma + 1e-10)

    return result.squeeze()


def cluster_signal(
    std_signal: np.ndarray, n_clusters: int, train_fraction: float, seed: int
) -> Tuple[np.ndarray, Any]:
    """K-means clustering.  Returns (labels, kmeans_model)."""
    if std_signal.ndim == 1:
        std_signal = std_signal.reshape(-1, 1)

    if not _HAS_SKLEARN:
        # Fallback: quantile-based binning (no sklearn needed)
        flat = std_signal.mean(axis=1) if std_signal.ndim > 1 else std_signal.ravel()
        quantiles = np.linspace(0, 100, n_clusters + 1)
        edges = np.percentile(flat, quantiles)
        labels = np.digitize(flat, edges[1:-1])
        return labels.astype(int), None

    half = int(len(std_signal) * train_fraction)
    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
    km.fit(std_signal[:half])
    labels = km.predict(std_signal)
    return labels.astype(int), km


def compute_qci(
    labels: np.ndarray, cmap: Dict[int, int], m: int,
    window: int, default_state: int = 5
) -> np.ndarray:
    """T-operator coherence index.  Returns array of length len(labels)-2."""
    t_match = []
    for t in range(len(labels) - 2):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        actual = cmap.get(int(labels[t + 2]), default_state)
        pred = qa_mod(b + e, m)
        t_match.append(1 if pred == actual else 0)

    arr = np.array(t_match, dtype=float)
    # Rolling mean
    out = np.full(len(arr), np.nan)
    min_p = window // 2
    for i in range(len(arr)):
        start = max(0, i - window + 1)
        chunk = arr[start:i + 1]
        if len(chunk) >= min_p:
            out[i] = float(np.mean(chunk))
    return out


def compute_orbit_distribution(
    labels: np.ndarray, cmap: Dict[int, int], m: int, default_state: int = 5
) -> Dict[str, Any]:
    """Orbit family distribution from consecutive state pairs."""
    family_counts = Counter()
    pair_families = []

    for t in range(len(labels) - 1):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        fam = classify_orbit_family(b, e, m)
        family_counts[fam] += 1
        pair_families.append(fam)

    total = sum(family_counts.values()) or 1
    fractions = {fam: count / total for fam, count in family_counts.items()}

    return {
        "counts": dict(family_counts),
        "fractions": fractions,
        "sequence_length": len(pair_families),
        "dominant_family": max(family_counts, key=family_counts.get) if family_counts else "none",
    }


def compute_toroidal_flow_distribution(
    labels: np.ndarray, cmap: Dict[int, int], m: int, default_state: int = 5
) -> Dict[str, Any]:
    """SVP toroidal flow distribution from consecutive state pairs.

    For each (state[t], state[t+1]), computes the orbit-level flow score
    and SVP flow classification.
    """
    flow_counts = Counter()
    flow_scores = []
    pair_to_flow: Dict[Tuple[int, int], Tuple[float, str]] = {}

    for t in range(len(labels) - 1):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        key = (qa_mod(b, m), qa_mod(e, m))

        if key not in pair_to_flow:
            pair_to_flow[key] = orbit_torus_flow_score(key[0], key[1], m)

        score, flow_type = pair_to_flow[key]
        flow_counts[flow_type] += 1
        if score >= 0:
            flow_scores.append(score)

    total = sum(flow_counts.values()) or 1
    fractions = {ft: count / total for ft, count in flow_counts.items()}

    score_arr = np.array(flow_scores) if flow_scores else np.array([0.0])
    return {
        "counts": dict(flow_counts),
        "fractions": fractions,
        "dominant_flow": max(flow_counts, key=flow_counts.get) if flow_counts else "none",
        "flow_score_stats": {
            "mean": float(np.mean(score_arr)),
            "std": float(np.std(score_arr)),
            "min": float(np.min(score_arr)),
            "max": float(np.max(score_arr)),
        },
        "svp_correspondence": {
            "outward": "cosmos (expansive, centrifugal, radiant)",
            "equilibrium": "satellite (bounded, balanced circulation)",
            "inward": "singularity (collapsed, centripetal, convergent)",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Transition Detection (#3)
# ═══════════════════════════════════════════════════════════════════════════

FAMILY_ORDER = ["cosmos", "satellite", "singularity"]
SVP_FLOW_ORDER = ["outward", "equilibrium", "inward"]
FAMILY_TO_SVP = {"cosmos": "outward", "satellite": "equilibrium", "singularity": "inward"}


def detect_orbit_transitions(
    labels: np.ndarray, cmap: Dict[int, int], m: int, default_state: int = 5
) -> Dict[str, Any]:
    """Detect transitions between orbit families over the signal.

    Returns transition matrix, event list, satellite streak analysis,
    and stability metrics.
    """
    # Build family sequence from consecutive state pairs
    families = []
    for t in range(len(labels) - 1):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        families.append(classify_orbit_family(b, e, m))

    if not families:
        return {"error": "no data"}

    # ── Transition matrix ──
    # P[i][j] = probability of moving from family_i to family_j
    trans_counts = defaultdict(lambda: defaultdict(int))
    for t in range(len(families) - 1):
        trans_counts[families[t]][families[t + 1]] += 1

    trans_matrix = {}
    for src in FAMILY_ORDER:
        row_total = sum(trans_counts[src].values())
        if row_total > 0:
            trans_matrix[src] = {
                dst: trans_counts[src][dst] / row_total for dst in FAMILY_ORDER
            }
        else:
            trans_matrix[src] = {dst: 0.0 for dst in FAMILY_ORDER}

    # ── Transition events (timestamped family changes) ──
    events = []
    for t in range(len(families) - 1):
        if families[t] != families[t + 1]:
            events.append({
                "t": t + 1,
                "from": families[t],
                "to": families[t + 1],
                "svp_from": FAMILY_TO_SVP.get(families[t], "?"),
                "svp_to": FAMILY_TO_SVP.get(families[t + 1], "?"),
            })

    # ── Transition rate ──
    n_transitions = len(events)
    transition_rate = n_transitions / max(len(families) - 1, 1)

    # ── Satellite streak analysis (metamorphosis detection) ──
    max_sat_streak = 0
    cur_sat_streak = 0
    sat_streaks = []
    for fam in families:
        if fam == "satellite":
            cur_sat_streak += 1
        else:
            if cur_sat_streak > 0:
                sat_streaks.append(cur_sat_streak)
            cur_sat_streak = 0
    if cur_sat_streak > 0:
        sat_streaks.append(cur_sat_streak)
    max_sat_streak = max(sat_streaks) if sat_streaks else 0

    # ── Dwell times (how long system stays in each family before transitioning) ──
    dwell_times = defaultdict(list)
    current_family = families[0]
    current_dwell = 1
    for t in range(1, len(families)):
        if families[t] == current_family:
            current_dwell += 1
        else:
            dwell_times[current_family].append(current_dwell)
            current_family = families[t]
            current_dwell = 1
    dwell_times[current_family].append(current_dwell)

    dwell_summary = {}
    for fam in FAMILY_ORDER:
        times = dwell_times.get(fam, [])
        if times:
            arr = np.array(times, dtype=float)
            dwell_summary[fam] = {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "max": int(np.max(arr)),
                "count": len(times),
            }
        else:
            dwell_summary[fam] = {"mean": 0, "median": 0, "max": 0, "count": 0}

    # ── Stability index ──
    # High stability = long dwell times, few transitions
    # Low stability = frequent transitions
    # Normalized: 1.0 = no transitions, 0.0 = transition every step
    stability = 1.0 - transition_rate

    return {
        "transition_matrix": trans_matrix,
        "n_transitions": n_transitions,
        "transition_rate": transition_rate,
        "stability_index": stability,
        "events": events,
        "n_events": len(events),
        "satellite_streak_max": max_sat_streak,
        "satellite_streak_metamorphosis": max_sat_streak >= 5,
        "dwell_times": dwell_summary,
        "family_sequence_length": len(families),
    }


def detect_qci_regime_shifts(
    qci: np.ndarray, threshold_std: float = 1.5
) -> Dict[str, Any]:
    """Detect regime shifts via QCI derivative analysis.

    A regime shift = sustained QCI drop exceeding threshold_std standard
    deviations from the rolling mean of the QCI derivative.

    Returns shift events, instability windows, and predictive metrics.
    """
    valid = qci[~np.isnan(qci)]
    if len(valid) < 10:
        return {"error": "insufficient QCI data", "shifts": []}

    # QCI first derivative (rate of coherence change)
    dqci = np.diff(valid)
    dqci_mean = float(np.mean(dqci))
    dqci_std = float(np.std(dqci))

    if dqci_std < 1e-10:
        return {
            "dqci_mean": dqci_mean, "dqci_std": dqci_std,
            "shifts": [], "n_shifts": 0,
            "instability_fraction": 0.0,
        }

    # Z-score of derivative
    dqci_z = (dqci - dqci_mean) / dqci_std

    # Detect sharp drops (negative z exceeds threshold)
    drop_mask = dqci_z < -threshold_std
    # Detect sharp rises (positive z exceeds threshold)
    rise_mask = dqci_z > threshold_std

    shifts = []
    in_drop = False
    drop_start = 0

    for t in range(len(dqci_z)):
        if drop_mask[t] and not in_drop:
            in_drop = True
            drop_start = t
        elif not drop_mask[t] and in_drop:
            in_drop = False
            shifts.append({
                "type": "coherence_drop",
                "t_start": int(drop_start),
                "t_end": int(t),
                "duration": int(t - drop_start),
                "magnitude": float(np.min(dqci_z[drop_start:t])),
                "svp_interpretation": "field destabilization — potential inward collapse",
            })

    for t in range(len(dqci_z)):
        if rise_mask[t]:
            # Find contiguous rise
            if t == 0 or not rise_mask[t - 1]:
                rise_start = t
            if t == len(dqci_z) - 1 or not rise_mask[t + 1]:
                shifts.append({
                    "type": "coherence_surge",
                    "t_start": int(rise_start),
                    "t_end": int(t + 1),
                    "duration": int(t + 1 - rise_start),
                    "magnitude": float(np.max(dqci_z[rise_start:t + 1])),
                    "svp_interpretation": "field expansion — outward radiation intensifying",
                })

    shifts.sort(key=lambda s: s["t_start"])

    # Instability fraction: what fraction of time is the system in a shift?
    shift_steps = sum(s["duration"] for s in shifts)
    instability_frac = shift_steps / max(len(dqci_z), 1)

    return {
        "dqci_mean": dqci_mean,
        "dqci_std": dqci_std,
        "shifts": shifts,
        "n_shifts": len(shifts),
        "instability_fraction": instability_frac,
        "svp_regime_interpretation": {
            "high_stability": "balanced toroidal circulation (equilibrium dominant)",
            "frequent_drops": "field collapse episodes (inward transitions)",
            "frequent_surges": "expansion bursts (outward radiation)",
            "mixed": "active field with competing flow modes",
        },
    }


def detect_svp_phase_transitions(
    labels: np.ndarray, cmap: Dict[int, int], m: int, default_state: int = 5
) -> Dict[str, Any]:
    """Detect SVP toroidal flow phase transitions.

    Maps orbit transitions to SVP flow changes:
      outward → equilibrium  = "field containment" (radiant → balanced)
      outward → inward       = "field collapse"    (radiant → convergent)
      equilibrium → outward  = "field expansion"   (balanced → radiant)
      equilibrium → inward   = "field decay"       (balanced → convergent)
      inward → equilibrium   = "field revival"     (convergent → balanced)
      inward → outward       = "field eruption"    (convergent → radiant)
    """
    SVP_TRANSITION_NAMES = {
        ("outward", "equilibrium"): "containment",
        ("outward", "inward"): "collapse",
        ("equilibrium", "outward"): "expansion",
        ("equilibrium", "inward"): "decay",
        ("inward", "equilibrium"): "revival",
        ("inward", "outward"): "eruption",
    }

    # Build SVP flow sequence
    pair_to_flow: Dict[Tuple[int, int], str] = {}
    flows = []
    for t in range(len(labels) - 1):
        b = cmap.get(int(labels[t]), default_state)
        e = cmap.get(int(labels[t + 1]), default_state)
        key = (qa_mod(b, m), qa_mod(e, m))
        if key not in pair_to_flow:
            _, flow_type = orbit_torus_flow_score(key[0], key[1], m)
            pair_to_flow[key] = flow_type
        flows.append(pair_to_flow[key])

    if len(flows) < 2:
        return {"error": "insufficient data", "phase_transitions": []}

    # Detect phase transitions
    phase_transitions = []
    trans_type_counts = Counter()
    for t in range(len(flows) - 1):
        if flows[t] != flows[t + 1]:
            pair = (flows[t], flows[t + 1])
            name = SVP_TRANSITION_NAMES.get(pair, f"{pair[0]}→{pair[1]}")
            phase_transitions.append({
                "t": t + 1,
                "from_flow": flows[t],
                "to_flow": flows[t + 1],
                "transition_name": name,
            })
            trans_type_counts[name] += 1

    # SVP flow transition matrix
    flow_trans = defaultdict(lambda: defaultdict(int))
    for t in range(len(flows) - 1):
        flow_trans[flows[t]][flows[t + 1]] += 1

    flow_matrix = {}
    for src in SVP_FLOW_ORDER:
        row_total = sum(flow_trans[src].values())
        if row_total > 0:
            flow_matrix[src] = {
                dst: flow_trans[src][dst] / row_total for dst in SVP_FLOW_ORDER
            }
        else:
            flow_matrix[src] = {dst: 0.0 for dst in SVP_FLOW_ORDER}

    # Dominant transition pattern
    if trans_type_counts:
        dominant = trans_type_counts.most_common(1)[0]
    else:
        dominant = ("none", 0)

    return {
        "svp_flow_transition_matrix": flow_matrix,
        "phase_transitions": phase_transitions,
        "n_phase_transitions": len(phase_transitions),
        "transition_type_counts": dict(trans_type_counts),
        "dominant_transition": {"name": dominant[0], "count": dominant[1]},
        "flow_sequence_length": len(flows),
        "svp_transition_glossary": {
            f"{k[0]}→{k[1]}": v for k, v in SVP_TRANSITION_NAMES.items()
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Main Harness
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HarnessResult:
    """Structured output of the full pipeline."""
    name: str
    config: Dict[str, Any]
    n_samples: int
    n_channels: int
    cmap: Dict[int, int]
    # QCI
    qci_mean: float
    qci_std: float
    qci_median: float
    qci_series: List[float]     # full QCI time series (for SVP comparison)
    # Orbit distribution
    orbit_distribution: Dict[str, Any]
    # Toroidal flow
    toroidal_flow: Dict[str, Any]
    # Transition detection (#3)
    orbit_transitions: Dict[str, Any]
    qci_regime_shifts: Dict[str, Any]
    svp_phase_transitions: Dict[str, Any]
    # State sequence (for SVP re-analysis)
    qa_state_sequence: List[int]
    # Metadata
    timestamp: str
    signal_hash: str
    harness_version: str = "1.0.0"

    def to_json(self, path: Optional[str] = None) -> str:
        """Serialize to JSON.  Optionally write to file."""
        d = asdict(self)
        # Clean up non-serializable values
        s = json.dumps(d, indent=2, default=str)
        if path:
            with open(path, "w") as f:
                f.write(s)
        return s


class QASVPHarness:
    """General-purpose QA → SVP cross-domain validation pipeline."""

    def __init__(self, config: Optional[HarnessConfig] = None):
        self.config = config or HarnessConfig()
        self.cmap = self.config.build_cmap()

    def run(
        self,
        signal: np.ndarray,
        name: str = "unnamed_signal",
        target: Optional[np.ndarray] = None,
    ) -> HarnessResult:
        """Run full pipeline on a time-series signal.

        Parameters
        ----------
        signal : np.ndarray
            Shape (T,) for univariate or (T, D) for multivariate.
        name : str
            Human-readable signal identifier.
        target : np.ndarray, optional
            Target variable for OOS correlation (not required for SVP comparison).

        Returns
        -------
        HarnessResult with all metrics and sequences needed for SVP comparison.
        """
        cfg = self.config
        signal = np.asarray(signal, dtype=float)
        if signal.ndim == 1:
            signal_2d = signal.reshape(-1, 1)
        else:
            signal_2d = signal

        T, D = signal_2d.shape

        # Signal fingerprint for reproducibility tracking
        sig_hash = hashlib.sha256(signal_2d.tobytes()).hexdigest()[:16]

        # Stage 1: Standardize
        std_signal = standardize(signal_2d, cfg.standardize_window)

        # Stage 2: Cluster
        labels, _km = cluster_signal(
            std_signal, cfg.n_clusters, cfg.train_fraction, cfg.seed
        )

        # Stage 3: QA state sequence
        qa_states = [self.cmap.get(int(l), cfg.default_state) for l in labels]

        # Stage 4: QCI
        qci = compute_qci(labels, self.cmap, cfg.modulus, cfg.qci_window,
                          cfg.default_state)
        valid_qci = qci[~np.isnan(qci)]

        # Stage 5: Orbit distribution
        orbit_dist = compute_orbit_distribution(
            labels, self.cmap, cfg.modulus, cfg.default_state
        )

        # Stage 6: Toroidal flow (SVP mapping)
        torus_flow = compute_toroidal_flow_distribution(
            labels, self.cmap, cfg.modulus, cfg.default_state
        )

        # Stage 7: Transition detection (#3)
        orbit_trans = detect_orbit_transitions(
            labels, self.cmap, cfg.modulus, cfg.default_state
        )
        qci_shifts = detect_qci_regime_shifts(qci)
        svp_phases = detect_svp_phase_transitions(
            labels, self.cmap, cfg.modulus, cfg.default_state
        )

        # Stage 8: OOS target correlation (optional)
        target_correlation = None
        if target is not None:
            target = np.asarray(target, dtype=float)
            # Align lengths (QCI is shorter by 2)
            min_len = min(len(valid_qci), len(target))
            if min_len > 10:
                half = min_len // 2
                oos_qci = valid_qci[-half:]
                oos_target = target[-half:]
                mask = ~(np.isnan(oos_qci) | np.isnan(oos_target))
                if mask.sum() > 5:
                    from scipy import stats as sp_stats
                    r, p = sp_stats.pearsonr(oos_qci[mask], oos_target[mask])
                    target_correlation = {
                        "r": float(r), "p": float(p), "n_oos": int(mask.sum()),
                        "significance": (
                            "***" if p < 0.001 else
                            "**" if p < 0.01 else
                            "*" if p < 0.05 else "ns"
                        ),
                    }

        # Package result
        result = HarnessResult(
            name=name,
            config={
                "modulus": cfg.modulus,
                "n_clusters": cfg.n_clusters,
                "qci_window": cfg.qci_window,
                "standardize_window": cfg.standardize_window,
                "train_fraction": cfg.train_fraction,
                "sample_rate": cfg.sample_rate,
            },
            n_samples=T,
            n_channels=D,
            cmap={int(k): int(v) for k, v in self.cmap.items()},
            qci_mean=float(np.mean(valid_qci)) if len(valid_qci) > 0 else 0.0,
            qci_std=float(np.std(valid_qci)) if len(valid_qci) > 0 else 0.0,
            qci_median=float(np.median(valid_qci)) if len(valid_qci) > 0 else 0.0,
            qci_series=[float(x) if not np.isnan(x) else None for x in qci],
            orbit_distribution=orbit_dist,
            toroidal_flow=torus_flow,
            orbit_transitions=orbit_trans,
            qci_regime_shifts=qci_shifts,
            svp_phase_transitions=svp_phases,
            qa_state_sequence=qa_states,
            timestamp=datetime.now(timezone.utc).isoformat(),
            signal_hash=sig_hash,
        )

        if target_correlation:
            result.toroidal_flow["target_correlation"] = target_correlation

        return result


# ═══════════════════════════════════════════════════════════════════════════
# Built-in Demo Signals
# ═══════════════════════════════════════════════════════════════════════════

def gen_sine(freq: float = 5.0, duration: float = 10.0, sr: float = 100.0) -> np.ndarray:
    """Pure sine wave."""
    t = np.arange(0, duration, 1 / sr)
    return np.sin(2 * np.pi * freq * t)


def gen_two_tone(f1: float = 5.0, f2: float = 12.0,
                 duration: float = 10.0, sr: float = 100.0) -> np.ndarray:
    """Superposition of two sine waves."""
    t = np.arange(0, duration, 1 / sr)
    return np.sin(2 * np.pi * f1 * t) + 0.5 * np.sin(2 * np.pi * f2 * t)


def gen_chirp(f0: float = 1.0, f1: float = 20.0,
              duration: float = 10.0, sr: float = 100.0) -> np.ndarray:
    """Linear frequency sweep from f0 to f1."""
    t = np.arange(0, duration, 1 / sr)
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * duration))
    return np.sin(phase)


def gen_am(carrier: float = 20.0, mod_freq: float = 2.0,
           duration: float = 10.0, sr: float = 100.0) -> np.ndarray:
    """Amplitude-modulated signal."""
    t = np.arange(0, duration, 1 / sr)
    envelope = 1 + 0.8 * np.sin(2 * np.pi * mod_freq * t)
    return envelope * np.sin(2 * np.pi * carrier * t)


def gen_ar1(alpha: float = 0.95, n: int = 1000) -> np.ndarray:
    """AR(1) process: x[t] = alpha * x[t-1] + noise."""
    rng = np.random.RandomState(42)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = alpha * x[t - 1] + rng.randn()
    return x


def gen_pink_noise(n: int = 1000) -> np.ndarray:
    """Approximate 1/f noise via spectral shaping."""
    rng = np.random.RandomState(42)
    white = rng.randn(n)
    fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n)
    freqs[0] = 1  # avoid division by zero
    fft /= np.sqrt(freqs)
    return np.fft.irfft(fft, n=n)


def gen_regime_switch(n: int = 1000) -> np.ndarray:
    """Signal with regime switch: low-vol → high-vol → low-vol."""
    rng = np.random.RandomState(42)
    third = n // 3
    seg1 = rng.randn(third) * 0.5
    seg2 = rng.randn(third) * 3.0 + np.sin(np.linspace(0, 8 * np.pi, third))
    seg3 = rng.randn(n - 2 * third) * 0.5
    return np.concatenate([seg1, seg2, seg3])


def gen_multi_channel(n: int = 1000, d: int = 4) -> np.ndarray:
    """Multi-channel signal with correlated + independent components."""
    rng = np.random.RandomState(42)
    common = rng.randn(n)
    channels = np.zeros((n, d))
    for i in range(d):
        channels[:, i] = 0.5 * common + 0.5 * rng.randn(n)
    return channels


DEMO_SIGNALS = {
    "sine_5hz": lambda: gen_sine(5.0, 10.0, 100.0),
    "two_tone": lambda: gen_two_tone(5.0, 12.0, 10.0, 100.0),
    "chirp": lambda: gen_chirp(1.0, 20.0, 10.0, 100.0),
    "am_modulated": lambda: gen_am(20.0, 2.0, 10.0, 100.0),
    "ar1_high": lambda: gen_ar1(0.95, 1000),
    "ar1_low": lambda: gen_ar1(0.50, 1000),
    "pink_noise": lambda: gen_pink_noise(1000),
    "white_noise": lambda: np.random.RandomState(42).randn(1000),
    "regime_switch": lambda: gen_regime_switch(1000),
    "multi_channel_4d": lambda: gen_multi_channel(1000, 4),
}


# ═══════════════════════════════════════════════════════════════════════════
# Main: run all demos
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("QA ↔ SVP CROSS-DOMAIN VALIDATION HARNESS")
    print("=" * 70)

    harness = QASVPHarness(HarnessConfig(modulus=24, n_clusters=6, qci_window=63))

    all_results = {}
    print(f"\n  Config: mod={harness.config.modulus}, "
          f"K={harness.config.n_clusters}, "
          f"window={harness.config.qci_window}")
    print(f"  cmap: {harness.cmap}")
    print(f"\n  Running {len(DEMO_SIGNALS)} demo signals...\n")

    for name, gen_fn in DEMO_SIGNALS.items():
        signal = gen_fn()
        result = harness.run(signal, name=name)
        all_results[name] = result

        # Compact summary
        orb = result.orbit_distribution["fractions"]
        flow = result.toroidal_flow["fractions"]
        print(f"  {name:<20}  "
              f"QCI={result.qci_mean:.3f}±{result.qci_std:.3f}  "
              f"orbits=[C:{orb.get('cosmos',0):.2f} "
              f"S:{orb.get('satellite',0):.2f} "
              f"X:{orb.get('singularity',0):.2f}]  "
              f"SVP=[out:{flow.get('outward',0):.2f} "
              f"eq:{flow.get('equilibrium',0):.2f} "
              f"in:{flow.get('inward',0):.2f}]")

    # ── Summary table ──
    print(f"\n{'=' * 70}")
    print("SUMMARY: ORBIT ↔ SVP FLOW ALIGNMENT ACROSS SIGNALS")
    print(f"{'=' * 70}")
    print(f"  {'Signal':<20} {'Dominant Orbit':<18} {'Dominant SVP Flow':<20} {'QCI':<10}")
    print(f"  {'─'*20} {'─'*18} {'─'*20} {'─'*10}")

    for name, result in all_results.items():
        dom_orb = result.orbit_distribution["dominant_family"]
        dom_flow = result.toroidal_flow["dominant_flow"]
        qci = result.qci_mean
        expected_flow = {"cosmos": "outward", "satellite": "equilibrium",
                         "singularity": "inward"}.get(dom_orb, "?")
        align = "+" if dom_flow == expected_flow else "-"
        print(f"  {name:<20} {dom_orb:<18} {dom_flow:<20} {qci:<10.3f} [{align}]")

    # ── Transition Detection Summary ──
    print(f"\n{'=' * 70}")
    print("TRANSITION DETECTION (#3)")
    print(f"{'=' * 70}")
    print(f"  {'Signal':<20} {'Transitions':<13} {'Rate':<8} "
          f"{'Stability':<10} {'QCI Shifts':<11} {'SVP Phases':<11} "
          f"{'Sat Streak':<10}")
    print(f"  {'─'*20} {'─'*13} {'─'*8} {'─'*10} {'─'*11} {'─'*11} {'─'*10}")

    for name, result in all_results.items():
        ot = result.orbit_transitions
        qs = result.qci_regime_shifts
        sp = result.svp_phase_transitions
        n_trans = ot.get("n_transitions", 0)
        rate = ot.get("transition_rate", 0)
        stab = ot.get("stability_index", 0)
        n_shifts = qs.get("n_shifts", 0)
        n_phases = sp.get("n_phase_transitions", 0)
        sat_str = ot.get("satellite_streak_max", 0)
        meta = "*" if ot.get("satellite_streak_metamorphosis", False) else ""
        print(f"  {name:<20} {n_trans:<13} {rate:<8.3f} "
              f"{stab:<10.3f} {n_shifts:<11} {n_phases:<11} "
              f"{sat_str}{meta:<10}")

    # Show transition details for most interesting signal (regime_switch)
    if "regime_switch" in all_results:
        rs = all_results["regime_switch"]
        print(f"\n  Regime Switch signal — detailed transitions:")
        tm = rs.orbit_transitions.get("transition_matrix", {})
        print(f"    Orbit transition matrix P[from → to]:")
        print(f"    {'':>14} {'cosmos':>10} {'satellite':>10} {'singularity':>12}")
        for src in FAMILY_ORDER:
            row = tm.get(src, {})
            print(f"    {src:>14} {row.get('cosmos',0):>10.3f} "
                  f"{row.get('satellite',0):>10.3f} {row.get('singularity',0):>12.3f}")

        fm = rs.svp_phase_transitions.get("svp_flow_transition_matrix", {})
        print(f"\n    SVP flow transition matrix P[from → to]:")
        print(f"    {'':>14} {'outward':>10} {'equilibrium':>12} {'inward':>10}")
        for src in SVP_FLOW_ORDER:
            row = fm.get(src, {})
            print(f"    {src:>14} {row.get('outward',0):>10.3f} "
                  f"{row.get('equilibrium',0):>12.3f} {row.get('inward',0):>10.3f}")

        # Dwell times
        dwell = rs.orbit_transitions.get("dwell_times", {})
        print(f"\n    Dwell times (steps in family before transition):")
        for fam in FAMILY_ORDER:
            d = dwell.get(fam, {})
            if d.get("count", 0) > 0:
                print(f"      {fam:>14}: mean={d['mean']:.1f} "
                      f"max={d['max']} episodes={d['count']}")

        # QCI regime shifts
        shifts = rs.qci_regime_shifts.get("shifts", [])
        if shifts:
            print(f"\n    QCI regime shifts ({len(shifts)} detected):")
            for s in shifts[:5]:
                print(f"      t={s['t_start']:>4}-{s['t_end']:<4} "
                      f"{s['type']:<18} mag={s['magnitude']:+.2f}  "
                      f"({s['svp_interpretation']})")

        # SVP phase transitions (first few)
        phases = rs.svp_phase_transitions.get("transition_type_counts", {})
        if phases:
            print(f"\n    SVP phase transition types:")
            for name_t, count in sorted(phases.items(), key=lambda x: -x[1]):
                print(f"      {name_t:<20} {count:>4} occurrences")

    # ── Save all results ──
    output_path = "qa_svp_harness_results.json"
    combined = {
        "harness_version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": asdict(harness.config),
        "cmap": {str(k): v for k, v in harness.cmap.items()},
        "svp_correspondence_key": {
            "outward": "cosmos — centrifugal / radiant / expansive",
            "equilibrium": "satellite — balanced toroidal circulation",
            "inward": "singularity — centripetal / convergent / collapsed",
        },
        "signals": {},
    }
    for name, result in all_results.items():
        combined["signals"][name] = {
            "n_samples": result.n_samples,
            "n_channels": result.n_channels,
            "signal_hash": result.signal_hash,
            "qci": {
                "mean": result.qci_mean,
                "std": result.qci_std,
                "median": result.qci_median,
            },
            "orbit_distribution": result.orbit_distribution,
            "toroidal_flow": result.toroidal_flow,
            "transitions": {
                "orbit": {
                    "matrix": result.orbit_transitions.get("transition_matrix"),
                    "n_transitions": result.orbit_transitions.get("n_transitions"),
                    "rate": result.orbit_transitions.get("transition_rate"),
                    "stability_index": result.orbit_transitions.get("stability_index"),
                    "dwell_times": result.orbit_transitions.get("dwell_times"),
                    "satellite_streak_max": result.orbit_transitions.get("satellite_streak_max"),
                },
                "qci_regime_shifts": {
                    "n_shifts": result.qci_regime_shifts.get("n_shifts"),
                    "instability_fraction": result.qci_regime_shifts.get("instability_fraction"),
                },
                "svp_phase": {
                    "matrix": result.svp_phase_transitions.get("svp_flow_transition_matrix"),
                    "n_transitions": result.svp_phase_transitions.get("n_phase_transitions"),
                    "dominant": result.svp_phase_transitions.get("dominant_transition"),
                    "type_counts": result.svp_phase_transitions.get("transition_type_counts"),
                },
            },
            "qa_state_sequence_length": len(result.qa_state_sequence),
        }

    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"\n  Results saved: {output_path}")

    # ── Per-signal detailed JSON ──
    for name, result in all_results.items():
        path = f"qa_svp_harness_{name}.json"
        result.to_json(path)
    print(f"  Per-signal JSONs: qa_svp_harness_<signal>.json ({len(all_results)} files)")

    print(f"\n  To compare with SVP:")
    print(f"    1. Load qa_svp_harness_<signal>.json")
    print(f"    2. Extract 'qa_state_sequence' and 'qci_series'")
    print(f"    3. Run SVP harmonic analysis on the same raw signal")
    print(f"    4. Compare SVP flow classification with 'toroidal_flow' results")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
