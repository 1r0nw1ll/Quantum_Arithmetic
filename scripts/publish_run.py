#!/usr/bin/env python3
"""
Publish run artifacts:
 - Package artifacts/ and qa_data/ into releases/run-<timestamp>.tar.gz
 - Generate a concise run report with task and artifact stats
 - Append a publish.run_report event to logs/collab_events.jsonl
"""

from __future__ import annotations

import tarfile
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

BASE = Path(__file__).resolve().parents[1]
RELEASES = BASE / 'releases'
RELEASES.mkdir(exist_ok=True)
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)

REPO_ROOT = BASE.parent
CERT_BUILDER = BASE / 'scripts' / 'build_run_artifact_cert.py'
CERT_VALIDATOR = REPO_ROOT / 'qa_alphageometry_ptolemy' / 'qa_fst' / 'validators' / 'qa_run_artifact_validate.py'
CERT_SCHEMAS = REPO_ROOT / 'qa_alphageometry_ptolemy' / 'qa_fst' / 'schemas'
SPINE_HYGIENE_GATE = BASE / 'scripts' / 'spine_hygiene_gate.py'
EBM_CROSSCHECK_GATE = BASE / 'scripts' / 'ebm_lane_crosscheck.py'
FASTPATH_EVAL = BASE / 'artifacts' / 'evals' / 'fastpath_eval.json'


def safe_count_completed() -> int:
    d = BASE / 'tasks' / 'completed'
    if not d.exists():
        return 0
    return sum(1 for _ in d.glob('*.yaml'))


def active_state_counts() -> Dict[str, int]:
    d = BASE / 'tasks' / 'active'
    counts: Dict[str, int] = {}
    if not d.exists():
        return counts
    for p in d.glob('*.yaml'):
        try:
            for line in p.read_text(encoding='utf-8').splitlines():
                if line.strip().startswith('state:'):
                    st = line.split(':', 1)[1].strip()
                    counts[st] = counts.get(st, 0) + 1
                    break
        except Exception:
            continue
    return counts


def read_delta() -> Dict[str, Any]:
    f = LOGS / 'artifacts_delta.json'
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}
    return {}


def read_ebm_certs() -> Dict[str, Any]:
    if not FASTPATH_EVAL.exists():
        return {}
    try:
        obj = json.loads(FASTPATH_EVAL.read_text(encoding='utf-8'))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    ebm = obj.get('ebm_certs')
    if not isinstance(ebm, dict):
        return {}

    out: Dict[str, Any] = {'source': str(FASTPATH_EVAL.relative_to(BASE))}
    for key in ('enabled', 'run_id', 'requested_verifier_bridge', 'accepted_by_verifier'):
        if key in ebm:
            out[key] = ebm[key]
    cases = ebm.get('cases')
    if isinstance(cases, dict):
        out['cases'] = cases
    return out


def make_archive(ts: str) -> str:
    out = RELEASES / f"run-{ts}.tar.gz"
    with tarfile.open(out, mode='w:gz') as tar:
        for name in ('artifacts', 'qa_data'):
            p = BASE / name
            if p.exists():
                tar.add(str(p), arcname=name)
    return str(out)


def build_and_validate_cert(report_file: Path) -> Dict[str, Any]:
    """
    Build QA_RUN_ARTIFACT_BUNDLE.v1 for report_file and validate it.

    Returns a status dictionary suitable for embedding in the run report.
    """
    if not CERT_BUILDER.exists():
        return {
            'validated': False,
            'error': f'cert_builder_not_found:{CERT_BUILDER}',
        }
    if not CERT_VALIDATOR.exists():
        return {
            'validated': False,
            'error': f'cert_validator_not_found:{CERT_VALIDATOR}',
        }
    if not CERT_SCHEMAS.exists():
        return {
            'validated': False,
            'error': f'cert_schema_dir_not_found:{CERT_SCHEMAS}',
        }

    build_proc = subprocess.run(
        [sys.executable, str(CERT_BUILDER), '--run-report', str(report_file)],
        capture_output=True,
        text=True,
    )
    if build_proc.returncode != 0:
        return {
            'validated': False,
            'error': 'cert_build_failed',
            'stderr': build_proc.stderr.strip(),
        }

    cert_dir = build_proc.stdout.strip().splitlines()[-1] if build_proc.stdout.strip() else ''
    if not cert_dir:
        return {
            'validated': False,
            'error': 'cert_build_failed_empty_output',
        }

    validate_proc = subprocess.run(
        [sys.executable, str(CERT_VALIDATOR), cert_dir, str(CERT_SCHEMAS)],
        capture_output=True,
        text=True,
    )
    if validate_proc.returncode != 0:
        return {
            'validated': False,
            'cert_dir': cert_dir,
            'error': 'cert_validation_failed',
            'stderr': validate_proc.stderr.strip(),
        }

    return {
        'validated': True,
        'cert_dir': cert_dir,
        'validator_stdout': validate_proc.stdout.strip(),
    }


def run_spine_hygiene_gate(ts: str) -> Dict[str, Any]:
    """
    Run repo-level QA meta-validator (Decision Certificate Spine) in strict mode and
    record a hash-bound report under qa_lab/logs/.
    """
    if not SPINE_HYGIENE_GATE.exists():
        return {
            "validated": False,
            "error": f"spine_hygiene_gate_not_found:{SPINE_HYGIENE_GATE}",
        }

    proc = subprocess.run(
        [sys.executable, str(SPINE_HYGIENE_GATE), "--ts", ts],
        capture_output=True,
        text=True,
    )
    # Script prints JSON status to stdout on both success/failure.
    try:
        status = json.loads(proc.stdout.strip() or "{}")
    except Exception:
        status = {
            "validated": False,
            "error": "spine_hygiene_gate_invalid_json",
            "stdout": (proc.stdout or "").strip()[:500],
            "stderr": (proc.stderr or "").strip()[:500],
            "returncode": proc.returncode,
        }
    # Prefer structured field from the gate, but keep subprocess returncode too.
    status.setdefault("returncode", proc.returncode)
    status["validated"] = bool(status.get("validated")) and proc.returncode == 0
    return status


def run_ebm_lane_crosscheck(ts: str, report_file: Path) -> Dict[str, Any]:
    """
    Run EBM lane cross-check (bridge->nav digest coupling + validator checks).
    """
    if not EBM_CROSSCHECK_GATE.exists():
        return {
            "validated": False,
            "mode": {"required": False},
            "error": f"ebm_crosscheck_gate_not_found:{EBM_CROSSCHECK_GATE}",
        }

    proc = subprocess.run(
        [sys.executable, str(EBM_CROSSCHECK_GATE), "--run-report", str(report_file), "--ts", ts],
        capture_output=True,
        text=True,
    )
    try:
        status = json.loads(proc.stdout.strip() or "{}")
    except Exception:
        status = {
            "validated": False,
            "mode": {"required": False},
            "error": "ebm_crosscheck_invalid_json",
            "stdout": (proc.stdout or "").strip()[:500],
            "stderr": (proc.stderr or "").strip()[:500],
            "returncode": proc.returncode,
        }
    status.setdefault("returncode", proc.returncode)
    status["validated"] = bool(status.get("validated"))
    return status


def main() -> int:
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_path = make_archive(ts)

    report = {
        'timestamp': datetime.now().isoformat(),
        'completed_count': safe_count_completed(),
        'active_state_counts': active_state_counts(),
        'artifact_archive': archive_path,
        'artifact_delta': read_delta(),
        'ebm_certs': read_ebm_certs(),
    }

    # Persist run report
    report_file = LOGS / f'run_report_{ts}.json'
    report_file.write_text(json.dumps(report, indent=2))

    # QA Decision Certificate Spine hygiene gate (strict)
    spine_status = run_spine_hygiene_gate(ts)
    report['spine_hygiene'] = spine_status
    report_file.write_text(json.dumps(report, indent=2))

    # EBM lane cross-check (hard gate only when verifier bridge was requested).
    ebm_crosscheck = run_ebm_lane_crosscheck(ts, report_file)
    report['ebm_crosscheck'] = ebm_crosscheck
    report_file.write_text(json.dumps(report, indent=2))

    # Build and validate run artifact certificate (hard gate for downstream push)
    cert_status = build_and_validate_cert(report_file)
    report['run_artifact_cert'] = cert_status
    report_file.write_text(json.dumps(report, indent=2))

    # Append event line
    evt = {
        'event_type': 'publish.run_report',
        'data': report,
        'timestamp': report['timestamp'],
        'source': 'qa_lab',
    }
    with open(LOGS / 'collab_events.jsonl', 'a') as f:
        f.write(json.dumps(evt) + '\n')

    requested_bridge = report.get('ebm_certs', {}).get('requested_verifier_bridge') is True
    crosscheck_required_fail = bool(requested_bridge) and not ebm_crosscheck.get('validated', False)

    if not spine_status.get('validated', False) or not cert_status.get('validated', False) or crosscheck_required_fail:
        print(
            json.dumps(
                {
                    'status': 'fail',
                    'archive': archive_path,
                    'report': str(report_file),
                    'spine_hygiene': spine_status,
                    'ebm_crosscheck': ebm_crosscheck,
                    'cert': cert_status,
                }
            )
        )
        return 1

    print(json.dumps({
        'status': 'ok',
        'archive': archive_path,
        'report': str(report_file),
        'spine_hygiene': spine_status,
        'ebm_crosscheck': ebm_crosscheck,
        'cert': cert_status
    }))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
