#!/usr/bin/env python3
"""
E8 Family Explorer

Computes E8 alignment across the full mod-24 QA system and summarizes
statistics for structured families (Fibonacci-like seeds, Lucas-like seeds,
digital-root classes, parity/prime classes). Produces CSV, JSON, and a
compact Markdown summary.

Outputs go to: scratch_experiments/out/e8_family_explorer_*.{csv,json,md}
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

BASE = Path(__file__).resolve().parents[1]
OUT_DIR = BASE / "scratch_experiments" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_e8_roots(base: Path) -> np.ndarray:
    p = base / "data" / "e8_roots_unit.npy"
    roots = np.load(p)
    if roots.shape[1] != 8:
        raise ValueError(f"expected 8D roots, got {roots.shape}")
    return roots


def mod24(x: int) -> int:
    return ((x - 1) % 24) + 1


def qa_tuple(b: int, e: int) -> Tuple[int, int, int, int]:
    d = mod24(b + e)
    a = mod24(e + d)
    return b, e, d, a


def project_to_8d(b: int, e: int, d: int, a: int) -> np.ndarray:
    v = np.array([b, e, d, a, 0, 0, 0, 0], dtype=np.float64)
    n = np.linalg.norm(v)
    return v if n == 0 else v / n


def e8_alignment(v: np.ndarray, roots: np.ndarray) -> float:
    # max absolute cosine similarity
    sims = np.abs(roots @ v)
    return float(sims.max())


def digital_root(n: int) -> int:
    n = abs(n)
    while n >= 10:
        n = sum(int(c) for c in str(n))
    return 9 if n == 0 else n


def families_for(b: int, e: int, d: int, a: int) -> List[str]:
    fams: List[str] = []
    # Fibonacci-like seeds (mod 24): consecutive pairs stepping forward
    fib_pairs = {
        (1, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 13), (13, 21), (21, 10), (10, 7), (7, 17)
    }
    if (b, e) in fib_pairs:
        fams.append("fib_seed")

    # Lucas-like seeds mod 24 (approximate cycle)
    lucas_pairs = {
        (2, 1), (3, 4), (4, 7), (7, 11), (11, 18), (18, 5), (5, 23), (23, 4)
    }
    if (b, e) in lucas_pairs:
        fams.append("lucas_seed")

    # Digital-root class by d (the closure sum)
    fams.append(f"dr_d_{digital_root(d)}")

    # Parity class
    fams.append(f"parity_{b % 2}{e % 2}")

    # Prime class (b or e prime)
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    if b in primes or e in primes:
        fams.append("prime_edge")
    else:
        fams.append("composite_edge")

    # Named tuples
    if (b, e, d, a) == (1, 2, 3, 5):
        fams.append("grant_lrt")
    if (b, e, d, a) == (3, 5, 8, 13):
        fams.append("satellite")

    return fams


def main():
    roots = load_e8_roots(BASE)
    rows: List[Dict] = []

    for b in range(1, 25):
        for e in range(1, 25):
            b_, e_, d, a = qa_tuple(b, e)
            v = project_to_8d(b_, e_, d, a)
            align = e8_alignment(v, roots)
            fams = families_for(b_, e_, d, a)
            rows.append({
                "b": b_, "e": e_, "d": d, "a": a,
                "alignment": align,
                "families": fams,
            })

    # Summary per family
    fam_stats: Dict[str, Dict] = {}
    for r in rows:
        for fam in r["families"]:
            st = fam_stats.setdefault(fam, {"count": 0, "sum": 0.0, "max": 0.0, "min": 1.0, "top": []})
            st["count"] += 1
            st["sum"] += r["alignment"]
            st["max"] = max(st["max"], r["alignment"])
            st["min"] = min(st["min"], r["alignment"])
    for fam, st in fam_stats.items():
        st["mean"] = st["sum"] / max(1, st["count"])
        # top tuples in this family
        fam_rows = [r for r in rows if fam in r["families"]]
        st["top"] = sorted(
            [{"b": r["b"], "e": r["e"], "d": r["d"], "a": r["a"], "alignment": r["alignment"]} for r in fam_rows],
            key=lambda x: x["alignment"], reverse=True
        )[:5]

    # Overall top 20
    overall_top = sorted(rows, key=lambda r: r["alignment"], reverse=True)[:20]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = OUT_DIR / f"e8_family_explorer_{ts}"

    # Write CSV
    csv_path = base.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["b", "e", "d", "a", "alignment", "families"])
        for r in rows:
            w.writerow([r["b"], r["e"], r["d"], r["a"], f"{r['alignment']:.9f}", ";".join(r["families"])])

    # Write JSON summary
    json_path = base.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump({
            "overall_top": overall_top,
            "family_stats": fam_stats,
            "total": len(rows)
        }, f, indent=2)

    # Write Markdown summary
    md_path = base.with_suffix(".md")
    with open(md_path, "w") as f:
        f.write("# E8 Family Explorer\n\n")
        f.write(f"Total tuples: {len(rows)}\n\n")
        f.write("## Overall Top 10\n")
        for i, r in enumerate(overall_top[:10], 1):
            f.write(f"{i}. ({r['b']}, {r['e']}, {r['d']}, {r['a']}) = {r['alignment']:.6f}\n")
        f.write("\n## Selected Families\n")
        for fam in ["grant_lrt", "satellite", "fib_seed", "lucas_seed", "prime_edge", "composite_edge", "parity_00", "parity_11", "dr_d_9", "dr_d_1"]:
            if fam in fam_stats:
                st = fam_stats[fam]
                f.write(f"\n### {fam}\n")
                f.write(f"count={st['count']}, mean={st['mean']:.6f}, max={st['max']:.6f}, min={st['min']:.6f}\n")
                for j, t in enumerate(st["top"], 1):
                    f.write(f"  {j}. ({t['b']}, {t['e']}, {t['d']}, {t['a']}) = {t['alignment']:.6f}\n")

    print("E8 Family Explorer outputs:")
    print("-", csv_path)
    print("-", json_path)
    print("-", md_path)


if __name__ == "__main__":
    main()

