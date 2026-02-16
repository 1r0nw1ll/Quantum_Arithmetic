#!/usr/bin/env python3
"""
Build a QA_RUN_ARTIFACT_BUNDLE.v1 certificate for a qa_lab run report.

Usage:
  python scripts/build_run_artifact_cert.py [--run-report <path>]

Output:
  Prints the absolute cert directory path on success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _shell(cmd: List[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(obj, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        handle.write("\n")


def _normalize_fail_record(item: Any, *, fallback_move: str) -> Dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    move = item.get("move")
    fail_type = item.get("fail_type")
    invariant_diff = item.get("invariant_diff")
    if not isinstance(move, str) or not move:
        return None
    if not isinstance(fail_type, str) or not fail_type:
        return None
    if not isinstance(invariant_diff, dict):
        return None
    return {
        "move": move or fallback_move,
        "fail_type": fail_type,
        "invariant_diff": invariant_diff,
    }


def _git_head(repo_root: Path) -> str:
    return _shell(["git", "rev-parse", "HEAD"], cwd=repo_root)


def _git_dirty(repo_root: Path) -> bool:
    status = _shell(["git", "status", "--porcelain"], cwd=repo_root)
    return bool(status.strip())


def _latest_run_report(logs_dir: Path) -> Path:
    reports = sorted(logs_dir.glob("run_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise RuntimeError(f"no run_report_*.json found under {logs_dir}")
    return reports[0]


def _make_manifest(cert_dir: Path, rel_paths: List[str], generated_utc: str) -> Dict[str, Any]:
    entries = []
    for rel in rel_paths:
        path = cert_dir / rel
        entries.append(
            {
                "id": rel,
                "sha256": _sha256_file(path),
                "canonicalization": "raw_bytes",
            }
        )
    material = {
        "schema_version": "QA_SHA256_MANIFEST.v1",
        "generated_utc": generated_utc,
        "entries": entries,
    }
    manifest_sha256 = hashlib.sha256(_canonical_bytes(material)).hexdigest()
    material["manifest_sha256"] = manifest_sha256
    return material


def build_run_artifact_cert(run_report: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    qa_lab_root = repo_root / "qa_lab"
    logs_dir = qa_lab_root / "logs"
    ingest_dir = repo_root / "ingestion candidates"

    run_report = run_report.resolve()
    if not run_report.exists():
        raise RuntimeError(f"run report not found: {run_report}")
    try:
        report_obj: Dict[str, Any] = json.loads(run_report.read_text(encoding="utf-8"))
    except Exception:
        report_obj = {}

    snapshot_src = logs_dir / "artifacts_snapshot.json"
    delta_src = logs_dir / "artifacts_delta.json"
    for required in (snapshot_src, delta_src):
        if not required.exists():
            raise RuntimeError(f"required artifact file missing: {required}")

    head_before = _git_head(repo_root)
    dirty_before = _git_dirty(repo_root)
    report_hash = _sha256_file(run_report)
    now = datetime.now(timezone.utc)
    run_ts = now.strftime("%Y%m%d-%H%M%S")
    run_id = f"{run_ts}-{head_before[:8]}-{report_hash[:12]}"

    cert_dir = qa_lab_root / "certs" / "run_artifact" / run_id
    witness_dir = cert_dir / "witness"
    witness_dir.mkdir(parents=True, exist_ok=True)

    run_report_dst = witness_dir / "run_report.json"
    snapshot_dst = witness_dir / "artifacts_snapshot.json"
    delta_dst = witness_dir / "artifacts_delta.json"

    shutil.copy2(run_report, run_report_dst)
    shutil.copy2(snapshot_src, snapshot_dst)
    shutil.copy2(delta_src, delta_dst)

    optional_exhibits: List[Dict[str, str]] = []
    for exhibit_name in ("INGESTION_INDEX.md", "INGESTION_JAN24_2026.md"):
        src = ingest_dir / exhibit_name
        if src.exists():
            dst = witness_dir / exhibit_name
            shutil.copy2(src, dst)
            optional_exhibits.append(
                {
                    "path": f"witness/{exhibit_name}",
                    "sha256": _sha256_file(dst),
                }
            )

    # Optional exhibits: QA Decision Certificate Spine hygiene reports (if present).
    # Convention: publish_run.py calls spine_hygiene_gate.py with ts matching run_report filename.
    ts = ""
    try:
        stem = run_report.stem
        if stem.startswith("run_report_"):
            ts = stem.split("run_report_", 1)[1]
    except Exception:
        ts = ""

    if ts:
        spine_json = logs_dir / f"spine_hygiene_{ts}.json"
        spine_out = logs_dir / f"spine_hygiene_{ts}.stdout.txt"
        spine_err = logs_dir / f"spine_hygiene_{ts}.stderr.txt"
        for src in (spine_json, spine_out, spine_err):
            if not src.exists():
                continue
            dst = witness_dir / src.name
            shutil.copy2(src, dst)
            optional_exhibits.append(
                {
                    "path": f"witness/{dst.name}",
                    "sha256": _sha256_file(dst),
                }
            )

    # Optional exhibits: EBM lane crosscheck report (if present).
    if ts:
        crosscheck_json = logs_dir / f"ebm_crosscheck_{ts}.json"
        if crosscheck_json.exists():
            dst = witness_dir / crosscheck_json.name
            shutil.copy2(crosscheck_json, dst)
            optional_exhibits.append(
                {
                    "path": f"witness/{dst.name}",
                    "sha256": _sha256_file(dst),
                }
            )

    # Optional exhibits: EBM cert lane artifacts under artifacts/certs/<run_id>/.
    certs_root = qa_lab_root / "artifacts" / "certs"
    cert_lane_warnings: List[Dict[str, Any]] = []
    if certs_root.exists():
        run_dirs = [path for path in certs_root.iterdir() if path.is_dir()]
        ebm_run_id = ""
        ebm_block = report_obj.get("ebm_certs")
        if isinstance(ebm_block, dict):
            run_id_value = ebm_block.get("run_id")
            if isinstance(run_id_value, str):
                candidate = run_id_value.strip()
                if candidate and "/" not in candidate and "\\" not in candidate:
                    ebm_run_id = candidate

        selected_run_dir: Path | None = None
        if ebm_run_id:
            run_dir = certs_root / ebm_run_id
            if run_dir.is_dir():
                selected_run_dir = run_dir
            else:
                cert_lane_warnings.append(
                    {
                        "move": "witness.ebm_certs",
                        "fail_type": "MISSING_DECLARED_EBM_CERT_RUN",
                        "invariant_diff": {
                            "declared_run_id": ebm_run_id,
                            "expected_path": str(run_dir),
                        },
                    }
                )
        elif run_dirs:
            selected_run_dir = max(run_dirs, key=lambda path: path.stat().st_mtime)
            cert_lane_warnings.append(
                {
                    "move": "witness.ebm_certs",
                    "fail_type": "NONDETERMINISTIC_EBM_CERT_RUN_SELECTION",
                    "invariant_diff": {
                        "reason": "run_report_missing_ebm_certs_run_id",
                        "selected_run_id": selected_run_dir.name,
                        "selection": "latest_mtime_fallback",
                    },
                }
            )

        if selected_run_dir is not None:
            for src in sorted(selected_run_dir.rglob("*")):
                if not src.is_file():
                    continue
                rel = src.relative_to(selected_run_dir)
                dst = witness_dir / "ebm_certs" / selected_run_dir.name / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                optional_exhibits.append(
                    {
                        "path": f"witness/{dst.relative_to(witness_dir).as_posix()}",
                        "sha256": _sha256_file(dst),
                    }
                )

    input_material = {
        "run_report_sha256": _sha256_file(run_report),
        "snapshot_sha256": _sha256_file(snapshot_src),
        "delta_sha256": _sha256_file(delta_src),
    }
    inputs_hash = hashlib.sha256(
        b"QA_RUN_ARTIFACT_BUNDLE.v1|inputs|" + _canonical_bytes(input_material)
    ).hexdigest()

    generated_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_paths = [
        "witness/run_report.json",
        "witness/artifacts_snapshot.json",
        "witness/artifacts_delta.json",
    ] + [item["path"] for item in optional_exhibits]
    witness_manifest = _make_manifest(cert_dir, manifest_paths, generated_utc)

    crosscheck_required = False
    crosscheck_validated = True
    crosscheck_records: List[Dict[str, Any]] = []
    crosscheck_block = report_obj.get("ebm_crosscheck")
    ebm_block = report_obj.get("ebm_certs")

    if isinstance(crosscheck_block, dict):
        mode_obj = crosscheck_block.get("mode")
        if isinstance(mode_obj, dict):
            crosscheck_required = mode_obj.get("required") is True
        crosscheck_validated = bool(crosscheck_block.get("validated"))
        raw_records = crosscheck_block.get("fail_records")
        if isinstance(raw_records, list):
            for item in raw_records:
                normalized = _normalize_fail_record(item, fallback_move="publish.ebm_crosscheck")
                if normalized is not None:
                    crosscheck_records.append(normalized)
                else:
                    crosscheck_records.append(
                        {
                            "move": "publish.ebm_crosscheck",
                            "fail_type": "EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                            "invariant_diff": {"error": "unparseable_fail_record"},
                        }
                    )
        elif raw_records is not None:
            crosscheck_records.append(
                {
                    "move": "publish.ebm_crosscheck",
                    "fail_type": "EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                    "invariant_diff": {"error": "fail_records_not_list"},
                }
            )
    elif isinstance(ebm_block, dict) and ebm_block.get("requested_verifier_bridge") is True:
        crosscheck_required = True
        crosscheck_validated = False
        crosscheck_records.append(
            {
                "move": "publish.ebm_crosscheck",
                "fail_type": "EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                "invariant_diff": {"error": "missing_ebm_crosscheck_block_when_required"},
            }
        )

    if crosscheck_required and not crosscheck_validated and not crosscheck_records:
        crosscheck_records.append(
            {
                "move": "publish.ebm_crosscheck",
                "fail_type": "EBM_CROSSCHECK_INVALID_REPORT_SHAPE",
                "invariant_diff": {"error": "crosscheck_required_but_not_validated"},
            }
        )

    result_status = "ok"
    fail_records: List[Dict[str, Any]] = cert_lane_warnings + crosscheck_records
    if crosscheck_required and not crosscheck_validated:
        result_status = "fail"
    elif fail_records:
        result_status = "partial"

    spine = {
        "schema_id": "QA_RUN_ARTIFACT_BUNDLE.v1",
        "version": 1,
        "run": {
            "run_id": run_id,
            "tool_id": "qa_lab.publish_run",
            "tool_version": "v1",
            "timestamp_utc": now.isoformat().replace("+00:00", "Z"),
            "inputs_hash": inputs_hash,
        },
        "git": {
            "head_before": head_before,
            "head_after": _git_head(repo_root),
            "dirty_before": dirty_before,
        },
        "artifacts": {
            "run_report": {
                "path": "witness/run_report.json",
                "sha256": _sha256_file(run_report_dst),
            },
            "snapshot": {
                "path": "witness/artifacts_snapshot.json",
                "sha256": _sha256_file(snapshot_dst),
            },
            "delta": {
                "path": "witness/artifacts_delta.json",
                "sha256": _sha256_file(delta_dst),
            },
            "optional_exhibits": optional_exhibits,
        },
        "result": {
            "status": result_status,
            "fail_records": fail_records,
        },
        "witness_manifest": witness_manifest,
    }

    _write_json(cert_dir / "spine.json", spine)
    return cert_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build QA run artifact certificate.")
    parser.add_argument("--run-report", default="", help="Path to run_report_*.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    logs_dir = repo_root / "qa_lab" / "logs"
    run_report = Path(args.run_report).resolve() if args.run_report else _latest_run_report(logs_dir)

    cert_dir = build_run_artifact_cert(run_report)
    print(str(cert_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
