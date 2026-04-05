"""
qa_lab.agents.experiment_agent
================================
ExperimentAgent — runs research scripts and auto-certifies results as [122] certs.

This is the primary research worker agent. Its role:
  1. Accept an EXPERIMENT task with a script path + arguments
  2. Run the script as a subprocess (approved scripts only)
  3. Parse exit code, stdout, stderr for success indicators
  4. Classify result: CONSISTENT / CONTRADICTS / PARTIAL / INCONCLUSIVE
  5. Auto-produce a [122] QA_EMPIRICAL_OBSERVATION_CERT artifact
  6. Surface any numeric results for the kernel's LEARN step

Security model
--------------
ExperimentAgent only runs scripts from the approved_scripts list OR scripts
within the repo_root (never absolute paths outside the repo). This prevents
arbitrary code execution via task injection.

The operator can also set dry_run=True on the kernel to prevent actual
script execution (outputs a mock result instead).

Verdict classification
----------------------
CONSISTENT    — exit 0 AND success_pattern matched (or no pattern specified)
CONTRADICTS   — exit 0 but explicit FAIL marker in output
PARTIAL       — exit 0 but some sub-checks failed
INCONCLUSIVE  — non-zero exit, timeout, or ambiguous output
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import QAAgent

_QA_LAB_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _QA_LAB_DIR.parent


class ExperimentAgent(QAAgent):
    """Runs research scripts and auto-certifies results as [122] certs.

    Capabilities: experiment
    """

    capabilities = ["experiment"]
    cert_family = "qa_experiment_cert"

    # Patterns that indicate explicit FAIL despite exit 0
    FAIL_PATTERNS = [
        r"\bFAIL\b", r"\bFAILED\b", r"VERDICT:\s*FAIL",
        r"CONTRADICTS", r"pre-declared criteria.*FAIL",
    ]
    # Patterns that indicate explicit PASS
    PASS_PATTERNS = [
        r"\bPASS\b", r"\bPASSED\b", r"VERDICT:\s*PASS",
        r"ALL PASS", r"ALL ASSERTIONS PASS",
    ]
    # Numeric result extraction
    NUMERIC_PATTERNS = [
        r"r\s*=\s*(-?[\d.]+)",           # correlation r = -0.845
        r"p\s*=\s*([\d.e+-]+)",           # p-value p = 0.0025
        r"SR\s*=\s*([+-]?[\d.]+)",        # Sharpe ratio SR = 0.803
        r"acc(?:uracy)?\s*=\s*([\d.]+)",  # accuracy = 0.689
        r"(\d+)/(\d+)\s+PASS",            # pass count 128/128
    ]

    def __init__(
        self,
        repo_root: Optional[str | Path] = None,
        approved_scripts: Optional[List[str]] = None,
        timeout: int = 120,
        modulus: int = 9,
        dry_run: bool = False,
    ):
        super().__init__(name="experiment_agent", modulus=modulus)
        self.repo_root = Path(repo_root) if repo_root else _REPO_ROOT
        self.timeout = timeout
        self.dry_run = dry_run
        # Approved scripts: relative paths from repo_root
        # Empty list = all scripts in repo_root are approved
        self.approved_scripts: List[str] = approved_scripts or []

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        """Execute an EXPERIMENT task.

        Required inputs:
          script_path   — path to Python script (relative to repo_root)

        Optional inputs:
          args          — list of CLI args to pass
          success_pattern  — regex that must match stdout for CONSISTENT verdict
          fail_pattern     — regex that, if matched, forces CONTRADICTS verdict
          parent_cert      — name of parent cert claim being tested
          capture_numbers  — bool, default True: extract numeric results
          env              — dict of extra environment variables
        """
        inputs = task.inputs if hasattr(task, "inputs") else {}
        script_path = inputs.get("script_path")

        if not script_path:
            return {
                "ok": False,
                "error": "EXPERIMENT task requires 'script_path' in inputs",
            }

        sp = Path(script_path)
        if not sp.is_absolute():
            sp = self.repo_root / sp

        # Security: must be within repo_root
        try:
            sp.relative_to(self.repo_root)
        except ValueError:
            return {
                "ok": False,
                "error": f"SECURITY: script_path '{script_path}' is outside repo_root",
            }

        if not sp.exists():
            return {"ok": False, "error": f"script not found: {sp}"}

        # Approval check
        if self.approved_scripts:
            rel = str(sp.relative_to(self.repo_root))
            if rel not in self.approved_scripts:
                return {
                    "ok": False,
                    "error": f"script '{rel}' not in approved_scripts list",
                    "approved": self.approved_scripts,
                }

        # Dry run
        if self.dry_run:
            return self._mock_result(script_path, inputs)

        # Run
        return self._run_script(sp, inputs, task)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _run_script(self, sp: Path, inputs: Dict[str, Any], task: Any) -> Dict[str, Any]:
        args = inputs.get("args", [])
        if isinstance(args, str):
            args = args.split()
        cmd = [sys.executable, str(sp)] + [str(a) for a in args]

        import os
        env = os.environ.copy()
        # Auto-inject PYTHONPATH=qa_lab for scripts that live under
        # qa_lab/ — they typically import their own package by top-level
        # name (e.g. `from qa_agents.cli.foo import ...`) which requires
        # qa_lab/ on sys.path, not the repo root.  Callers can still
        # override via inputs["env"].
        try:
            rel = sp.relative_to(self.repo_root)
            if rel.parts and rel.parts[0] == "qa_lab":
                qa_lab_dir = str(self.repo_root / "qa_lab")
                existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    qa_lab_dir
                    if not existing
                    else f"{qa_lab_dir}{os.pathsep}{existing}"
                )
        except (ValueError, AttributeError):
            pass
        env.update(inputs.get("env", {}))

        t_start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=self.timeout,
                cwd=str(self.repo_root),
                env=env,
            )
            elapsed_ms = (time.time() - t_start) * 1000
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "verdict": "INCONCLUSIVE",
                "error": f"script timed out after {self.timeout}s",
                "script_path": str(sp.relative_to(self.repo_root)),
            }
        except Exception as exc:
            return {"ok": False, "verdict": "INCONCLUSIVE", "error": str(exc)}

        combined = proc.stdout + proc.stderr
        verdict = self._classify_verdict(proc.returncode, combined, inputs)
        numbers = self._extract_numbers(combined) if inputs.get("capture_numbers", True) else {}

        # Build [122] cert
        cert = self.certify(
            observation_body=self._make_observation_body(sp, proc, verdict, numbers),
            verdict=verdict,
            evidence=self._make_evidence(proc, numbers, elapsed_ms),
            parent_cert_name=inputs.get("parent_cert", "QA_CORE_SPEC.v1"),
            observation_source="experiment_script",
            fail_ledger=self._make_fail_ledger(verdict, combined) if verdict == "CONTRADICTS" else None,
        )

        return {
            "ok": proc.returncode == 0,
            "verdict": verdict,
            "exit_code": proc.returncode,
            "script_path": str(sp.relative_to(self.repo_root)),
            "stdout": proc.stdout[-3000:],
            "stderr": proc.stderr[-500:],
            "elapsed_ms": round(elapsed_ms, 1),
            "numbers": numbers,
            "cert": cert,
        }

    # ------------------------------------------------------------------
    # Verdict classification
    # ------------------------------------------------------------------

    def _classify_verdict(self, exit_code: int, output: str, inputs: Dict[str, Any]) -> str:
        """Classify result into QA verdict."""
        if exit_code != 0:
            return "INCONCLUSIVE"

        # Explicit fail pattern from inputs
        custom_fail = inputs.get("fail_pattern")
        if custom_fail and re.search(custom_fail, output):
            return "CONTRADICTS"

        # Check built-in fail patterns
        for pat in self.FAIL_PATTERNS:
            if re.search(pat, output):
                return "CONTRADICTS"

        # Explicit success pattern from inputs
        custom_pass = inputs.get("success_pattern")
        if custom_pass:
            return "CONSISTENT" if re.search(custom_pass, output) else "PARTIAL"

        # Check built-in pass patterns
        for pat in self.PASS_PATTERNS:
            if re.search(pat, output):
                return "CONSISTENT"

        # Default: exit 0 with no explicit markers = PARTIAL
        return "PARTIAL"

    # ------------------------------------------------------------------
    # Number extraction
    # ------------------------------------------------------------------

    def _extract_numbers(self, text: str) -> Dict[str, Any]:
        results = {}
        for pat in self.NUMERIC_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                key = pat.split(r"\s")[0].strip(r"\b").rstrip("s").lower()
                if m.lastindex and m.lastindex >= 2:
                    results[key] = f"{m.group(1)}/{m.group(2)}"
                else:
                    results[key] = m.group(1)
        return results

    # ------------------------------------------------------------------
    # Cert construction helpers
    # ------------------------------------------------------------------

    def _make_observation_body(self, sp: Path, proc: subprocess.CompletedProcess,
                                verdict: str, numbers: Dict) -> str:
        rel = str(sp.relative_to(self.repo_root))
        body = f"Script: {rel}\nExit code: {proc.returncode}\nVerdict: {verdict}"
        if numbers:
            body += "\nKey results: " + ", ".join(f"{k}={v}" for k, v in numbers.items())
        # First non-empty output line as summary
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                body += f"\nFirst output: {line[:120]}"
                break
        return body

    def _make_evidence(self, proc: subprocess.CompletedProcess,
                        numbers: Dict, elapsed_ms: float) -> List[Dict[str, Any]]:
        return [{
            "type": "script_execution",
            "exit_code": proc.returncode,
            "elapsed_ms": round(elapsed_ms, 1),
            "stdout_tail": proc.stdout[-500:].strip(),
            "numbers": numbers,
        }]

    def _make_fail_ledger(self, verdict: str, output: str) -> List[Dict[str, Any]]:
        if verdict != "CONTRADICTS":
            return []
        # Find the first fail pattern that matched
        for pat in self.FAIL_PATTERNS:
            m = re.search(pat, output)
            if m:
                return [{
                    "fail_type": "EXPERIMENT_OUTPUT_CONTRADICTS_CRITERIA",
                    "detail": f"Pattern '{pat}' matched: '{m.group(0)}'",
                }]
        return [{"fail_type": "EXPERIMENT_OUTPUT_CONTRADICTS_CRITERIA", "detail": "output indicates failure"}]

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def _mock_result(self, script_path: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Return a mock result for dry-run mode."""
        return {
            "ok": True,
            "verdict": "CONSISTENT",
            "exit_code": 0,
            "script_path": script_path,
            "stdout": "[DRY RUN — script not executed]",
            "stderr": "",
            "elapsed_ms": 0.0,
            "numbers": {},
            "dry_run": True,
        }
