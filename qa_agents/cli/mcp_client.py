"""
Auto-refactor: normalize formatting for mcp_client.py
"""

#!/usr/bin/env python3
"""
MCP Client for QA Lab
JSON-RPC client for communicating with MCP servers
"""

import json
import subprocess
import sys
from typing import Dict, List, Any, Optional

class MCPClient:
    """Client for Model Context Protocol servers"""

    def __init__(self, server_command: List[str]):
        """
        Initialize MCP client with server command

        Args:
            server_command: Command to start server (e.g., ['python3', 'server.py'])
        """
        self.server_command = server_command
        self.process = None
        self.request_id = 0

    def start(self):
        """Start the MCP server process"""
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send JSON-RPC request to server"""
        if not self.process:
            raise Exception("MCP server not started. Call start() first.")

        self.request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        # Send request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()

        # Read response
        response_str = self.process.stdout.readline()
        if not response_str:
            raise Exception("MCP server did not respond")

        response = json.loads(response_str)

        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")

        return response.get("result", {})

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Dictionary of tool arguments

        Returns:
            Tool result
        """
        return self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    def list_tools(self) -> List[Dict]:
        """
        List available tools from server

        Returns:
            List of tool definitions
        """
        result = self.send_request("tools/list")
        return result.get("tools", [])

    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()


def main():
    """CLI interface for MCP client testing"""
    import argparse

    parser = argparse.ArgumentParser(description='MCP Client CLI')
    parser.add_argument('server_command', nargs='+', help='Command to start MCP server')
    parser.add_argument('--list-tools', action='store_true', help='List available tools')
    parser.add_argument('--call-tool', help='Tool name to call')
    parser.add_argument('--args', help='JSON arguments for tool call')

    args = parser.parse_args()

    with MCPClient(args.server_command) as client:
        if args.list_tools:
            tools = client.list_tools()
            print("Available tools:")
            for tool in tools:
                print(f"  • {tool['name']}: {tool.get('description', 'No description')}")

        elif args.call_tool:
            arguments = json.loads(args.args) if args.args else {}
            result = client.call_tool(args.call_tool, arguments)
            print(json.dumps(result, indent=2))

        else:
            print("Specify --list-tools or --call-tool")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
