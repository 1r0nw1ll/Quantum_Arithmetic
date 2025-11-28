#!/usr/bin/env python3
"""
QA Collaboration MCP Server
Exposes collaboration bus functionality as MCP tools for external AI agents
(Claude, OpenCode, Gemini, Codex, etc.)
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_agents.cli.qa_agent_base import CollaborativeAgent


class CollabMCPServer:
    """MCP Server for collaboration bus access"""

    def __init__(self):
        self.agent = None
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
