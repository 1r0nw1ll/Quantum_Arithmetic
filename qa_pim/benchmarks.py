"""Benchmark suite for QA Graph-PIM operations."""

import time
import numpy as np
from typing import Dict, Any

from .schema import generate_graph_data, QAParams
from .kernels import RESIDUE_SELECT, ROLLING_SUM_PHASE
from .crt import crt_join_general
from .graph import build_sector_csr, neighbor_expand
from .util import timing_context, percentile_stats


def benchmark_residue_neighbor(
    N: int = 100000, E: int = 500000, trials: int = 10,
) -> Dict[str, Any]:
    """Benchmark 1: Residue-select + neighbor expand."""
    data = generate_graph_data(N, E)
    sectors = data["sectors"]
    edges = data["edges"]
    m = data["params"].m

    sector_csr = build_sector_csr(sectors, edges, m)

    sector_vertices = {}
    for s in range(m):
        sector_vertices[s] = np.where(sectors == s)[0]

    durations = []
    edge_counts = []

    for _ in range(trials):
        mask_sectors = set(np.random.choice(m, 8, replace=False))

        with timing_context() as timer:
            selected_mask = RESIDUE_SELECT(sectors, mask_sectors)
            edge_count, _neighbors = neighbor_expand(
                sector_csr, sector_vertices, selected_mask,
            )

        durations.append(timer.elapsed)
        edge_counts.append(edge_count)

    avg_edges = np.mean(edge_counts)
    teps = avg_edges / np.mean(durations) if durations else 0

    return {
        "name": "residue_neighbor",
        "throughput_teps": teps,
        "avg_edges_traversed": int(avg_edges),
        "timing": percentile_stats(durations),
    }


def benchmark_rolling_phase(
    N: int = 100000, trials: int = 100,
) -> Dict[str, Any]:
    """Benchmark 2: Rolling sums on phase ring."""
    data = generate_graph_data(N)
    P = data["params"].P

    durations = []
    bytes_processed = []

    for _ in range(trials):
        phase_series = np.random.randint(-1000, 1000, P, dtype=np.int64)

        with timing_context() as timer:
            result = ROLLING_SUM_PHASE(phase_series, width=64)

        durations.append(timer.elapsed)
        bytes_processed.append(phase_series.nbytes + result.nbytes)

    avg_bytes = np.mean(bytes_processed)
    gbps = (avg_bytes / np.mean(durations)) / (1024**3) if durations else 0

    return {
        "name": "rolling_phase",
        "throughput_gbps": gbps,
        "avg_bytes": int(avg_bytes),
        "timing": percentile_stats(durations),
    }


def benchmark_crt_general(trials: int = 100000) -> Dict[str, Any]:
    """Benchmark 3: CRT join (general)."""
    rng = np.random.RandomState(42)
    a1_vals = rng.randint(0, 24, trials)
    a2_vals = rng.randint(0, 30, trials)

    unsolvable_count = 0
    durations = []

    start_time = time.perf_counter()

    for i in range(trials):
        iter_start = time.perf_counter()
        result = crt_join_general(int(a1_vals[i]), 24, int(a2_vals[i]), 30)
        durations.append(time.perf_counter() - iter_start)

        if result == (None, None):
            unsolvable_count += 1

    total_time = time.perf_counter() - start_time
    joins_per_sec = trials / total_time if total_time > 0 else 0

    return {
        "name": "crt_general",
        "throughput_joins_per_sec": joins_per_sec,
        "unsolvable_fraction": unsolvable_count / trials if trials > 0 else 0,
        "total_joins": trials,
        "timing": percentile_stats(durations),
    }


def benchmark_spectral_anomaly(
    N: int = 100000, trials: int = 50,
) -> Dict[str, Any]:
    """Benchmark 4: Spectral anomaly proxy (rolling z-score)."""
    data = generate_graph_data(N)
    P = data["params"].P

    durations = []
    anomaly_counts = []

    for _ in range(trials):
        phase_series = np.random.normal(0, 1, P).astype(np.float64)
        anomaly_indices = np.random.choice(P, P // 20, replace=False)
        phase_series[anomaly_indices] += np.random.normal(0, 5, len(anomaly_indices))

        with timing_context() as timer:
            window = 32
            rolling_mean = ROLLING_SUM_PHASE(phase_series, window) / window
            rolling_var = np.var(phase_series)
            z_scores = np.abs(phase_series - rolling_mean) / np.sqrt(rolling_var + 1e-8)
            anomalies = int(np.sum(z_scores > 3.0))

        durations.append(timer.elapsed)
        anomaly_counts.append(anomalies)

    avg_anomalies = np.mean(anomaly_counts)
    anomalies_per_sec = avg_anomalies / np.mean(durations) if durations else 0

    return {
        "name": "spectral_anomaly",
        "throughput_anomalies_per_sec": anomalies_per_sec,
        "avg_anomalies_found": int(avg_anomalies),
        "timing": percentile_stats(durations),
    }


def run_all() -> Dict[str, Any]:
    """Run all benchmarks and return results."""
    print("Running QA Graph-PIM benchmarks...")

    results = {
        "qa_graph_pim_benchmarks": {
            "version": "0.2.0",
            "timestamp": time.time(),
        }
    }

    for bench_func in [
        benchmark_residue_neighbor,
        benchmark_rolling_phase,
        benchmark_crt_general,
        benchmark_spectral_anomaly,
    ]:
        print(f"  Running {bench_func.__name__}...")
        try:
            result = bench_func()
            results[result["name"]] = result
            print(f"    OK: {result['name']}")
        except Exception as e:
            print(f"    ERROR in {bench_func.__name__}: {e}")
            results[f"{bench_func.__name__}_error"] = str(e)

    return results
