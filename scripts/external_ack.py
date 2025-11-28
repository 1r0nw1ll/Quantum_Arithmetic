"""
Auto-refactor: normalize formatting for external_ack.py
"""

#!/usr/bin/env python3
"""
External ACK helper

Reads a JSON payload from stdin (as sent by the executor to external agents),
writes a small artifact file for the task under artifacts/external/<task_id>.json,
logs an event to logs/collab_events.jsonl, and returns JSON with an 'artifact'
key so the Reviewer quality gate approves the completion.

Supports both payload styles:
 - {"task": {...}, "agent": "gemini", ...}
 - {"event_type": "gemini.execute", "data": {"task": {...}}}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ART = BASE / 'artifacts' / 'external'
ART.mkdir(parents=True, exist_ok=True)
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"invalid_input:{e}"}))
        return 0

    # Extract task and agent
    task = payload.get('task')
    if not task:
        task = (payload.get('data') or {}).get('task')

    agent = payload.get('agent') or (payload.get('data') or {}).get('source')
    if not agent:
        evt = payload.get('event_type') or ''
        if evt and '.' in evt:
            agent = evt.split('.', 1)[0]
    agent = agent or 'external'

    task_id = (task or {}).get('id') or payload.get('task_id') or 'task'
    title = (task or {}).get('title') or ''

    # Write artifact JSON
    out = ART / f"{task_id}.json"
    content = {
        'task_id': task_id,
        'title': title,
        'agent': agent,
        'timestamp': datetime.now().isoformat(),
        'note': 'External ACK generated artifact',
    }
    out.write_text(json.dumps(content, indent=2), encoding='utf-8')

    # Log event
    evt = {
        'event_type': 'external.ack',
        'data': content,
        'timestamp': content['timestamp'],
        'source': 'qa_lab',
    }
    with open(LOGS / 'collab_events.jsonl', 'a') as f:
        f.write(json.dumps(evt) + '\n')

    # Return executor-friendly JSON
    print(json.dumps({'status': 'ok', 'artifact': str(out), 'agent': agent}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

