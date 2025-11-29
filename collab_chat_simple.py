#!/usr/bin/env python3
"""
Simple Collaborative Chat Interface
Real-time CLI chat to collaborate with all agents
"""

import sys
import threading
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

class SimpleChat:
    """Simple streaming chat interface"""

    def __init__(self, username="player2"):
        self.username = username
        self.agent = None
        self.running = False

    def connect(self):
        """Connect to collaboration bus"""
        try:
            print(f"🔌 Connecting as {self.username}...")
            self.agent = CollaborativeAgent(
                f"human_{self.username}",
                auto_connect=True,
                metadata={"type": "human", "username": self.username}
            )

            if self.agent.connected:
                print(f"✅ Connected to collaboration bus!")
                print(f"👤 You are: {self.username}")
                print()
                self.running = True

                # Subscribe to events
                self.agent.subscribe("chat.message")
                self.agent.subscribe("human.joined")
                self.agent.subscribe("human.left")
                self.agent.subscribe("claude.analysis_complete")
                self.agent.subscribe("execute.help_needed")

                # Register handlers
                self.agent.on("chat.message", self.on_chat_message)
                self.agent.on("human.joined", self.on_user_joined)
                self.agent.on("human.left", self.on_user_left)
                self.agent.on("claude.analysis_complete", self.on_claude_message)

                # Announce presence
                self.agent.broadcast("human.joined", {
                    "username": self.username,
                    "timestamp": datetime.now().isoformat()
                })

                return True
            else:
                print("❌ Connection failed")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def on_chat_message(self, data):
        """Handle chat messages"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})

        sender = event_data.get('from', 'unknown')
        message = event_data.get('message', '')

        # Skip our own messages
        if sender == self.username:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\r\033[K[{timestamp}] {sender}: {message}")
        print("> ", end="", flush=True)

    def on_user_joined(self, data):
        """Handle user join"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        username = event_data.get('username', 'someone')

        if username != self.username:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\r\033[K[{timestamp}] 🟢 {username} joined the chat")
            print("> ", end="", flush=True)

    def on_user_left(self, data):
        """Handle user leave"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        username = event_data.get('username', 'someone')

        if username != self.username:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\r\033[K[{timestamp}] 🔴 {username} left the chat")
            print("> ", end="", flush=True)

    def on_claude_message(self, data):
        """Handle Claude's messages"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})

        message = event_data.get('message', 'Analysis complete')
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\r\033[K[{timestamp}] 🤖 Claude: {message}")
        print("> ", end="", flush=True)

    def send_message(self, message):
        """Send a chat message"""
        if not self.agent or not self.agent.connected:
            print("❌ Not connected!")
            return

        try:
            self.agent.broadcast("chat.message", {
                "from": self.username,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"❌ Send failed: {e}")

    def handle_command(self, text):
        """Handle slash commands"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self.show_help()

        elif cmd == "/status":
            agents = self.agent.query_agents()
            print(f"📊 Status: Connected")
            print(f"👥 Agents online: {len(agents)}")
            for agent in agents:
                print(f"   • {agent['name']}")

        elif cmd == "/state":
            if args:
                value = self.agent.get_state(args)
                print(f"📋 {args} = {value}")
            else:
                print("Usage: /state <key>")

        elif cmd == "/set":
            if args:
                try:
                    key, value = args.split(" ", 1)
                    self.agent.set_state(key, value)
                    print(f"✅ Set {key} = {value}")
                except:
                    print("Usage: /set <key> <value>")
            else:
                print("Usage: /set <key> <value>")

        elif cmd == "/broadcast":
            if args:
                try:
                    event_type, message = args.split(" ", 1)
                    self.agent.broadcast(event_type, {
                        "from": self.username,
                        "message": message
                    })
                    print(f"✅ Broadcasted: {event_type}")
                except:
                    print("Usage: /broadcast <event_type> <message>")
            else:
                print("Usage: /broadcast <event_type> <message>")

        elif cmd == "/agents":
            agents = self.agent.query_agents()
            print(f"👥 Active agents ({len(agents)}):")
            for agent in agents:
                role = agent.get('metadata', {}).get('role', 'agent')
                print(f"   • {agent['name']} ({role})")

        elif cmd == "/claude":
            # Get Claude's latest observations
            report = self.agent.get_state("claude.detailed_report")
            if report:
                print("\n📊 Claude's Latest Report:")
                print(f"Status: {report.get('status', 'unknown')}")
                metrics = report.get('observations', {}).get('quality_metrics', {})
                print(f"Quality: {metrics.get('approval_rate', 'N/A')}")
                print(f"Throughput: {metrics.get('throughput', 'N/A')}")
                print(f"Archive: {metrics.get('archive_size', 'N/A')} tasks")
            else:
                print("No report available yet")

        elif cmd == "/quit" or cmd == "/exit":
            self.running = False

        else:
            print(f"❌ Unknown command: {cmd}")
            print("Type /help for commands")

    def show_help(self):
        """Show help message"""
        print("\n" + "="*60)
        print("COLLABORATIVE CHAT COMMANDS")
        print("="*60)
        print()
        print("Chat:")
        print("  Just type your message and press Enter")
        print()
        print("Commands:")
        print("  /help            - Show this help")
        print("  /status          - Show connection status")
        print("  /agents          - List active agents")
        print("  /state <key>     - Get shared state value")
        print("  /set <key> <val> - Set shared state value")
        print("  /broadcast <evt> - Broadcast custom event")
        print("  /claude          - Get Claude's latest report")
        print("  /quit            - Exit chat")
        print()
        print("Examples:")
        print("  > Hello everyone!")
        print("  > /agents")
        print("  > /state claude.status")
        print("  > /broadcast help_needed Can someone help with task X?")
        print()
        print("="*60)
        print()

    def run(self):
        """Run the chat"""
        if not self.connect():
            return

        print("="*60)
        print("🤝 COLLABORATIVE AGENT CHAT")
        print("="*60)
        print()
        print("You can now chat with all agents in real-time!")
        print("Type /help for commands, /quit to exit")
        print()
        print("-"*60)
        print()

        try:
            while self.running:
                try:
                    user_input = input("> ").strip()

                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        self.handle_command(user_input)
                    else:
                        self.send_message(user_input)
                        # Show our own message
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"\r\033[K[{timestamp}] {self.username}: {user_input}")

                except KeyboardInterrupt:
                    print("\n")
                    self.running = False
                    break
                except EOFError:
                    print("\n")
                    self.running = False
                    break

        finally:
            if self.agent:
                print("\n👋 Leaving chat...")
                self.agent.broadcast("human.left", {
                    "username": self.username,
                    "timestamp": datetime.now().isoformat()
                })
                self.agent.disconnect()
                print("✅ Disconnected")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Collaborative Agent Chat (Simple)')
    parser.add_argument('--username', default='player2', help='Your username')

    args = parser.parse_args()

    chat = SimpleChat(username=args.username)
    chat.run()


if __name__ == "__main__":
    main()
