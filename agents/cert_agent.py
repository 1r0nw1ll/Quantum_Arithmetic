"""
qa_lab.agents.cert_agent
========================
CertAgent — validates cert artifacts through the QA cert ecosystem.

This is the first concrete micro-agent in QA Lab. Its job:
  1. Accept a CERTIFY task pointing to a cert family validator
  2. Run the validator with --self-test
  3. Return a structured result that the kernel can verify and learn from

The CertAgent is the governance layer made autonomous: instead of a human
manually running `python qa_meta_validator.py`, the kernel dispatches a
CERTIFY task to the CertAgent, which runs the check and reports back.

CertAgent can also:
  - Run the full meta-validator (128/128 sweep)
  - Validate a single cert fixture against a named validator
  - Report which gates failed and why
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import QAAgent

_AGENTS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _AGENTS_DIR.parent
_REPO_ROOT = _QA_LAB_DIR.parent


class CertAgent(QAAgent):
    """Validates cert artifacts against the QA cert ecosystem.

    Capabilities: CERTIFY
    Cert family:  (governance agent — does not itself produce cert families)
    """

    capabilities = ["certify"]
    cert_family = None  # governance agent, not a research artifact

    def __init__(
        self,
        repo_root: Optional[str | Path] = None,
        modulus: int = 9,
    ):
        super().__init__(name="cert_agent", modulus=modulus)
        self.repo_root = Path(repo_root) if repo_root else _REPO_ROOT

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        """Execute a CERTIFY task.

        Task inputs may contain:
          validator_path  — path to a specific validator (relative to repo root)
          cert_path       — path to a specific fixture JSON to validate
          run_meta        — if True, run the full meta-validator sweep
          family_name     — human label for logging

        Returns dict with:
          ok              — bool
          validator_path  — path used (for kernel VERIFY step)
          exit_code       — subprocess return code
          stdout          — validator stdout (trimmed)
          stderr          — validator stderr (trimmed)
          gate_reached    — highest gate passed
          fail_type       — first FAIL type seen, if any
        """
        inputs = task.inputs if hasattr(task, "inputs") else {}

        # Route: full meta-validator sweep vs single validator
        if inputs.get("run_meta", False):
            return self._run_meta_validator()

        validator_path = inputs.get("validator_path")
        cert_path = inputs.get("cert_path")

        if validator_path:
            return self._run_single_validator(
                validator_path=validator_path,
                cert_path=cert_path,
                family_name=inputs.get("family_name", ""),
            )

        return {
            "ok": False,
            "error": "CERTIFY task requires 'validator_path' or 'run_meta=True' in inputs",
        }

    # ------------------------------------------------------------------
    # Meta-validator sweep
    # ------------------------------------------------------------------

    def _run_meta_validator(self) -> Dict[str, Any]:
        """Run the full meta-validator and parse results."""
        meta_path = self.repo_root / "qa_alphageometry_ptolemy" / "qa_meta_validator.py"
        if not meta_path.exists():
            return {"ok": False, "error": f"meta-validator not found: {meta_path}"}

        proc = self._run(str(meta_path), [], timeout=300)
        ok = proc.returncode == 0
        # Parse pass count from output
        pass_count = self._extract_pass_count(proc.stdout)

        return {
            "ok": ok,
            "validator_path": str(meta_path.relative_to(self.repo_root)),
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-2000:],  # last 2k chars
            "stderr": proc.stderr[-500:],
            "pass_count": pass_count,
            "gate_reached": "GATE_5" if ok else "GATE_0",
            "fail_type": None if ok else "META_VALIDATOR_FAIL",
        }

    # ------------------------------------------------------------------
    # Single validator
    # ------------------------------------------------------------------

    def _run_single_validator(
        self,
        validator_path: str,
        cert_path: Optional[str],
        family_name: str,
    ) -> Dict[str, Any]:
        """Run one validator.

        If cert_path is provided: validate that fixture.
        Otherwise: run --self-test.
        """
        vp = Path(validator_path)
        if not vp.is_absolute():
            vp = self.repo_root / vp
        if not vp.exists():
            return {"ok": False, "error": f"validator not found: {vp}"}

        if cert_path:
            cp = Path(cert_path)
            if not cp.is_absolute():
                cp = self.repo_root / cp
            extra_args = ["--file", str(cp)]
            mode = "cert"
        else:
            extra_args = ["--self-test"]
            mode = "self-test"

        proc = self._run(str(vp), extra_args)
        ok = proc.returncode == 0

        # Try to parse fail_type from stderr/stdout
        fail_type = self._extract_fail_type(proc.stdout + proc.stderr) if not ok else None

        return {
            "ok": ok,
            "validator_path": str(vp.relative_to(self.repo_root)),
            "exit_code": proc.returncode,
            "mode": mode,
            "family_name": family_name,
            "stdout": proc.stdout[-1000:],
            "stderr": proc.stderr[-500:],
            "gate_reached": "GATE_5" if ok else "GATE_0",
            "fail_type": fail_type,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, script: str, extra_args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        cmd = [sys.executable, script] + extra_args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(self.repo_root),
        )

    @staticmethod
    def _extract_pass_count(text: str) -> Optional[int]:
        """Parse 'N/M PASS' pattern from meta-validator output."""
        import re
        m = re.search(r"(\d+)/(\d+)\s+PASS", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _extract_fail_type(text: str) -> Optional[str]:
        """Extract first FAIL type token from validator output."""
        import re
        m = re.search(r"FAIL_TYPE[:\s]+([A-Z_]+)", text)
        if m:
            return m.group(1)
        # Look for any ALL_CAPS error token
        m = re.search(r"\b([A-Z][A-Z_]{4,})\b", text)
        if m:
            return m.group(1)
        return None
