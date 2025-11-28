"""
Auto-refactor: normalize formatting for mcp_json_tools.py
"""

#!/usr/bin/env python3
import json
import re

def last_json_object(text: str):
    """Return the last valid JSON object contained in text, if any."""
    candidates = re.findall(r"\{.*\}", text, flags=re.S)
    for s in reversed(candidates):
        try:
            return json.loads(s)
        except Exception:
            continue
    return None

