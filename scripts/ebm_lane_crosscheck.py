#!/usr/bin/env python3
"""
ebm_lane_crosscheck.py

Cross-check QA Lab EBM lane cert coupling from a run report.

Enforces bridge -> navigation digest binding and (optionally) runs both family
validators against emitted cert files under qa_lab/artifacts/certs/<run_id>/.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_LAB_ROOT = REPO_ROOT / "qa_lab"
LOGS_DIR = QA_LAB_ROOT / "logs"
CERTS_ROOT = QA_LAB_ROOT / "artifacts" / "certs"
NAV_VALIDATOR = REPO_ROOT / "qa_ebm_navigation_cert" / "validator.py"
BRIDGE_VALIDATOR = REPO_ROOT / "qa_ebm_verifier_bridge_cert" / "validator.py"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_safe_token(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


def _is_under(path: Path, root: Path) -> bool:
    p = path.resolve()
    r = root.resolve()
    return p == r or r in p.parents


def _run_validator(validator: Path, cert: Path) -> Tuple[bool, str, int]:
    if not validator.exists():
        return False, f"validator_missing:{validator}", 127
    proc = subprocess.run(
        [sys.executable, str(validator), str(cert), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    output = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, output[:4000], int(proc.returncode)


def _fail(
    fail_records: List[Dict[str, Any]],
    *,
    fail_type: str,
    run_id: str,
    case_name: str,
    nav_path: Optional[Path] = None,
    bridge_path: Optional[Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    invariant_diff: Dict[str, Any] = {
        "run_id": run_id,
        "case_name": case_name,
        "nav_path": str(nav_path) if nav_path is not None else None,
        "bridge_path": str(bridge_path) if bridge_path is not None else None,
    }
    if extra:
        invariant_diff.update(extra)
    fail_records.append(
        {
            "move": "publish.ebm_crosscheck",
            "fail_type": fail_type,
            "invariant_diff": invariant_diff,
        }
    )


def run_crosscheck(
    *,
    run_report: Path,
    ts: str,
    run_validators: bool,
) -> Dict[str, Any]:
    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fail_records: List[Dict[str, Any]] = []
    checked_pairs = 0

    try:
        report_obj = json.loads(run_report.read_text(encoding="utf-8"))
    except Exception as exc:
        status = {
            "validated": False,
            "mode": {"required": False},
            "checked_pairs": 0,
            "fail_records": [
                {
                    "move": "publish.ebm_crosscheck",
                    "fail_type": "EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                    "invariant_diff": {
                        "run_id": "",
                        "case_name": "",
                        "nav_path": None,
                        "bridge_path": None,
                        "error": f"run_report_unreadable:{type(exc).__name__}:{exc}",
                    },
                }
            ],
            "run_report": str(run_report),
            "started_utc": started_utc,
        }
        _write_json(LOGS_DIR / f"ebm_crosscheck_{ts}.json", status)
        return status

    if not isinstance(report_obj, dict):
        report_obj = {}

    ebm = report_obj.get("ebm_certs")
    if not isinstance(ebm, dict):
        ebm = {}
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
            run_id="",
            case_name="",
            extra={"error": "ebm_certs_block_missing_or_not_object"},
        )

    required = ebm.get("requested_verifier_bridge") is True
    run_id_obj = ebm.get("run_id")
    run_id = run_id_obj.strip() if isinstance(run_id_obj, str) else ""
    if not run_id:
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_MISSING_RUN_ID",
            run_id=run_id,
            case_name="",
            extra={"requested_verifier_bridge": bool(required)},
        )
    elif not _is_safe_token(run_id):
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
            run_id=run_id,
            case_name="",
            extra={"error": "unsafe_run_id_token"},
        )

    cases_obj = ebm.get("cases")
    cases: Dict[str, Any]
    if isinstance(cases_obj, dict):
        cases = cases_obj
    else:
        cases = {}
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
            run_id=run_id,
            case_name="",
            extra={"error": "ebm_certs.cases_missing_or_not_object"},
        )
    if len(cases) == 0:
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
            run_id=run_id,
            case_name="",
            extra={"error": "ebm_certs.cases_empty"},
        )

    run_dir = CERTS_ROOT / run_id if run_id else CERTS_ROOT / "__missing__"
    if run_id and not _is_under(run_dir, CERTS_ROOT):
        _fail(
            fail_records,
            fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
            run_id=run_id,
            case_name="",
            extra={"error": "run_dir_outside_certs_root"},
        )

    for case_name in sorted(cases.keys()):
        case_obj = cases.get(case_name)
        if not isinstance(case_name, str) or not _is_safe_token(case_name):
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=str(case_name),
                extra={"error": "unsafe_case_name_token"},
            )
            continue
        if not isinstance(case_obj, dict):
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=case_name,
                extra={"error": "case_block_not_object"},
            )
            continue

        nav_path = run_dir / f"ebm_nav_{run_id}_{case_name}.json"
        bridge_path = run_dir / f"ebm_bridge_{run_id}_{case_name}.json"
        if not _is_under(nav_path, CERTS_ROOT) or not _is_under(bridge_path, CERTS_ROOT):
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
                extra={"error": "cert_path_outside_certs_root"},
            )
            continue

        if not nav_path.exists():
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_MISSING_NAV_CERT",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
            )
            continue

        if required and not bridge_path.exists():
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_MISSING_BRIDGE_CERT",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
            )
            continue

        try:
            nav_obj = json.loads(nav_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path if bridge_path.exists() else None,
                extra={"error": f"nav_read_failed:{type(exc).__name__}:{exc}"},
            )
            continue

        if run_validators:
            nav_ok, nav_msg, nav_rc = _run_validator(NAV_VALIDATOR, nav_path)
            if not nav_ok:
                _fail(
                    fail_records,
                    fail_type="EBM_CROSSCHECK_VALIDATOR_FAIL",
                    run_id=run_id,
                    case_name=case_name,
                    nav_path=nav_path,
                    bridge_path=bridge_path if bridge_path.exists() else None,
                    extra={
                        "cert_kind": "navigation",
                        "returncode": nav_rc,
                        "validator_output": nav_msg,
                    },
                )

        if not bridge_path.exists():
            continue

        try:
            bridge_obj = json.loads(bridge_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
                extra={"error": f"bridge_read_failed:{type(exc).__name__}:{exc}"},
            )
            continue

        nav_digest = nav_obj.get("digests", {}).get("canonical_sha256")
        bridge_cert_digest = bridge_obj.get("digests", {}).get("canonical_sha256")

        # New coupling direction (preferred): navigation.outcome.verifier_bridge_ref -> bridge digests.canonical_sha256
        nav_outcome = nav_obj.get("trace", {}).get("outcome", {})
        nav_bridge_ref = nav_outcome.get("verifier_bridge_ref") if isinstance(nav_outcome, dict) else None
        nav_bridge_sha = nav_bridge_ref.get("sha256") if isinstance(nav_bridge_ref, dict) else None
        nav_bridge_name = nav_bridge_ref.get("ref_name") if isinstance(nav_bridge_ref, dict) else None
        expected_bridge_ref_name = str(bridge_path.relative_to(REPO_ROOT).as_posix())

        # Legacy coupling direction: bridge.subject.navigation_cert_ref -> nav digests.canonical_sha256
        legacy_bridge_nav_sha = bridge_obj.get("subject", {}).get("navigation_cert_ref", {}).get("sha256")

        digest_ok = False
        mode = "none"
        if (
            isinstance(nav_bridge_sha, str)
            and isinstance(bridge_cert_digest, str)
            and nav_bridge_sha == bridge_cert_digest
        ):
            digest_ok = True
            mode = "nav_to_bridge"
        elif (
            isinstance(legacy_bridge_nav_sha, str)
            and isinstance(nav_digest, str)
            and legacy_bridge_nav_sha == nav_digest
        ):
            digest_ok = True
            mode = "bridge_to_nav_legacy"

        if not digest_ok:
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_DIGEST_MISMATCH",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
                extra={
                    "nav_digest": nav_digest,
                    "nav_verifier_bridge_sha256": nav_bridge_sha,
                    "nav_verifier_bridge_ref_name": nav_bridge_name,
                    "bridge_cert_digest": bridge_cert_digest,
                    "bridge_subject_navigation_sha256_legacy": legacy_bridge_nav_sha,
                },
            )
        else:
            checked_pairs += 1

        if isinstance(nav_bridge_name, str) and nav_bridge_name != expected_bridge_ref_name:
            _fail(
                fail_records,
                fail_type="EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                run_id=run_id,
                case_name=case_name,
                nav_path=nav_path,
                bridge_path=bridge_path,
                extra={
                    "error": "nav_verifier_bridge_ref_name_mismatch",
                    "expected": expected_bridge_ref_name,
                    "got": nav_bridge_name,
                    "mode": mode,
                },
            )

        if run_validators:
            bridge_ok, bridge_msg, bridge_rc = _run_validator(BRIDGE_VALIDATOR, bridge_path)
            if not bridge_ok:
                _fail(
                    fail_records,
                    fail_type="EBM_CROSSCHECK_VALIDATOR_FAIL",
                    run_id=run_id,
                    case_name=case_name,
                    nav_path=nav_path,
                    bridge_path=bridge_path,
                    extra={
                        "cert_kind": "bridge",
                        "returncode": bridge_rc,
                        "validator_output": bridge_msg,
                    },
                )

    validated = len(fail_records) == 0
    status = {
        "validated": validated,
        "mode": {"required": bool(required)},
        "checked_pairs": checked_pairs,
        "fail_records": fail_records,
        "run_report": str(run_report),
        "run_id": run_id,
        "started_utc": started_utc,
    }
    _write_json(LOGS_DIR / f"ebm_crosscheck_{ts}.json", status)
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-check EBM lane bridge->nav coupling for QA Lab publish.")
    ap.add_argument("--run-report", required=True, help="Path to run_report_*.json")
    ap.add_argument("--ts", default="", help="Timestamp tag used for output filenames")
    ap.add_argument("--no-validators", action="store_true", help="Skip family validator subprocess checks")
    args = ap.parse_args()

    run_report = Path(args.run_report).resolve()
    ts = args.ts.strip()
    if not ts:
        stem = run_report.stem
        if stem.startswith("run_report_"):
            ts = stem.split("run_report_", 1)[1]
    if not ts:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    status = run_crosscheck(
        run_report=run_report,
        ts=ts,
        run_validators=not args.no_validators,
    )
    print(json.dumps(status, sort_keys=True))
    required = bool(status.get("mode", {}).get("required"))
    return 1 if required and not status.get("validated") else 0


if __name__ == "__main__":
    raise SystemExit(main())
