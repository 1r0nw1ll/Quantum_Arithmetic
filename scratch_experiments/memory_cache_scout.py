#!/usr/bin/env python3
"""
Memory Cache Scout (offline prototype)

Build a simple memory over existing artifacts/evals to recommend a pipeline
and re-serve results for similar tasks without recomputation.

Approach
- Parse artifacts/evals/* JSON files
- Extract signatures per artifact type (e8 mean/std; qa rows count, etc.)
- Use a lightweight KNN over signatures keyed by task keywords
- Report: cache coverage, nearest match quality, and suggestion summary

No modifications to lab/executor — read-only, offline.
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

BASE = Path(__file__).resolve().parents[1]
ART = BASE / "artifacts" / "evals"


@dataclass
class ArtifactSig:
    path: Path
    kind: str
    task_id: str
    features: List[float]
    quality: float


def artifact_kind(p: Path) -> str:
    name = p.name
    if name.startswith("e8_benchmark_"):
        return "e8_benchmark"
    if name.startswith("e8_scout_"):
        return "e8_scout"
    if name.startswith("e8_orchestrator_"):
        return "e8_orchestrator"
    if name.startswith("qa_orchestrator_"):
        return "qa_orchestrator"
    return "other"


def load_e8_sig(p: Path) -> Optional[ArtifactSig]:
    try:
        d = json.load(open(p))
        stats = d.get("statistics", {})
        mean = float(stats.get("mean_alignment", 0.0))
        std = float(stats.get("std_alignment", 0.0))
        mx = float(stats.get("max_alignment", 0.0))
        mn = float(stats.get("min_alignment", 0.0))
        task_id = d.get("task_id") or p.stem.split("_", 2)[-1]
        return ArtifactSig(path=p, kind=artifact_kind(p), task_id=task_id,
                           features=[mean, std, mx, mn], quality=mean)
    except Exception:
        return None


def load_qa_sig(p: Path) -> Optional[ArtifactSig]:
    try:
        d = json.load(open(p))
        rows = d.get("rows")
        count = int(d.get("count") or (len(rows) if isinstance(rows, list) else 0))
        task_id = d.get("task_id") or p.stem.split("_", 2)[-1]
        # Map to a neutral quality (we don't have a canonical metric for QA rows)
        q = min(1.0, 0.3 + 0.01 * count)
        return ArtifactSig(path=p, kind="qa_orchestrator", task_id=task_id,
                           features=[count / 100.0], quality=q)
    except Exception:
        return None


def l2(a: List[float], b: List[float]) -> float:
    s = 0.0
    for x, y in zip(a, b):
        d = (x - y)
        s += d * d
    return s ** 0.5


def build_memory() -> List[ArtifactSig]:
    sigs: List[ArtifactSig] = []
    for fp in glob.glob(str(ART / "*.json")):
        p = Path(fp)
        k = artifact_kind(p)
        sig = None
        if k in {"e8_benchmark", "e8_scout", "e8_orchestrator"}:
            sig = load_e8_sig(p)
        elif k == "qa_orchestrator":
            sig = load_qa_sig(p)
        if sig:
            sigs.append(sig)
    return sigs


def recommend(memory: List[ArtifactSig], query_title: str) -> Dict:
    title = query_title.lower()
    if any(w in title for w in ["e8", "alignment", "benchmark"]):
        # Find nearest E8 signature
        e8s = [s for s in memory if s.kind.startswith("e8_")]
        if not e8s:
            return {"pipeline": "e8_tool", "strategy": "no_memory_fallback"}
        # Use average features as target prototype (E8 distribution is stable)
        proto = [sum(f[i] for f in [s.features for s in e8s]) / len(e8s) for i in range(len(e8s[0].features))]
        best = min(e8s, key=lambda s: l2(s.features, proto))
        return {
            "pipeline": "e8_tool",
            "reason": "nearest_prior_e8_artifact",
            "expected_quality": best.quality,
            "artifact": str(best.path),
        }
    elif any(w in title for w in ["qa ", "invariant", "tuple"]):
        qas = [s for s in memory if s.kind == "qa_orchestrator"]
        if not qas:
            return {"pipeline": "qa_tool", "strategy": "no_memory_fallback"}
        best = max(qas, key=lambda s: s.quality)
        return {
            "pipeline": "qa_tool",
            "reason": "best_prior_qa_artifact",
            "expected_quality": best.quality,
            "artifact": str(best.path),
        }
    else:
        # Unknown task: pick most frequent high-quality family (E8 if present)
        fams = {
            "e8_tool": [s.quality for s in memory if s.kind.startswith("e8_")],
            "qa_tool": [s.quality for s in memory if s.kind == "qa_orchestrator"],
        }
        best = max(fams.items(), key=lambda kv: (len(kv[1]), sum(kv[1]) / max(1, len(kv[1]))))
        return {"pipeline": best[0], "strategy": "popularity_quality_mix"}


def main():
    memory = build_memory()
    e8_count = sum(1 for s in memory if s.kind.startswith("e8_"))
    qa_count = sum(1 for s in memory if s.kind == "qa_orchestrator")
    print("Memory Cache Scout")
    print("=" * 60)
    print(f"Loaded {len(memory)} artifacts | E8: {e8_count} | QA: {qa_count}")

    # Demo queries
    queries = [
        "E8 alignment benchmark: mod-24 QA system",
        "QA invariants sampler for tuples",
        "Unknown task type: choose best prior"
    ]
    for q in queries:
        rec = recommend(memory, q)
        print(f"- Query: {q}\n  -> Recommendation: {json.dumps(rec, indent=2)}")


if __name__ == "__main__":
    main()

