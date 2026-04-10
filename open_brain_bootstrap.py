#!/usr/bin/env python3
"""
qa_lab.open_brain_bootstrap
===========================

Fail-fast Open Brain bootstrap for QA Lab sessions.

What it does:
- verifies Open Brain is reachable with the local MCP HTTP endpoint
- fetches recent thoughts immediately at session start
- writes the fetched context into qa_lab/kernel/injected_context.txt

Default behavior is strict: connection or authentication failure exits non-zero.
For explicit emergency bypasses only, pass --allow-missing-open-brain.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

QA_LAB_DIR = Path(__file__).resolve().parent
CONTEXT_FILE = QA_LAB_DIR / "kernel" / "injected_context.txt"
DEFAULT_URL = "https://bepguekxksbgiqleadvq.supabase.co/functions/v1/open-brain-mcp"


class OpenBrainBootstrapError(RuntimeError):
    """Raised when the session cannot establish Open Brain context."""


@dataclass
class BootstrapResult:
    connected: bool
    chars_written: int
    thoughts_requested: int
    since_days: int


def _read_token() -> str:
    token = os.environ.get("OPEN_BRAIN_TOKEN", "").strip()
    if token:
        return token

    key_path = Path.home() / ".open_brain_mcp_key"
    if key_path.exists():
        value = key_path.read_text(encoding="utf-8").strip()
        if value:
            return value

    raise OpenBrainBootstrapError(
        "Open Brain token not found. Set OPEN_BRAIN_TOKEN or create ~/.open_brain_mcp_key."
    )


def _post_json(url: str, token: str, payload: dict[str, object], timeout: float = 30.0) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OpenBrainBootstrapError(f"Open Brain HTTP error {exc.code}: {body}") from exc
    except URLError as exc:
        raise OpenBrainBootstrapError(f"Open Brain network error: {exc}") from exc

    result_obj: dict[str, object] | None = None
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        payload_text = line[6:].strip()
        if not payload_text:
            continue
        try:
            event = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if "error" in event:
            err = event["error"]
            if isinstance(err, dict):
                raise OpenBrainBootstrapError(
                    f"Open Brain RPC error {err.get('code')}: {err.get('message')}"
                )
            raise OpenBrainBootstrapError(f"Open Brain RPC error: {err}")
        if "result" in event:
            result_obj = event["result"]

    if result_obj is None:
        raise OpenBrainBootstrapError("Open Brain did not return a parseable result.")
    return result_obj


def _call_tool(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    token = _read_token()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    result = _post_json(DEFAULT_URL, token, payload)
    if not isinstance(result, dict):
        raise OpenBrainBootstrapError(f"Unexpected Open Brain result type: {type(result).__name__}")
    return result


def _extract_text(result: dict[str, object]) -> str:
    content = result.get("content")
    texts: list[str] = []

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(item["text"].strip())

    if texts:
        return "\n\n".join(text for text in texts if text)

    thoughts = result.get("thoughts")
    if isinstance(thoughts, list):
        formatted: list[str] = []
        for thought in thoughts:
            if not isinstance(thought, dict):
                continue
            timestamp = thought.get("created_at") or thought.get("timestamp") or ""
            thought_type = thought.get("type") or "thought"
            body = thought.get("content") or thought.get("body") or ""
            if body:
                formatted.append(f"- {timestamp} ({thought_type}) {body}".strip())
        return "\n".join(formatted).strip()

    return ""


def bootstrap_open_brain_context(
    *,
    limit: int = 10,
    since_days: int = 7,
    write_context: bool = True,
) -> BootstrapResult:
    result = _call_tool("recent_thoughts", {"limit": limit, "since_days": since_days})
    text = _extract_text(result)

    if write_context:
        CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONTEXT_FILE.write_text(text, encoding="utf-8")

    return BootstrapResult(
        connected=True,
        chars_written=len(text),
        thoughts_requested=limit,
        since_days=since_days,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Open Brain context for QA Lab sessions.")
    parser.add_argument("--limit", type=int, default=10, help="How many recent thoughts to fetch")
    parser.add_argument("--since-days", type=int, default=7, help="How far back to query")
    parser.add_argument(
        "--allow-missing-open-brain",
        action="store_true",
        help="Emergency bypass: continue even if Open Brain cannot be reached",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output")
    args = parser.parse_args()

    try:
        result = bootstrap_open_brain_context(limit=args.limit, since_days=args.since_days)
    except OpenBrainBootstrapError as exc:
        if args.allow_missing_open_brain:
            if not args.quiet:
                print(f"[open-brain] BYPASS: {exc}")
            return 0
        print(f"[open-brain] ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"[open-brain] connected; fetched recent thoughts "
            f"(limit={result.thoughts_requested}, since_days={result.since_days}) "
            f"→ wrote {result.chars_written} chars to {CONTEXT_FILE}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
