"""
Auto-refactor: normalize formatting for collab_bridge.py
"""

#!/usr/bin/env python3
"""
Collaboration Bus Bridge

Non-invasive bridge that broadcasts events and interacts with a collaboration bus
when available. If not configured, it writes events to a local JSONL log as a
graceful no-op fallback.

Configuration via environment variables:
- COLLAB_BROADCAST_CMD: external command to broadcast an event. It should
  accept a single JSON payload on stdin and return JSON on stdout.
- COLLAB_SET_STATE_CMD / COLLAB_GET_STATE_CMD: optional commands for shared state.
"""

import json
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
EVENT_LOG = LOGS_DIR / "collab_events.jsonl"


def _run_cmd(cmd: Optional[str], payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not cmd:
        return None
    try:
        proc = subprocess.run(
            shlex.split(cmd),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=int(os.getenv("QA_EXT_TIMEOUT", "120")),
            cwd=str(BASE_DIR),
        )
        if proc.returncode != 0:
            return {"status": "error", "stderr": proc.stderr[-4000:], "code": proc.returncode}
        try:
            return json.loads(proc.stdout.strip() or "{}")
        except Exception:
            return {"status": "ok", "raw": proc.stdout[-4000:]}
    except Exception as e:
        return {"status": "error", "error": f"spawn_failed: {e}"}


def broadcast(event: str, data: Dict[str, Any]) -> None:
    payload = {
        "event": event,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "source": "qa_lab",
    }
    # Best effort external broadcast
    res = _run_cmd(os.getenv("COLLAB_BROADCAST_CMD"), payload)
    # Always append locally for observability
    try:
        with open(EVENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"payload": payload, "result": res}) + "\n")
    except Exception:
        pass


def set_state(key: str, value: Any) -> Optional[Dict[str, Any]]:
    payload = {"op": "set_state", "key": key, "value": value}
    res = _run_cmd(os.getenv("COLLAB_SET_STATE_CMD"), payload)
    return res


def get_state(key: str) -> Optional[Dict[str, Any]]:
    payload = {"op": "get_state", "key": key}
    res = _run_cmd(os.getenv("COLLAB_GET_STATE_CMD"), payload)
    return res


if __name__ == "__main__":
    # Simple self-test
    broadcast("collab.self_test", {"ok": True})
    print("collab_bridge: event logged")

