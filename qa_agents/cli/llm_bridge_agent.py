#!/usr/bin/env python3
"""
LLM Bridge Agent

Connects to the QA collaboration layer (ZMQ if available, otherwise filesystem mode)
and turns an external CLI (e.g. `gemini`, `codex`) into a responsive collab agent.

Security:
  - Prompt threat scanning via QA Guardrail (blocks malicious instructions)
  - Stderr sanitization (strips API keys, credentials, tokens before publishing)
  - Audit logging of all ALLOW/DENY decisions

Protocol:
  - Subscribe to `--in-topic` events whose payload contains:
      {"request_id": "...", "prompt": "..."}
  - Publish to `--out-topic`:
      {"request_id": "...", "ok": bool, "stdout": "...", "stderr": "...", "returncode": int}
"""

from __future__ import annotations

import argparse
import re
import subprocess
import threading
import time
from typing import Any, Dict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qa_agents.cli.qa_agent_base import CollaborativeAgent

# --- Security: QA Guardrail threat scanner ---
_GUARDRAIL_DIR = Path(__file__).resolve().parents[3] / "qa_alphageometry_ptolemy" / "qa_guardrail"
sys.path.insert(0, str(_GUARDRAIL_DIR))
try:
    from threat_scanner import scan_for_threats, is_content_safe
    GUARDRAIL_AVAILABLE = True
except ImportError:
    GUARDRAIL_AVAILABLE = False

# --- Stderr sanitization patterns ---
# Matches API keys, bearer tokens, credentials in URLs, session tokens
_SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|apikey|api_secret|secret_key)\s*[=:]\s*\S+'),
    re.compile(r'(?i)(bearer|token|authorization)\s*[=:]\s*\S+'),
    re.compile(r'https?://[^@\s]+:[^@\s]+@'),  # credentials in URLs
    re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*\S+'),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),  # OpenAI-style keys
    re.compile(r'AIza[a-zA-Z0-9_-]{35}'),  # Google API keys
    re.compile(r'ya29\.[a-zA-Z0-9_-]+'),  # Google OAuth tokens
    re.compile(r'AKIA[A-Z0-9]{16}'),  # AWS access keys
]


def _sanitize_stderr(stderr: str) -> str:
    """Strip sensitive data from stderr before publishing to event log."""
    sanitized = stderr
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub('[REDACTED]', sanitized)
    return sanitized


def _scan_prompt(prompt: str, request_id: str, agent_name: str) -> Dict[str, Any] | None:
    """
    Scan prompt for threats using QA Guardrail threat scanner.

    Returns None if safe, or a DENY response dict if threats detected.
    """
    if not GUARDRAIL_AVAILABLE:
        return None  # Fail open if guardrail not importable (log warning at startup)

    if is_content_safe(prompt):
        return None

    # Content has threats — scan for details and block
    scan_result = scan_for_threats(prompt)
    threat_summary = []
    for category in ("malicious", "malformed", "adversarial"):
        patterns = scan_result.get(category, [])
        if patterns:
            for p in patterns:
                label = p["pattern_id"] if isinstance(p, dict) else str(p)
                threat_summary.append(f"{category}:{label}")

    return {
        "ok": False,
        "stdout": "",
        "stderr": f"GUARDRAIL_DENY: prompt blocked by QA threat scanner. "
                  f"Threats: {', '.join(threat_summary) or 'unknown'}",
        "returncode": 77,  # EX_NOPERM
        "guardrail": "DENY",
        "threats": threat_summary,
    }


def _run_cmd(cmd: str, prompt: str, timeout_s: float) -> Dict[str, Any]:
    try:
        p = subprocess.run(
            cmd.split(),
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
        return {
            "ok": p.returncode == 0,
            "stdout": p.stdout,
            "stderr": _sanitize_stderr(p.stderr),
            "returncode": p.returncode,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "stdout": e.stdout or "",
            "stderr": _sanitize_stderr((e.stderr or "") + f"\nTIMEOUT after {timeout_s}s"),
            "returncode": 124,
        }
    except Exception as e:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"spawn_failed: {e}",
            "returncode": 127,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Agent name, e.g. gemini_bridge")
    ap.add_argument("--cmd", required=True, help="External command, e.g. 'gemini' or 'codex'")
    ap.add_argument("--in-topic", required=True, help="Topic to listen on, e.g. llm_request.gemini")
    ap.add_argument("--out-topic", required=True, help="Topic to respond on, e.g. llm_response.gemini")
    ap.add_argument("--timeout-s", type=float, default=120.0)
    ap.add_argument("--no-guardrail", action="store_true",
                    help="Disable threat scanning (NOT recommended)")
    args = ap.parse_args()

    guardrail_active = GUARDRAIL_AVAILABLE and not args.no_guardrail
    if not GUARDRAIL_AVAILABLE:
        print(f"⚠️  {args.name}: QA Guardrail not importable — running WITHOUT threat scanning")
    elif args.no_guardrail:
        print(f"⚠️  {args.name}: Guardrail explicitly disabled via --no-guardrail")
    else:
        print(f"🛡️  {args.name}: QA Guardrail active — prompt threat scanning enabled")

    agent = CollaborativeAgent(str(args.name), auto_connect=True)
    agent.subscribe(str(args.in_topic))

    lock = threading.Lock()
    active: set[str] = set()

    def handle(msg: Dict[str, Any]) -> None:
        payload = msg.get("payload") if isinstance(msg, dict) else None
        if not isinstance(payload, dict):
            return
        request_id = str(payload.get("request_id") or "").strip()
        prompt = payload.get("prompt")
        if not request_id or not isinstance(prompt, str):
            return

        with lock:
            if request_id in active:
                return
            active.add(request_id)

        def work() -> None:
            # --- Security gate: scan prompt before execution ---
            if guardrail_active:
                deny = _scan_prompt(prompt, request_id, agent.name)
                if deny is not None:
                    agent.publish(
                        str(args.out_topic),
                        {"request_id": request_id, "agent": agent.name, **deny},
                    )
                    with lock:
                        active.discard(request_id)
                    return

            res = _run_cmd(str(args.cmd), prompt, float(args.timeout_s))
            agent.publish(
                str(args.out_topic),
                {"request_id": request_id, "agent": agent.name, **res},
            )
            with lock:
                active.discard(request_id)

        threading.Thread(target=work, daemon=True).start()

    agent.on(str(args.in_topic), handle)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        agent.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
