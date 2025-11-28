"""
Auto-refactor: normalize formatting for mock_external_agent.py
"""

#!/usr/bin/env python3
"""
Mock external agent for Codex/Gemini/OpenCode.

Reads a JSON payload from stdin and returns a JSON success result to
simulate an external agent completing the task. Useful for draining
awaiting_external tasks during local testing.
"""

import sys
import json

def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"invalid_input:{e}"}))
        return 0

    task = payload.get("task") or payload.get("data", {}).get("task") or {}
    agent = payload.get("agent") or payload.get("data", {}).get("source") or "external"
    task_id = task.get("id") or payload.get("task_id")

    # Minimal OK response; executor treats status!=error as success
    resp = {
        "status": "ok",
        "agent": agent,
        "task_id": task_id,
        "message": "external agent processed task",
    }
    print(json.dumps(resp))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

