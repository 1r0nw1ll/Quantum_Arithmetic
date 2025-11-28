#!/usr/bin/env python3
"""
daily_summary.py - Generate a high-level daily summary for QA Lab.

Reads key evaluation artifacts (fast-path eval) and emits a concise summary to:
  - artifacts/evals/daily_summary_YYYY-MM-DD.txt
  - artifacts/evals/daily_summary_latest.txt (overwrites)

If QA_COLLAB_LIVE=1 and a broadcast tool is available, also posts a brief
notification so researchers can find the latest results without digging.

Idempotent: skips creating a new daily file if one already exists for today,
unless QA_FORCE_SUMMARY=1 is set.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import json


ART_EVALS = Path('artifacts/evals')
FAST_TXT = ART_EVALS / 'fastpath_eval.txt'
FAST_JSON = ART_EVALS / 'fastpath_eval.json'


def read_fast_eval() -> dict:
    data = {}
    if FAST_JSON.exists():
        try:
            data = json.loads(FAST_JSON.read_text())
        except Exception:
            data = {}
    return data


def format_summary(fast: dict) -> str:
    lines = []
    today = datetime.now().strftime('%Y-%m-%d')
    lines.append(f"QA Lab Daily Summary — {today}")
    lines.append("=")
    if not fast:
        lines.append("No fast-path evaluation found.")
        return '\n'.join(lines) + '\n'

    lines.append("Fast-Path Evaluation (gates → QA → E8)")
    for key in ("default", "numpy_pref", "rust_disabled"):
        if key in fast:
            v = fast[key]
            post_stage = v.get('post_qa', v.get('post_qe'))
            qa_topk = v.get('qa_topk', v.get('qe_topk'))
            lines.append(
                f"- {key}: kept={v.get('kept')}/{v.get('n')} gates={v.get('post_gates')} qa={post_stage} "
                f"pipeline={v.get('time_sec_pipeline'):.3f}s baseline={v.get('time_sec_baseline'):.3f}s "
                f"speedup={v.get('speedup_vs_baseline'):.2f}x roots={v.get('roots_used')}"
            )
    lines.append("")
    # Trend length if available
    trends_path = ART_EVALS / 'fastpath_trends.json'
    if trends_path.exists():
        try:
            arr = json.loads(trends_path.read_text())
            if isinstance(arr, list):
                lines.append(f"Trend entries: {len(arr)}")
        except Exception:
            pass
    lines.append(f"See: {FAST_TXT}")

    # Optional: include vault mining suggestions
    mining_json = ART_EVALS / 'fastpath_mining.json'
    if mining_json.exists():
        try:
            mining = json.loads(mining_json.read_text())
            sug = mining.get('suggestions', {})
            lines.append('')
            lines.append('Vault Mining Suggestions:')
            lines.append(f"- Wheel: enable={sug.get('wheel',{}).get('enable')}")
            fam = sug.get('family', {})
            lines.append(f"- Family: enable={fam.get('enable')} phi_tol={fam.get('phi_tol')}")
            lines.append(f"- Curv weight: {sug.get('curvature',{}).get('qe_weight')}")
            lines.append(f"- Ideal weight: {sug.get('ideal',{}).get('qe_weight')}")
        except Exception:
            pass

    # Current fast-path settings (prefer persisted .env values when present)
    lines.append('')
    lines.append('Fast-Path Settings (current):')
    env_kv = {}
    try:
        env_path = Path('.env')
        if env_path.exists():
            for raw in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                env_kv[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    def getv(name: str, default: str = '') -> str:
        return env_kv.get(name, os.getenv(name, default))
    # Display normalized QA settings; for weights prefer QA_QA_* but fall back to legacy QA_QE_*
    normalized = {
        'QA_FP_ENABLE_WHEEL': getv('QA_FP_ENABLE_WHEEL', ''),
        'QA_FP_ENABLE_FAMILY': getv('QA_FP_ENABLE_FAMILY', ''),
        'QA_FP_FAMILY_TOL': getv('QA_FP_FAMILY_TOL', ''),
        'QA_FP_POS_MIN': getv('QA_FP_POS_MIN', ''),
        'QA_QA_CURV_WEIGHT': getv('QA_QA_CURV_WEIGHT', getv('QA_QE_CURV_WEIGHT', '')),
        'QA_QA_IDEAL_WEIGHT': getv('QA_QA_IDEAL_WEIGHT', getv('QA_QE_IDEAL_WEIGHT', '')),
        'QA_FP_IDEAL_MIN': getv('QA_FP_IDEAL_MIN', ''),
    }
    for k, v in normalized.items():
        if v != '':
            lines.append(f"- {k}={v}")
    return '\n'.join(lines) + '\n'


def maybe_broadcast(msg: str) -> None:
    # Try collab broadcast if enabled
    if os.getenv('QA_COLLAB_LIVE', '0') != '1':
        return
    # Use collab_broadcast if present, else external_ack.py
    if Path('collab_broadcast').exists():
        cmd = ['bash', '-lc', f'./collab_broadcast << EOF\n{msg}\nEOF']
    elif Path('scripts/external_ack.py').exists():
        cmd = ['python3', 'scripts/external_ack.py']
    else:
        return
    try:
        import subprocess
        subprocess.run(cmd, check=False)
    except Exception:
        pass


def main():
    # Best-effort: load .env so settings are visible when running under make -C qa_lab
    try:
        env_path = Path('.env')
        if env_path.exists():
            for raw in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass
    ART_EVALS.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    out_daily = ART_EVALS / f'daily_summary_{today}.txt'
    out_latest = ART_EVALS / 'daily_summary_latest.txt'

    if out_daily.exists() and os.getenv('QA_FORCE_SUMMARY', '0') != '1':
        return

    fast = read_fast_eval()
    summary = format_summary(fast)
    out_daily.write_text(summary)
    out_latest.write_text(summary)

    # Optional broadcast
    maybe_broadcast(summary)


if __name__ == '__main__':
    main()
