#!/usr/bin/env python3
"""
Send a request over the collaboration layer and wait for a response.

Example (filesystem mode works without sockets/bus):
  QA_COLLAB_MODE=fs python3 qa_lab/qa_agents/cli/collab_request.py \
    --to gemini --prompt "Summarize PROJECT_SPEC.md in 5 bullets"
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import uuid
from typing import Any, Dict, Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qa_agents.cli.qa_agent_base import CollaborativeAgent


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="Target name suffix, e.g. gemini -> llm_request.gemini")
    ap.add_argument("--prompt", default="", help="Prompt string (if empty, read stdin)")
    ap.add_argument("--timeout-s", type=float, default=60.0)
    args = ap.parse_args(argv)

    prompt = str(args.prompt)
    if not prompt.strip():
        prompt = sys.stdin.read()

    request_id = uuid.uuid4().hex
    in_topic = f"llm_response.{args.to}"
    out_topic = f"llm_request.{args.to}"

    agent = CollaborativeAgent("collab_request", auto_connect=True)
    agent.subscribe(in_topic)

    done = threading.Event()
    result: dict[str, Any] = {}

    def handle(msg: Dict[str, Any]) -> None:
        payload = msg.get("payload") if isinstance(msg, dict) else None
        if not isinstance(payload, dict):
            return
        if str(payload.get("request_id") or "") != request_id:
            return
        result.update(payload)
        done.set()

    agent.on(in_topic, handle)

    agent.publish(out_topic, {"request_id": request_id, "prompt": prompt})

    timeout_s = max(0.0, min(300.0, float(args.timeout_s)))
    ok = done.wait(timeout=timeout_s)
    agent.disconnect()

    if not ok:
        print(f"Timed out waiting for {in_topic} request_id={request_id}", file=sys.stderr)
        return 2

    # Print stdout as the main result; include error on stderr if present.
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    if stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith("\n"):
            sys.stdout.write("\n")
    if stderr.strip():
        print(stderr.strip(), file=sys.stderr)
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
