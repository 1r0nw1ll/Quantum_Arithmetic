#!/usr/bin/env python3
"""
QA Collaboration MCP Server
Exposes collaboration bus functionality as MCP tools for external AI agents
(Claude, OpenCode, Gemini, Codex, etc.)
"""

import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_agents.cli.qa_agent_base import CollaborativeAgent


# ============================================================================
# TOPIC-LEVEL ACCESS CONTROL
# ============================================================================
# Defines which agent name prefixes can publish to which topic patterns.
# "llm_request.*" topics are restricted because they trigger external command
# execution via bridge agents. Other topics are open by default.
#
# Format: topic_prefix -> set of allowed agent name prefixes
# An agent matches if its name starts with any allowed prefix.
# Topics not listed here are OPEN (any agent can publish).

TOPIC_ACL = {
    "llm_request.": {"claude-code", "mcp_agent"},   # only Claude sessions
    "commit_intent": {"claude-code", "mcp_agent"},   # git commits need auth
    "commit_veto": {"claude-code", "mcp_agent"},
}

# State keys that require authorization to write
STATE_ACL = {
    "file_locks": {"claude-code", "mcp_agent"},      # only Claude sessions manage locks
}


def _check_topic_acl(topic: str, agent_name: str) -> str | None:
    """
    Check if agent is authorized to publish to topic.
    Returns None if allowed, or an error message if denied.
    """
    for prefix, allowed_agents in TOPIC_ACL.items():
        if topic.startswith(prefix):
            if not any(agent_name.startswith(a) for a in allowed_agents):
                return (f"ACL_DENY: agent '{agent_name}' not authorized to "
                        f"publish to '{topic}'. Allowed: {sorted(allowed_agents)}")
    return None


def _check_state_acl(key: str, agent_name: str) -> str | None:
    """
    Check if agent is authorized to write a state key.
    Returns None if allowed, or an error message if denied.
    """
    for protected_key, allowed_agents in STATE_ACL.items():
        if key == protected_key or key.startswith(protected_key + ":"):
            if not any(agent_name.startswith(a) for a in allowed_agents):
                return (f"ACL_DENY: agent '{agent_name}' not authorized to "
                        f"write state key '{key}'. Allowed: {sorted(allowed_agents)}")
    return None


class CollabMCPServer:
    """MCP Server for collaboration bus access"""

    def __init__(self):
        self.agent = None
        self.agent_name = "unknown"
        self.request_id = 0

    def handle_request(self, request: dict) -> dict:
        """Handle MCP requests"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return self.handle_initialize(params)
        elif method == "tools/list":
            return self.handle_tools_list()
        elif method == "tools/call":
            return self.handle_tool_call(params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    def handle_initialize(self, params: dict) -> dict:
        """Initialize MCP server"""
        # Connect to collaboration bus
        agent_name = params.get("clientInfo", {}).get("name", "mcp_agent")

        try:
            self.agent_name = agent_name
            self.agent = CollaborativeAgent(
                name=agent_name,
                auto_connect=True,
                metadata={"type": "mcp", "client": agent_name}
            )

            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "qa-collab",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "error": {
                    "code": -32603,
                    "message": f"Failed to connect to collaboration bus: {str(e)}"
                }
            }

    def handle_tools_list(self) -> dict:
        """List available tools"""
        tools = [
            {
                "name": "collab_broadcast",
                "description": "Broadcast an event to all agents on the collaboration bus",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "description": "Type of event (e.g., 'task_started', 'task_completed', 'help_needed')"
                        },
                        "data": {
                            "type": "object",
                            "description": "Event data payload"
                        }
                    },
                    "required": ["event_type", "data"]
                }
            },
            {
                "name": "collab_get_state",
                "description": "Get a value from the shared state accessible to all agents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "State key to retrieve"
                        },
                        "default": {
                            "description": "Default value if key doesn't exist"
                        }
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "collab_set_state",
                "description": "Set a value in the shared state accessible to all agents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "State key to set"
                        },
                        "value": {
                            "description": "Value to store"
                        }
                    },
                    "required": ["key", "value"]
                }
            },
            {
                "name": "collab_query_agents",
                "description": "Query active agents on the collaboration bus",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Filters to apply (e.g., {'name': 'executor'})"
                        }
                    }
                }
            },
            {
                "name": "collab_subscribe",
                "description": "Subscribe to events on a topic",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Topic to subscribe to (e.g., 'task_completed', 'state_changed')"
                        }
                    },
                    "required": ["topic"]
                }
            },
            {
                "name": "collab_publish",
                "description": "Publish an event to a specific topic",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Topic to publish to"
                        },
                        "payload": {
                            "type": "object",
                            "description": "Event payload"
                        }
                    },
                    "required": ["topic", "payload"]
                }
            },
            {
                "name": "collab_log_activity",
                "description": "Log an activity for other agents to see",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Action being performed"
                        },
                        "details": {
                            "type": "object",
                            "description": "Activity details"
                        }
                    },
                    "required": ["action", "details"]
                }
            },
            {
                "name": "collab_read_events",
                "description": "Read collaboration events from the append-only JSONL log (works in filesystem mode)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "after_offset": {
                            "type": "integer",
                            "description": "Byte offset to start reading from (0 for start). If omitted, reads from end-0.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max events to return (default 50, max 200).",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Optional topic filter (exact match).",
                        },
                        "request_id": {
                            "type": "string",
                            "description": "Optional filter: payload.request_id must match exactly.",
                        },
                    },
                },
            },
            {
                "name": "collab_wait_for_event",
                "description": "Poll the event log until a matching event arrives (filesystem mode friendly)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "timeout_s": {"type": "number"},
                        "after_offset": {"type": "integer"},
                        "request_id": {"type": "string"},
                    },
                    "required": ["topic"],
                },
            }
        ]

        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "result": {
                "tools": tools
            }
        }

    def handle_tool_call(self, params: dict) -> dict:
        """Handle tool calls"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not self.agent or not self.agent.connected:
            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "error": {
                    "code": -32603,
                    "message": "Not connected to collaboration bus"
                }
            }

        try:
            if tool_name == "collab_broadcast":
                success = self.agent.broadcast(
                    arguments["event_type"],
                    arguments["data"]
                )
                result = {
                    "success": success,
                    "message": f"Broadcasted {arguments['event_type']}" if success else "Broadcast failed"
                }

            elif tool_name == "collab_get_state":
                value = self.agent.get_state(
                    arguments["key"],
                    arguments.get("default")
                )
                result = {
                    "key": arguments["key"],
                    "value": value
                }

            elif tool_name == "collab_set_state":
                # --- ACL check: state key access control ---
                acl_err = _check_state_acl(arguments["key"], self.agent_name)
                if acl_err:
                    result = {
                        "success": False,
                        "key": arguments["key"],
                        "error": acl_err,
                    }
                else:
                    success = self.agent.set_state(
                        arguments["key"],
                        arguments["value"]
                    )
                    result = {
                        "success": success,
                        "key": arguments["key"],
                        "value": arguments["value"]
                    }

            elif tool_name == "collab_query_agents":
                agents = self.agent.query_agents(arguments.get("filters"))
                result = {
                    "agents": agents,
                    "count": len(agents)
                }

            elif tool_name == "collab_subscribe":
                self.agent.subscribe(arguments["topic"])
                result = {
                    "success": True,
                    "topic": arguments["topic"],
                    "message": f"Subscribed to {arguments['topic']}"
                }

            elif tool_name == "collab_publish":
                # --- ACL check: topic-level access control ---
                acl_err = _check_topic_acl(arguments["topic"], self.agent_name)
                if acl_err:
                    result = {
                        "success": False,
                        "topic": arguments["topic"],
                        "error": acl_err,
                    }
                else:
                    success = self.agent.publish(
                        arguments["topic"],
                        arguments["payload"]
                    )
                    result = {
                        "success": success,
                        "topic": arguments["topic"]
                    }

            elif tool_name == "collab_log_activity":
                self.agent.log_activity(
                    arguments["action"],
                    arguments["details"]
                )
                result = {
                    "success": True,
                    "action": arguments["action"]
                }

            elif tool_name == "collab_read_events":
                base_dir = Path(__file__).parent.parent.parent
                events_path = base_dir / "logs" / "collab_events.jsonl"
                topic = str(arguments.get("topic") or "").strip()
                want_request_id = str(arguments.get("request_id") or "").strip()
                limit = int(arguments.get("limit") or 50)
                limit = max(1, min(200, limit))

                after_offset = arguments.get("after_offset", None)
                if after_offset is None:
                    after_offset = events_path.stat().st_size if events_path.exists() else 0
                after_offset = int(after_offset)
                after_offset = max(0, after_offset)

                events = []
                next_offset = after_offset
                if events_path.exists():
                    with events_path.open("r", encoding="utf-8") as f:
                        f.seek(after_offset)
                        while len(events) < limit:
                            line = f.readline()
                            if not line:
                                break
                            next_offset = f.tell()
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                ev = json.loads(line)
                            except Exception:
                                continue
                            if not isinstance(ev, dict):
                                continue
                            if topic and str(ev.get("topic") or "") != topic:
                                continue
                            if want_request_id:
                                payload = ev.get("payload")
                                if not isinstance(payload, dict) or str(payload.get("request_id") or "") != want_request_id:
                                    continue
                            events.append(ev)
                result = {"events": events, "next_offset": next_offset}

            elif tool_name == "collab_wait_for_event":
                base_dir = Path(__file__).parent.parent.parent
                events_path = base_dir / "logs" / "collab_events.jsonl"
                topic = str(arguments["topic"]).strip()
                want_request_id = str(arguments.get("request_id") or "").strip()
                timeout_s = float(arguments.get("timeout_s") or 10.0)
                timeout_s = max(0.0, min(60.0, timeout_s))
                after_offset = int(arguments.get("after_offset") or (events_path.stat().st_size if events_path.exists() else 0))
                after_offset = max(0, after_offset)

                deadline = time.time() + timeout_s
                cur = after_offset
                matched = None
                while time.time() < deadline and matched is None:
                    evs = []
                    nxt = cur
                    if events_path.exists():
                        with events_path.open("r", encoding="utf-8") as f:
                            f.seek(cur)
                            while True:
                                line = f.readline()
                                if not line:
                                    break
                                nxt = f.tell()
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    ev = json.loads(line)
                                except Exception:
                                    continue
                                if not isinstance(ev, dict) or str(ev.get("topic") or "") != topic:
                                    continue
                                if want_request_id:
                                    payload = ev.get("payload")
                                    if not isinstance(payload, dict) or str(payload.get("request_id") or "") != want_request_id:
                                        continue
                                matched = ev
                                break
                    cur = nxt
                    if matched is None:
                        time.sleep(0.2)
                result = {"event": matched, "next_offset": cur, "timed_out": matched is None}

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": self.request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }

    def run(self):
        """Run MCP server on stdin/stdout"""
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    self.request_id = request.get("id", 0)
                    response = self.handle_request(request)
                    print(json.dumps(response), flush=True)

                except json.JSONDecodeError as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {str(e)}"
                        }
                    }
                    print(json.dumps(error_response), flush=True)

        finally:
            if self.agent:
                self.agent.disconnect()


if __name__ == "__main__":
    server = CollabMCPServer()
    server.run()
