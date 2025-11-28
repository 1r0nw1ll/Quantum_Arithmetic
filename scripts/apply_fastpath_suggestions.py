#!/usr/bin/env python3
"""
apply_fastpath_suggestions.py - Read mining suggestions and tentatively apply.

Policy:
  - Read artifacts/evals/fastpath_mining.json
  - Build proposed env overrides (wheel, family phi_tol, curvature/ideal weights)
  - Read previous fastpath_eval.json (prev_speedup)
  - Run qa_fast_eval.py once with proposed env overrides (without persisting .env)
  - If new_speedup >= prev_speedup and survivors healthy (post_gates>0, post_qe>0),
    persist changes to qa_lab/.env; else keep existing .env and re-run eval with
    original env to restore baseline metrics.
  - Write artifacts/evals/fastpath_apply_log.json with decision and metrics.

This script is non-interactive and safe to run each metrics pass.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path('.')
EVALS = ROOT / 'artifacts' / 'evals'
MINING = EVALS / 'fastpath_mining.json'
FAST_JSON = EVALS / 'fastpath_eval.json'
ENV_FILE = ROOT / 'qa_lab' / '.env'
APPLY_LOG = EVALS / 'fastpath_apply_log.json'


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def run_eval_with_env(env_overrides: dict[str, str]) -> dict:
    env = os.environ.copy()
    env.update(env_overrides)
    subprocess.run(['python3', 'qa_lab/qa_fast_eval.py'], check=False, env=env)
    return load_json(FAST_JSON)


def persist_env(overrides: dict[str, str]) -> None:
    # Append/update .env with overrides (simple replace per key)
    lines = []
    existing = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                lines.append(line)
                continue
            k, v = line.split('=', 1)
            existing[k.strip()] = v.strip()
    existing.update(overrides)
    out_lines = ["# QA Lab Fast-Path Defaults (auto-applied)"]
    for k, v in existing.items():
        if k:
            out_lines.append(f"{k}={v}")
    ENV_FILE.write_text('\n'.join(out_lines) + '\n')


def main():
    EVALS.mkdir(parents=True, exist_ok=True)
    mining = load_json(MINING)
    prev = load_json(FAST_JSON)
    prev_speed = float(prev.get('default', {}).get('speedup_vs_baseline', 0.0))

    # Build proposed overrides
    sug = mining.get('suggestions', {})
    overrides = {}
    if sug.get('wheel', {}).get('enable', True):
        overrides['QA_FP_ENABLE_WHEEL'] = '1'
    fam = sug.get('family', {})
    if fam.get('enable', True):
        overrides['QA_FP_ENABLE_FAMILY'] = '1'
        overrides['QA_FP_FAMILY_TOL'] = str(fam.get('phi_tol', 0.05))
    curv_w = sug.get('curvature', {}).get('qe_weight')
    if curv_w is not None:
        overrides['QA_QA_CURV_WEIGHT'] = str(curv_w)
    ideal_w = sug.get('ideal', {}).get('qe_weight')
    if ideal_w is not None:
        overrides['QA_QA_IDEAL_WEIGHT'] = str(ideal_w)
        # Set a light ideal min gate when ideal feature > 0
        overrides.setdefault('QA_FP_IDEAL_MIN', '0.10')

    # Run eval with proposed overrides
    new = run_eval_with_env(overrides)
    new_default = new.get('default', {})
    new_speed = float(new_default.get('speedup_vs_baseline', 0.0))
    post_gates = int(new_default.get('post_gates', 0))
    post_qa = int(new_default.get('post_qa', new_default.get('post_qe', 0)))

    decision = 'accepted' if (new_speed >= prev_speed and post_gates > 0 and post_qa > 0) else 'rejected'

    if decision == 'accepted':
        persist_env(overrides)
    else:
        # Re-run eval with original env to restore metrics
        run_eval_with_env({})

    APPLY_LOG.write_text(json.dumps({
        'decision': decision,
        'prev_speed': prev_speed,
        'new_speed': new_speed,
        'post_gates': post_gates,
        'post_qa': post_qa,
        'overrides': overrides,
    }, indent=2))


if __name__ == '__main__':
    main()
