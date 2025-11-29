#!/usr/bin/env python3
"""
Collaborative Chat Interface
Real-time CLI chat to collaborate with all agents (Codex, Claude, etc.)
"""

import sys
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from collections import deque

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

console = Console()

class CollabChat:
    """Interactive chat interface for agent collaboration"""

    def __init__(self, username="player2"):
        self.username = username
        self.agent = None
        self.running = False
        self.messages = deque(maxlen=50)  # Keep last 50 messages
        self.events = deque(maxlen=20)    # Keep last 20 events
        self.status = "Connecting..."
        self.agents_online = []

        # Prompt session for input
        self.session = PromptSession(history=InMemoryHistory())

    def connect(self):
        """Connect to collaboration bus"""
        try:
            self.agent = CollaborativeAgent(
                f"human_{self.username}",
                auto_connect=True,
                metadata={"type": "human", "username": self.username}
            )

            if self.agent.connected:
                self.status = "Connected ✓"
                self.running = True

                # Subscribe to all events
                self.agent.subscribe("*")

                # Register event handler
                self.agent.on("*", self.on_event)

                # Add welcome message
                self.add_message("system", "Connected to collaboration bus!", "green")
                self.add_message("system", f"You are: {self.username}", "cyan")
                self.add_message("system", "Type /help for commands", "yellow")

                # Broadcast presence
                self.agent.broadcast("human.joined", {
                    "username": self.username,
                    "timestamp": datetime.now().isoformat()
                })

                return True
            else:
                self.status = "Connection failed"
                return False

        except Exception as e:
            self.status = f"Error: {e}"
            return False

    def on_event(self, data):
        """Handle incoming events"""
        try:
            topic = data.get('topic', 'unknown')
            payload = data.get('payload', {})
            timestamp = data.get('timestamp', '')

            # Parse event
            agent_name = payload.get('agent_name', 'unknown')
            event_data = payload.get('data', {})

            # Skip our own events
            if agent_name == f"human_{self.username}":
                return

            # Add to events list
            event_summary = f"[{topic}] {agent_name}"
            self.events.append({
                'time': timestamp[-8:] if len(timestamp) > 8 else timestamp,
                'summary': event_summary,
                'data': event_data
            })

            # Special handling for chat messages
            if topic == "chat.message":
                sender = event_data.get('from', agent_name)
                message = event_data.get('message', '')
                self.add_message(sender, message)

            elif topic == "human.joined":
                username = event_data.get('username', 'someone')
                self.add_message("system", f"{username} joined the chat", "green")

            elif topic == "claude.analysis_complete":
                self.add_message("Claude", "Analysis complete! Check shared state.", "blue")

            # Update agents list
            self.update_agents_list()

        except Exception as e:
            self.add_message("system", f"Event error: {e}", "red")

    def add_message(self, sender, message, color="white"):
        """Add a message to the chat"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append({
            'time': timestamp,
            'sender': sender,
            'message': message,
            'color': color
        })

    def update_agents_list(self):
        """Update list of online agents"""
        if self.agent and self.agent.connected:
            try:
                agents = self.agent.query_agents()
                self.agents_online = [a['name'] for a in agents]
            except:
                pass

    def send_message(self, message):
        """Send a chat message to all agents"""
        if not self.agent or not self.agent.connected:
            self.add_message("system", "Not connected!", "red")
            return

        try:
            self.agent.broadcast("chat.message", {
                "from": self.username,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

            # Add to local chat
            self.add_message(self.username, message, "cyan")

        except Exception as e:
            self.add_message("system", f"Send failed: {e}", "red")

    def handle_command(self, text):
        """Handle slash commands"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self.show_help()

        elif cmd == "/status":
            self.update_agents_list()
            self.add_message("system", f"Status: {self.status}", "yellow")
            self.add_message("system", f"Agents online: {len(self.agents_online)}", "yellow")
            for agent in self.agents_online:
                self.add_message("system", f"  • {agent}", "yellow")

        elif cmd == "/state":
            if args:
                value = self.agent.get_state(args)
                self.add_message("system", f"{args} = {value}", "yellow")
            else:
                self.add_message("system", "Usage: /state <key>", "red")

        elif cmd == "/set":
            if args:
                try:
                    key, value = args.split(" ", 1)
                    self.agent.set_state(key, value)
                    self.add_message("system", f"Set {key} = {value}", "green")
                except:
                    self.add_message("system", "Usage: /set <key> <value>", "red")
            else:
                self.add_message("system", "Usage: /set <key> <value>", "red")

        elif cmd == "/broadcast":
            if args:
                try:
                    # Parse: /broadcast event_type message
                    event_type, message = args.split(" ", 1)
                    self.agent.broadcast(event_type, {
                        "from": self.username,
                        "message": message
                    })
                    self.add_message("system", f"Broadcasted: {event_type}", "green")
                except:
                    self.add_message("system", "Usage: /broadcast <event_type> <message>", "red")
            else:
                self.add_message("system", "Usage: /broadcast <event_type> <message>", "red")

        elif cmd == "/agents":
            self.update_agents_list()
            self.add_message("system", f"Active agents ({len(self.agents_online)}):", "yellow")
            for agent in self.agents_online:
                self.add_message("system", f"  • {agent}", "yellow")

        elif cmd == "/clear":
            self.messages.clear()
            self.add_message("system", "Chat cleared", "green")

        elif cmd == "/quit" or cmd == "/exit":
            self.running = False
            self.add_message("system", "Disconnecting...", "yellow")

        else:
            self.add_message("system", f"Unknown command: {cmd}", "red")
            self.add_message("system", "Type /help for commands", "yellow")

    def show_help(self):
        """Show help message"""
        help_text = [
            ("Commands:", "yellow"),
            ("  /help          - Show this help", "white"),
            ("  /status        - Show connection status", "white"),
            ("  /agents        - List active agents", "white"),
            ("  /state <key>   - Get shared state value", "white"),
            ("  /set <key> <v> - Set shared state value", "white"),
            ("  /broadcast <e> - Broadcast custom event", "white"),
            ("  /clear         - Clear chat history", "white"),
            ("  /quit          - Exit chat", "white"),
            ("", "white"),
            ("To chat: Just type your message and press Enter", "green"),
        ]

        for msg, color in help_text:
            self.add_message("system", msg, color)

    def build_layout(self):
        """Build the UI layout"""
        layout = Layout()

        # Header
        header = Panel(
            f"[bold cyan]Collaborative Agent Chat[/bold cyan]  |  "
            f"User: [yellow]{self.username}[/yellow]  |  "
            f"Status: [green]{self.status}[/green]  |  "
            f"Agents: {len(self.agents_online)}",
            box=box.DOUBLE
        )

        # Messages panel
        messages_text = Text()
        for msg in list(self.messages)[-20:]:  # Show last 20
            messages_text.append(f"[{msg['time']}] ", style="dim")
            messages_text.append(f"{msg['sender']}: ", style=f"bold {msg['color']}")
            messages_text.append(f"{msg['message']}\n", style=msg['color'])

        messages_panel = Panel(
            messages_text,
            title="[bold]Chat Messages[/bold]",
            border_style="cyan",
            box=box.ROUNDED
        )

        # Events panel
        events_table = Table(show_header=True, box=box.SIMPLE)
        events_table.add_column("Time", style="dim", width=8)
        events_table.add_column("Event", style="yellow")

        for event in list(self.events)[-10:]:  # Show last 10
            events_table.add_row(event['time'], event['summary'])

        events_panel = Panel(
            events_table,
            title="[bold]Recent Events[/bold]",
            border_style="magenta",
            box=box.ROUNDED
        )

        # Agents panel
        agents_text = Text()
        for agent in self.agents_online:
            agents_text.append(f"● {agent}\n", style="green")

        agents_panel = Panel(
            agents_text if self.agents_online else "[dim]No agents online[/dim]",
            title="[bold]Online Agents[/bold]",
            border_style="green",
            box=box.ROUNDED
        )

        # Layout structure
        layout.split_column(
            Layout(header, size=3),
            Layout(name="main"),
            Layout(name="bottom", size=12)
        )

        layout["main"].split_row(
            Layout(messages_panel, name="messages"),
            Layout(name="sidebar", ratio=1)
        )

        layout["sidebar"].split_column(
            Layout(events_panel, name="events"),
            Layout(agents_panel, name="agents")
        )

        layout["bottom"] = Panel(
            "[dim]Type your message and press Enter. Use /help for commands.[/dim]",
            title="[bold]Input[/bold]",
            border_style="blue"
        )

        return layout

    def run(self):
        """Run the chat interface"""
        if not self.connect():
            console.print(f"[red]Failed to connect: {self.status}[/red]")
            return

        console.clear()
        console.print(Panel(
            "[bold green]Welcome to Collaborative Agent Chat![/bold green]\n"
            "You can now chat with all agents (Codex, Claude, etc.) in real-time.\n"
            "Type /help for commands.",
            title="QA Collaboration Chat",
            border_style="green"
        ))
        console.print()

        try:
            while self.running:
                # Show current state
                layout = self.build_layout()
                console.clear()
                console.print(layout)

                # Get user input
                try:
                    user_input = self.session.prompt("\n> ").strip()

                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        self.handle_command(user_input)
                    else:
                        self.send_message(user_input)

                    time.sleep(0.1)  # Brief pause to show update

                except KeyboardInterrupt:
                    self.running = False
                    break
                except EOFError:
                    self.running = False
                    break

        finally:
            if self.agent:
                self.agent.broadcast("human.left", {
                    "username": self.username,
                    "timestamp": datetime.now().isoformat()
                })
                self.agent.disconnect()

            console.print("\n[yellow]Disconnected from collaboration chat.[/yellow]")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Collaborative Agent Chat')
    parser.add_argument('--username', default='player2', help='Your username')

    args = parser.parse_args()

    chat = CollabChat(username=args.username)
    chat.run()


if __name__ == "__main__":
    main()
