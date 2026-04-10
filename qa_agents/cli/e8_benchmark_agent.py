#!/usr/bin/env python3
"""
e8_benchmark_agent.py - E8 Alignment Benchmark Agent

Agent for computing E8 root system alignment scores across the full mod 24 QA orbit.
This is a working agent designed as a proof-of-concept for Path 3 (Fix Everything).

**What this agent does:**
1. Computes all 576 (24×24) QA tuples in mod 24 system
2. Calculates E8 alignment using full 240-root system
3. Generates JSON artifacts with results and statistics
4. Returns proper status for reviewer validation

**Task format expected:**
```yaml
title: "E8 alignment benchmark"
description: "Compute E8 alignments for mod 24 QA system"
```

**Output artifact format:**
```json
{
  "task_id": "...",
  "timestamp": "...",
  "total_tuples": 576,
  "results": [
    {"b": 1, "e": 1, "d": 2, "a": 3, "e8_alignment": 0.923},
    ...
  ],
  "statistics": {
    "mean_alignment": 0.456,
    "max_alignment": 0.987,
    "min_alignment": 0.123,
    "std_alignment": 0.234
  }
}
```

**Week 1, Day 1-2 of Path 3 Roadmap**
**Date**: 2025-11-30
"""

from __future__ import annotations

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class E8BenchmarkAgent:
    """
    Agent for computing E8 alignment benchmarks across QA mod 24 system.

    This agent loads the full 240 E8 roots and computes alignments for all
    576 possible (b, e) pairs in the mod 24 QA system.
    """

    def __init__(self, base_dir: Path = None):
        """
        Initialize E8 Benchmark Agent.

        Args:
            base_dir: Base directory for QA lab (defaults to parent of this file)
        """
        if base_dir is None:
            # Assume we're in qa_agents/cli/, so base is ../../
            base_dir = Path(__file__).parent.parent.parent

        self.base_dir = Path(base_dir)
        self.artifacts_dir = self.base_dir / "artifacts" / "evals"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Load E8 roots
        self.e8_roots = self._load_e8_roots()
        print(f"✓ Loaded {len(self.e8_roots)} E8 roots")

    def _load_e8_roots(self) -> np.ndarray:
        """
        Load the full 240 E8 root system.

        Returns:
            np.ndarray: Shape (240, 8) unit-normalized E8 roots
        """
        e8_path = self.base_dir / "data" / "e8_roots_unit.npy"

        if not e8_path.exists():
            raise FileNotFoundError(
                f"E8 roots not found at {e8_path}\n"
                f"Run: python scripts/generate_e8_roots.py"
            )

        roots = np.load(e8_path)

        if roots.shape != (240, 8):
            raise ValueError(
                f"Expected E8 roots shape (240, 8), got {roots.shape}"
            )

        return roots

    def _project_to_8d(self, b: int, e: int, d: int, a: int) -> np.ndarray:
        """
        Project QA tuple (b, e, d, a) to 8D space.

        QA tuples naturally embed into 8D as [b, e, d, a, 0, 0, 0, 0].
        This embedding preserves the additive structure and allows comparison
        with E8 root system.

        Args:
            b, e, d, a: QA tuple components

        Returns:
            np.ndarray: Unit-normalized 8D vector
        """
        vector = np.array([b, e, d, a, 0, 0, 0, 0], dtype=np.float64)
        norm = np.linalg.norm(vector)

        if norm == 0:
            return vector

        return vector / norm

    def _compute_e8_alignment(self, b: int, e: int, d: int, a: int) -> float:
        """
        Compute E8 alignment score using full 240-root system.

        E8 alignment is the maximum cosine similarity between the QA vector
        and any of the 240 E8 roots. Higher values indicate geometric resonance
        with the E8 Lie algebra structure.

        Args:
            b, e, d, a: QA tuple components

        Returns:
            float: Maximum alignment score [0, 1]
        """
        qa_vector = self._project_to_8d(b, e, d, a)

        # Compute cosine similarity with all 240 roots
        # qa_vector: (8,), e8_roots: (240, 8) -> similarities: (240,)
        similarities = np.abs(np.dot(self.e8_roots, qa_vector))

        # Return maximum alignment
        max_alignment = float(np.max(similarities))
        return max_alignment

    def execute(self, task: Dict) -> Dict:
        """
        Execute E8 benchmark task.

        Computes E8 alignments for all 576 (24×24) QA tuples in mod 24 system.

        Args:
            task: Task dictionary with 'id', 'title', 'description'

        Returns:
            Dict with keys:
                - status: "ok" or "error"
                - artifact: Path to output JSON file
                - tuples_computed: Number of tuples processed
                - mean_alignment: Average E8 alignment
                - max_alignment: Best alignment found
                - error: Error message (if status="error")
        """
        task_id = task.get('id', 'unknown')

        print(f"\n{'='*60}")
        print(f"E8 BENCHMARK AGENT: {task_id}")
        print(f"{'='*60}")
        print(f"Computing E8 alignments for mod 24 QA system...")

        try:
            results = []

            # Compute all 24×24 = 576 tuples
            for b in range(1, 25):
                for e in range(1, 25):
                    # QA arithmetic (mod 24, using 1-24 not 0-23)
                    d = ((b + e - 1) % 24) + 1
                    a = ((b + 2*e - 1) % 24) + 1

                    # Compute E8 alignment
                    alignment = self._compute_e8_alignment(b, e, d, a)

                    results.append({
                        "b": b,
                        "e": e,
                        "d": d,
                        "a": a,
                        "e8_alignment": alignment
                    })

            # Compute statistics
            alignments = np.array([r["e8_alignment"] for r in results])
            stats = {
                "mean_alignment": float(np.mean(alignments)),
                "max_alignment": float(np.max(alignments)),
                "min_alignment": float(np.min(alignments)),
                "std_alignment": float(np.std(alignments)),
                "median_alignment": float(np.median(alignments))
            }

            print(f"\n✓ Computed {len(results)} tuples")
            print(f"  Mean E8 alignment: {stats['mean_alignment']:.4f}")
            print(f"  Max E8 alignment:  {stats['max_alignment']:.4f}")
            print(f"  Min E8 alignment:  {stats['min_alignment']:.4f}")

            # Find top 5 tuples with highest alignment
            sorted_results = sorted(results, key=lambda x: x["e8_alignment"], reverse=True)
            top_5 = sorted_results[:5]

            print(f"\n  Top 5 tuples by E8 alignment:")
            for i, r in enumerate(top_5, 1):
                print(f"    {i}. ({r['b']:2d}, {r['e']:2d}, {r['d']:2d}, {r['a']:2d}) = {r['e8_alignment']:.6f}")

            # Write artifact JSON
            output_file = self.artifacts_dir / f"e8_benchmark_{task_id}.json"
            output_data = {
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "agent": "e8_benchmark",
                "total_tuples": len(results),
                "modulus": 24,
                "results": results,
                "statistics": stats,
                "top_5_tuples": top_5
            }

            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)

            print(f"\n✓ Artifact written: {output_file}")
            print(f"  Size: {output_file.stat().st_size} bytes")
            print(f"{'='*60}\n")

            return {
                "status": "ok",
                "agent": "e8_benchmark",
                "artifact": str(output_file),
                "tuples_computed": len(results),
                "mean_alignment": stats["mean_alignment"],
                "max_alignment": stats["max_alignment"]
            }

        except Exception as e:
            error_msg = f"e8_benchmark_failed: {str(e)}"
            print(f"\n✗ ERROR: {error_msg}")
            print(f"{'='*60}\n")

            return {
                "status": "error",
                "agent": "e8_benchmark",
                "error": error_msg
            }


def main():
    """
    Standalone test of E8 Benchmark Agent.

    This allows testing the agent without running it through the executor.
    """
    print("E8 Benchmark Agent - Standalone Test")
    print("=" * 60)

    # Create test task
    test_task = {
        "id": "test-e8-standalone",
        "title": "E8 alignment benchmark (standalone test)",
        "description": "Test E8 benchmark agent"
    }

    # Initialize agent
    agent = E8BenchmarkAgent()

    # Execute task
    result = agent.execute(test_task)

    # Print result
    print("\nAgent Result:")
    print("-" * 60)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("=" * 60)

    if result["status"] == "ok":
        print("\n✓ Standalone test PASSED")
        return 0
    else:
        print("\n✗ Standalone test FAILED")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
