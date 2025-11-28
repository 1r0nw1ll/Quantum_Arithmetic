#!/usr/bin/env python3
"""
fastpath_auto_apply.py - Test-and-apply fast-path suggestions (safe, artifact-driven).

Behavior
- Reads vault mining suggestions from artifacts/evals/fastpath_mining.json.
- Benchmarks current vs suggested settings with the eval core (multiple seeds).
- Accepts only if speedup improves by a minimum margin and survivors stay healthy.
- Persists accepted settings to qa_lab/.env; logs all decisions to artifacts/evals/fastpath_apply_log.json.

Notes
- Single pass; quiet; daily summary remains minimal. Use the apply log for decisions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Dict, Any


ROOT = Path('.')
ART = ROOT / 'artifacts' / 'evals'
EVAL_JSON = ART / 'fastpath_eval.json'
MINING_JSON = ART / 'fastpath_mining.json'
APPLY_LOG = ART / 'fastpath_apply_log.json'
ENV_PATH = ROOT / '.env'


def read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def update_env_file(path: Path, updates: Dict[str, str]) -> None:
    lines = []
    existing = {}
    if path.exists():
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            if '=' in raw and not raw.strip().startswith('#'):
                k, v = raw.split('=', 1)
                existing[k.strip()] = v.strip()
            lines.append(raw)
    else:
        lines = []
    # Apply updates
    out_lines = []
    seen = set()
    for raw in lines:
        if '=' in raw and not raw.strip().startswith('#'):
            k, _ = raw.split('=', 1)
            k = k.strip()
            if k in updates:
                out_lines.append(f"{k}={updates[k]}")
                seen.add(k)
            else:
                out_lines.append(raw)
        else:
            out_lines.append(raw)
    # Append missing keys
    for k, v in updates.items():
        if k not in seen and k not in existing:
            out_lines.append(f"{k}={v}")
    path.write_text('\n'.join(out_lines).rstrip() + '\n', encoding='utf-8')


def load_current_settings() -> Dict[str, str]:
    vals: Dict[str, str] = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def _eval_speed_with_env(phi_tol: float | None, curv_w: float | None, ideal_w: float | None,
                         seeds: list[int] | None = None) -> Dict[str, float]:
    """Run eval across multiple seeds and return median metrics."""
    import importlib
    # Ensure we can import qa_fast_eval from parent directory (qa_lab)
    here = Path(__file__).resolve().parent
    parent = here.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    qa_fast_eval = importlib.import_module('qa_fast_eval')

    # Prepare environment for this eval set (do not persist here)
    if phi_tol is not None:
        os.environ['QA_FP_ENABLE_FAMILY'] = '1'
        os.environ['QA_FP_FAMILY_TOL'] = str(phi_tol)
    if curv_w is not None:
        os.environ['QA_QA_CURV_WEIGHT'] = str(curv_w)
    if ideal_w is not None:
        os.environ['QA_QA_IDEAL_WEIGHT'] = str(ideal_w)
    os.environ['QA_FP_ENABLE_WHEEL'] = os.getenv('QA_FP_ENABLE_WHEEL', '1')
    os.environ['QA_E8_VEC_CHUNK'] = os.getenv('QA_E8_VEC_CHUNK', '200000')

    if not seeds:
        seeds = [0, 1, 2]
    metrics = []
    for sd in seeds:
        res = qa_fast_eval._run_eval(n=200_000, qe_topk=4096, topk=256, seed=sd,
                                     qe_curv_weight=curv_w, family_phi_tol=phi_tol,
                                     e8_chunk=200_000)
        metrics.append({
            'speedup': float(res.get('speedup_vs_baseline', 0.0)),
            'post_gates': float(res.get('post_gates', 0.0)),
            'post_qa': float(res.get('post_qa', res.get('post_qe', 0.0))),
            'pipeline': float(res.get('time_sec_pipeline', 0.0)),
            'baseline': float(res.get('time_sec_baseline', 0.0)),
        })

    # Median aggregation for robustness
    import statistics as st
    agg = {
        'speedup': st.median(m['speedup'] for m in metrics),
        'post_gates': st.median(m['post_gates'] for m in metrics),
        'post_qa': st.median(m['post_qa'] for m in metrics),
        'pipeline': st.median(m['pipeline'] for m in metrics),
        'baseline': st.median(m['baseline'] for m in metrics),
    }
    return agg


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    eval_data = read_json(EVAL_JSON) or {}
    mining = read_json(MINING_JSON)
    if not mining:
        return 0  # nothing to do

    # Baseline from fresh eval with current settings (multi-seed for stability)
    cur_env = load_current_settings()
    try:
        phi_cur = float(cur_env.get('QA_FP_FAMILY_TOL')) if cur_env.get('QA_FP_FAMILY_TOL') else None
    except Exception:
        phi_cur = None
    try:
        curv_cur = float(cur_env.get('QA_QE_CURV_WEIGHT')) if cur_env.get('QA_QE_CURV_WEIGHT') else None
    except Exception:
        curv_cur = None
    try:
        ideal_cur = float(cur_env.get('QA_QE_IDEAL_WEIGHT')) if cur_env.get('QA_QE_IDEAL_WEIGHT') else None
    except Exception:
        ideal_cur = None
    baseline_metrics = _eval_speed_with_env(phi_cur, curv_cur, ideal_cur)
    base_speed = float(baseline_metrics['speedup'])
    base_pg = float(baseline_metrics['post_gates'])
    base_pq = float(baseline_metrics['post_qa'])

    sug = mining.get('suggestions', {})
    phi_tol = float(sug.get('family', {}).get('phi_tol', 0.05)) if sug.get('family') else None
    curv_w = float(sug.get('curvature', {}).get('qe_weight', 0.25)) if sug.get('curvature') else None
    ideal_w = float(sug.get('ideal', {}).get('qe_weight', 0.0)) if sug.get('ideal') else None

    # Evaluate suggestions
    tested = _eval_speed_with_env(phi_tol, curv_w, ideal_w)

    # Decision thresholds (tunable via env)
    def _getf(key: str, default: float) -> float:
        try:
            return float(os.getenv(key, str(default)))
        except Exception:
            return default
    min_improve = _getf('QA_APPLY_MIN_IMPROVEMENT', 0.03)  # require +3% speedup
    min_pg_abs = _getf('QA_APPLY_MIN_POST_GATES', 5000.0)
    min_pq_abs = _getf('QA_APPLY_MIN_POST_QA', float(os.getenv('QA_APPLY_MIN_POST_QE', '3500.0')))
    min_pg_rel = _getf('QA_APPLY_MIN_POST_GATES_REL', 0.9)  # at least 90% of baseline gates
    min_pq_rel = _getf('QA_APPLY_MIN_POST_QA_REL', float(os.getenv('QA_APPLY_MIN_POST_QE_REL', '0.9')))     # at least 90% of baseline QA

    improves = tested['speedup'] >= base_speed * (1.0 + min_improve)
    healthy_abs = (tested['post_gates'] >= min_pg_abs) and (tested['post_qa'] >= min_pq_abs)
    healthy_rel = (tested['post_gates'] >= base_pg * min_pg_rel) and (tested['post_qa'] >= base_pq * min_pq_rel)
    accept = improves and healthy_abs and healthy_rel

    # If accepted, persist to .env
    applied_updates = {}
    if accept:
        updates = {}
        if phi_tol is not None:
            updates['QA_FP_ENABLE_FAMILY'] = '1'
            updates['QA_FP_FAMILY_TOL'] = str(phi_tol)
        if curv_w is not None:
            updates['QA_QA_CURV_WEIGHT'] = str(curv_w)
        if ideal_w is not None:
            updates['QA_QA_IDEAL_WEIGHT'] = str(ideal_w)
        # Keep wheel on by default
        updates['QA_FP_ENABLE_WHEEL'] = os.getenv('QA_FP_ENABLE_WHEEL', '1')
        update_env_file(ENV_PATH, updates)
        applied_updates = updates

    # Log decision
    entry = {
        'baseline': {
            'speedup': base_speed,
            'post_gates': base_pg,
            'post_qa': base_pq,
        },
        'tested': tested,
        'proposed': {
            'QA_FP_FAMILY_TOL': phi_tol,
            'QA_QA_CURV_WEIGHT': curv_w,
            'QA_QA_IDEAL_WEIGHT': ideal_w,
        },
        'decision': 'accepted' if accept else 'rejected',
        'criteria': {
            'min_improvement': min_improve,
            'min_post_gates_abs': min_pg_abs,
            'min_post_qa_abs': min_pq_abs,
            'min_post_gates_rel': min_pg_rel,
            'min_post_qa_rel': min_pq_rel,
        },
        'applied_updates': applied_updates,
    }
    try:
        if APPLY_LOG.exists():
            arr = json.loads(APPLY_LOG.read_text())
            if isinstance(arr, list):
                arr.append(entry)
            else:
                arr = [arr, entry]
        else:
            arr = [entry]
        APPLY_LOG.write_text(json.dumps(arr, indent=2))
    except Exception:
        # best-effort: write single entry
        APPLY_LOG.write_text(json.dumps([entry], indent=2))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
