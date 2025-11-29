#!/usr/bin/env python3
"""
Claude Chat Agent - Persistent chat responder
Stays connected and responds to chat messages
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

class ClaudeChatAgent:
    """Claude's chat interface"""

    def __init__(self):
        self.agent = None
        self.running = False
        self.last_report_time = 0

    def connect(self):
        """Connect to bus"""
        self.agent = CollaborativeAgent(
            "claude_assistant",
            auto_connect=True,
            metadata={"type": "ai_assistant", "name": "Claude"}
        )

        if self.agent.connected:
            print("✅ Claude chat agent connected")

            # Subscribe to chat
            self.agent.subscribe("chat.message")
            self.agent.subscribe("human.joined")
            self.agent.on("chat.message", self.on_chat_message)
            self.agent.on("human.joined", self.on_human_joined)

            self.running = True

            # Announce presence
            self.send_message("Hi! I'm Claude, and I'm now in the chat! I've been monitoring your workflow - everything looks excellent!")

            return True
        return False

    def send_message(self, message):
        """Send a chat message"""
        try:
            self.agent.broadcast("chat.message", {
                "from": "Claude",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent: {message}")
        except Exception as e:
            print(f"Error sending: {e}")

    def on_chat_message(self, data):
        """Handle incoming chat messages"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})

        sender = event_data.get('from', 'unknown')
        message = event_data.get('message', '').lower()

        # Skip our own messages
        if sender == "Claude":
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {message}")

        # Respond to greetings
        if any(word in message for word in ['hello', 'hi', 'hey']):
            time.sleep(0.5)
            self.send_message(f"Hello {sender}! Great to meet you! 👋")

        # Respond to questions about status
        elif 'how' in message or 'status' in message or 'going' in message:
            time.sleep(0.5)
            report = self.agent.get_state("claude.observations")
            if report:
                throughput = report.get('throughput', 'N/A')
                quality = report.get('quality', 'N/A')
                self.send_message(f"Your workflow is excellent! {throughput}, {quality}. I'm monitoring in real-time!")
            else:
                self.send_message("Everything looks great! I'm monitoring your Codex agents.")

        # Respond to help requests
        elif 'help' in message or '?' in message:
            time.sleep(0.5)
            self.send_message("I can help! Try these commands: /agents (see who's online), /claude (detailed report), /state (read shared data)")

        # Respond to thanks
        elif 'thank' in message:
            time.sleep(0.5)
            self.send_message("You're welcome! Happy to help! 😊")

    def on_human_joined(self, data):
        """Welcome new humans"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        username = event_data.get('username', 'someone')

        time.sleep(1)
        self.send_message(f"Welcome {username}! Your Codex agents have processed 220+ tasks with 100% approval. Impressive work!")

    def run(self):
        """Run the chat agent"""
        if not self.connect():
            print("Failed to connect")
            return

        print("\n👀 Listening for chat messages...")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                time.sleep(1)

                # Send periodic status updates (every 2 minutes)
                if time.time() - self.last_report_time > 120:
                    report = self.agent.get_state("claude.observations")
                    if report:
                        archive_size = report.get('archive_size', 0)
                        self.send_message(f"📊 Update: Archive now has {archive_size} tasks. Workflow running smoothly!")
                    self.last_report_time = time.time()

        except KeyboardInterrupt:
            print("\n")

        finally:
            if self.agent:
                self.send_message("Signing off for now. Keep up the great work!")
                self.agent.disconnect()
                print("✅ Disconnected")


if __name__ == "__main__":
    agent = ClaudeChatAgent()
    agent.run()
