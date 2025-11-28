"""
Auto-refactor: normalize formatting for mock_external.py
"""

#!/usr/bin/env python3
"""
Mock external agent for integration testing.
Reads a single JSON payload from stdin and returns a minimal JSON result.
"""

import sys
import json
from datetime import datetime

def main():
    data = sys.stdin.read()
    try:
        payload = json.loads(data) if data.strip() else {}
    except Exception as e:
        print(json.dumps({"success": False, "error": f"invalid input: {e}"}))
        return 0

    task = payload.get("task", {})
    title = task.get("title", "task")
    result = {
        "success": True,
        "output": f"Processed: {title}",
        "changes": [],
        "state": "completed",
        "completed_at": datetime.now().isoformat(),
    }
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    sys.exit(main())

