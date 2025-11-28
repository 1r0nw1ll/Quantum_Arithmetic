"""
Auto-refactor: normalize formatting for external_agent_wrappers.py
"""

#!/usr/bin/env python3
import json
import shlex
import subprocess
from typing import Optional, Dict

def call_command(cmd: Optional[str], payload: Dict, timeout: int = 120) -> Dict:
    """Call an external command with JSON stdin/stdout.

    Returns parsed JSON or a structured error.
    """
    if not cmd:
        return {"status": "error", "error": "no command"}
    try:
        p = subprocess.run(
            shlex.split(cmd),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except Exception as e:
        return {"status": "error", "error": f"spawn_failed:{e}"}

    if p.returncode != 0:
        return {"status": "error", "code": p.returncode, "stderr": p.stderr[-4000:]}

    try:
        return json.loads(p.stdout.strip() or "{}")
    except Exception:
        return {"status": "ok", "raw": p.stdout[-4000:]}

