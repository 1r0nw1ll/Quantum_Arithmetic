#!/usr/bin/env python3
"""
spine_hygiene_gate.py

QA Lab hygiene gate for the QA Decision Certificate Spine.

Purpose:
- Run the repo-level meta-validator (`qa_alphageometry_ptolemy/qa_meta_validator.py`)
  in strict mode and record a deterministic, hash-bound report under `qa_lab/logs/`.
- Emit a small JSON status blob suitable for embedding into QA Lab run reports.

This is a lab-level integration point: it does not generate new certs; it certifies
that the shipped certificate families + docs + policy guards are currently passing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gate(ts: str, *, fast: bool, strict: bool, timeout_sec: int) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    qa_lab_root = repo_root / "qa_lab"
    logs_dir = qa_lab_root / "logs"

    meta = repo_root / "qa_alphageometry_ptolemy" / "qa_meta_validator.py"
    if not meta.exists():
        return {
            "validated": False,
            "error": f"meta_validator_not_found:{meta}",
        }

    cmd = [sys.executable, str(meta)]
    if fast:
        cmd.append("--fast")
    if strict:
        cmd.append("--strict")

    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "validated": False,
            "error": "meta_validator_timeout",
            "command": cmd,
            "started_utc": started_utc,
            "timeout_sec": timeout_sec,
        }

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    stdout_sha256 = _sha256_text(stdout)
    stderr_sha256 = _sha256_text(stderr)

    stdout_path = logs_dir / f"spine_hygiene_{ts}.stdout.txt"
    stderr_path = logs_dir / f"spine_hygiene_{ts}.stderr.txt"
    _write_text(stdout_path, stdout)
    if stderr.strip():
        _write_text(stderr_path, stderr)
        stderr_rel: Optional[str] = str(stderr_path.relative_to(qa_lab_root))
    else:
        stderr_rel = None

    # Lightweight success heuristic: meta-validator is exit-code authoritative.
    validated = proc.returncode == 0

    status = {
        "validated": validated,
        "command": cmd,
        "mode": {
            "fast": fast,
            "strict": strict,
        },
        "started_utc": started_utc,
        "returncode": proc.returncode,
        "stdout": {
            "path": str(stdout_path.relative_to(qa_lab_root)),
            "sha256": stdout_sha256,
        },
        "stderr": {
            "path": stderr_rel,
            "sha256": stderr_sha256 if stderr_rel else None,
        },
        "summary": {
            "stdout_head": stdout.strip().splitlines()[:5],
            "tail_marker": "[PASS]" if "[PASS]" in stdout else None,
        },
    }

    _write_json(logs_dir / f"spine_hygiene_{ts}.json", status)
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="QA Lab gate: QA Decision Certificate Spine hygiene")
    ap.add_argument("--ts", required=False, default="", help="Timestamp tag used for output filenames")
    ap.add_argument("--fast", action="store_true", help="Run meta-validator in fast mode (manifest integrity only)")
    ap.add_argument("--no-strict", action="store_true", help="Disable strict policy guards")
    ap.add_argument("--timeout-sec", type=int, default=120, help="Timeout seconds for meta-validator sweep")
    args = ap.parse_args()

    ts = args.ts.strip() or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    strict = not args.no_strict

    status = run_gate(ts, fast=bool(args.fast), strict=strict, timeout_sec=int(args.timeout_sec))
    print(json.dumps(status, sort_keys=True))
    return 0 if status.get("validated") else 1


if __name__ == "__main__":
    raise SystemExit(main())
