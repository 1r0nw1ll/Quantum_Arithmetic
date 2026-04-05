"""
Auto-refactor: normalize formatting for qa_cli.py
"""

#!/usr/bin/env python3
"""
QA Bob-iverse CLI v4.0
Unified command-line interface for the QA Autonomic Research Lab
"""

import argparse
import subprocess
import sys
from pathlib import Path

class QACLI:
    """QA Command Line Interface"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.cli_dir = Path(__file__).parent

    def run_command(self, cmd: list, description: str = "") -> int:
        """Run a shell command with logging."""
        if description:
            print(f"🔧 {description}")
        try:
            result = subprocess.run(cmd, cwd=self.base_dir, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {' '.join(cmd)}")
            return e.returncode

    def cmd_init(self, args):
        """Initialize QA Lab environment."""
        return self.run_command(
            ["make", "init"],
            "Initializing QA Lab environment..."
        )

    def cmd_test(self, args):
        """Run QA tests."""
        return self.run_command(
            ["make", "test"],
            "Running QA invariant tests..."
        )

    def cmd_docs(self, args):
        """Build documentation."""
        return self.run_command(
            ["make", "docs"],
            "Building QA documentation..."
        )

    def cmd_viz(self, args):
        """Generate visualizations."""
        return self.run_command(
            ["make", "viz"],
            "Generating QA visualizations..."
        )

    def cmd_meta(self, args):
        """Run full meta-pipeline."""
        return self.run_command(
            ["make", "meta"],
            "Running QA meta-pipeline..."
        )

    def cmd_scout(self, args):
        """Run Scout agent."""
        return self.run_command(
            ["make", "scout"],
            "Scouting for new tasks..."
        )

    def cmd_prioritize(self, args):
        """Run Prioritizer agent."""
        return self.run_command(
            ["make", "prioritize"],
            "Prioritizing tasks..."
        )

    def cmd_plan(self, args):
        """Run Planner agent."""
        return self.run_command(
            ["make", "plan"],
            "Planning task execution..."
        )

    def cmd_builder(self, args):
        """Run Agent Builder agent."""
        return self.run_command(
            ["make", "builder"],
            "Scaffolding new agents..."
        )
    def cmd_dispatch(self, args):
        """Run Dispatcher agent."""
        return self.run_command(
            ["make", "dispatch"],
            "Dispatching tasks to agents..."
        )

    def cmd_executor(self, args):
        """Run Executor agent."""
        return self.run_command(
            ["make", "executor"],
            "Executing assigned tasks..."
        )

    def cmd_inject(self, args):
        """Inject a task into inbox (quick utility)."""
        # Pass remaining args to injector for flexibility
        injector = self.base_dir / "qa_agents" / "cli" / "task_injector.py"
        return self.run_command(
            ["python3", str(injector), *sys.argv[2:]],
            "Injecting task..."
        )

    def cmd_review(self, args):
        """Run Reviewer agent."""
        return self.run_command(
            ["make", "review"],
            "Reviewing completed work..."
        )

    def cmd_archive(self, args):
        """Run Archivist agent."""
        return self.run_command(
            ["make", "archive"],
            "Archiving completed work..."
        )

    def cmd_loop(self, args):
        """Run full agent orchestration loop."""
        return self.run_command(
            ["make", "agent_loop"],
            "Running full agent orchestration loop..."
        )

    def cmd_speclock(self, args):
        """Verify SpecLock integrity."""
        speclock_script = self.cli_dir / "speclock.sh"
        return self.run_command(
            [str(speclock_script)],
            "Verifying SpecLock integrity..."
        )

    def cmd_mcp_test(self, args):
        """Test MCP integration (Phase 1)."""
        return self.run_command(
            ["python3", "test_mcp_phase1.py"],
            "Testing MCP integration..."
        )

    def cmd_mcp_list(self, args):
        """List all MCP servers and tools."""
        print("🔌 Available MCP Servers:\n")

        servers = [
            ("qa-right-triangle", "qa_mcp_servers/qa-right-triangle/server.py"),
            ("qa-collab", "qa_mcp_servers/qa-collab/server.py"),
        ]

        for server_name, server_path in servers:
            full_path = self.base_dir / server_path
            if full_path.exists():
                try:
                    # Import MCP client
                    import sys
                    sys.path.insert(0, str(self.cli_dir))
                    from mcp_client import MCPClient

                    client = MCPClient(['python3', str(full_path)])
                    client.start()
                    tools = client.list_tools()
                    client.stop()

                    print(f"  📦 {server_name}")
                    for tool in tools:
                        print(f"     • {tool['name']}: {tool.get('description', 'No description')}")
                except Exception as e:
                    print(f"  ❌ {server_name}: {e}")
            else:
                print(f"  ⚠️  {server_name}: Not found")

        return 0

    def cmd_mcp_call(self, args):
        """Call an MCP tool."""
        if not args.tool:
            print("❌ Error: --tool required")
            return 1

        # Import MCP client
        import sys
        import json
        sys.path.insert(0, str(self.cli_dir))
        from mcp_client import MCPClient

        # Map tools to servers
        tool_server_map = {
            'qa_compute_triangle': 'qa_mcp_servers/qa-right-triangle/server.py',
            'qa_scan_resonance': 'qa_mcp_servers/qa-resonance/server.py',
            'qa_optimize_hgd': 'qa_mcp_servers/qa-hgd-optimizer/server.py'
        }

        server_path = tool_server_map.get(args.tool)
        if not server_path:
            print(f"❌ Unknown tool: {args.tool}")
            return 1

        full_path = self.base_dir / server_path
        if not full_path.exists():
            print(f"❌ Server not found: {server_path}")
            return 1

        # Parse arguments
        arguments = json.loads(args.args) if args.args else {}

        # Call tool
        try:
            with MCPClient(['python3', str(full_path)]) as client:
                result = client.call_tool(args.tool, arguments)
                print(json.dumps(result, indent=2))
            return 0
        except Exception as e:
            print(f"❌ Error calling tool: {e}")
            return 1

    def cmd_status(self, args):
        """Show QA Lab status."""
        print("🏗️  QA Bob-iverse Autonomic Research Lab v4.0")
        print()

        # Check environment
        venv_exists = (self.base_dir / "qa_venv").exists()
        print(f"Environment: {'✅' if venv_exists else '❌'} Virtual environment")

        # Check key directories
        dirs_to_check = ["tasks", "projects", "artifacts", "logs"]
        for dir_name in dirs_to_check:
            exists = (self.base_dir / dir_name).exists()
            print(f"{dir_name.capitalize()}: {'✅' if exists else '❌'} Directory")

        # Check SpecLock
        try:
            result = subprocess.run(
                [str(self.cli_dir / "speclock.sh")],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            speclock_ok = result.returncode == 0
            print(f"SpecLock: {'✅' if speclock_ok else '❌'} Integrity verified")
        except:
            print("SpecLock: ❌ Unable to verify")

        # Show recent activity
        print()
        print("Recent Activity:")
        log_dir = self.base_dir / "logs"
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), reverse=True)[:3]
            for log_file in log_files:
                print(f"  📄 {log_file.name}")
        else:
            print("  📄 No logs yet")

    def cmd_help(self, args):
        """Show help information."""
        print("QA Bob-iverse Autonomic Research Lab v4.0")
        print()
        print("Available commands:")
        print("  init         - Initialize QA Lab environment")
        print("  test         - Run QA invariant tests")
        print("  docs         - Build documentation")
        print("  viz          - Generate visualizations")
        print("  meta         - Run full meta-pipeline")
        print("  scout        - Mine for new tasks")
        print("  prioritize   - Compute task priorities")
        print("  plan         - Create execution plans")
        print("  dispatch     - Assign tasks to agents")
        print("  review       - Validate completed work")
        print("  archive      - Update knowledge base")
        print("  loop         - Run full agent orchestration")
        print("  speclock     - Verify SpecLock integrity")
        print("  mcp-test     - Test MCP integration")
        print("  mcp-list     - List all MCP servers and tools")
        print("  mcp-call     - Call an MCP tool")
        print("  status       - Show QA Lab status")
        print("  help         - Show this help")
        print()
        print("For more information, see docs/ or run 'make help'")

def main():
    cli = QACLI()

    parser = argparse.ArgumentParser(
        description="QA Bob-iverse CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  qa init                    # Initialize environment
  qa scout                   # Find new tasks
  qa loop                    # Run full agent orchestration
  qa status                  # Check system status
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add subcommands
    commands = [
        ("init", "Initialize QA Lab environment"),
        ("test", "Run QA tests"),
        ("docs", "Build documentation"),
        ("viz", "Generate visualizations"),
        ("meta", "Run meta-pipeline"),
        ("scout", "Run Scout agent"),
        ("prioritize", "Run Prioritizer agent"),
        ("plan", "Run Planner agent"),
        ("dispatch", "Run Dispatcher agent"),
        ("builder", "Run Agent Builder agent"),
        ("executor", "Run Executor agent"),
        ("inject", "Inject a task into inbox"),
        ("review", "Run Reviewer agent"),
        ("archive", "Run Archivist agent"),
        ("loop", "Run agent orchestration loop"),
        ("speclock", "Verify SpecLock"),
        ("mcp-test", "Test MCP integration"),
        ("mcp-list", "List MCP servers and tools"),
        ("mcp-call", "Call an MCP tool"),
        ("status", "Show system status"),
        ("help", "Show help"),
    ]

    for cmd_name, cmd_help in commands:
        subparser = subparsers.add_parser(cmd_name, help=cmd_help)
        # Add common args if needed
        if cmd_name in ["scout", "prioritize", "plan", "dispatch"]:
            subparser.add_argument("--dry-run", action="store_true",
                                 help="Show what would be done without executing")
        if cmd_name == "mcp-call":
            subparser.add_argument("--tool", required=True,
                                 help="Tool name to call (e.g., qa_compute_triangle)")
            subparser.add_argument("--args", default="{}",
                                 help='JSON arguments for tool call (e.g., \'{"b": 1.0, "e": 1.0}\')')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Route to appropriate handler
    handler_name = f"cmd_{args.command.replace('-', '_')}"
    if hasattr(cli, handler_name):
        return getattr(cli, handler_name)(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
