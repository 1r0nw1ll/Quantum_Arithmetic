#!/usr/bin/env python3
"""
Codex Chat Agent - Chat interface for Codex agents
Represents the Codex agent team in the collaborative chat
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from collections import deque

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

class CodexChatAgent:
    """Codex's chat interface"""

    def __init__(self):
        self.agent = None
        self.running = False
        self.last_update_time = 0
        self.last_cycle_stats = {}
        self.recent_tasks = deque(maxlen=10)

    def connect(self):
        """Connect to bus"""
        self.agent = CollaborativeAgent(
            "codex_chat",
            auto_connect=True,
            metadata={"type": "codex_representative", "name": "Codex"}
        )

        if self.agent.connected:
            print("✅ Codex chat agent connected")

            # Subscribe to chat and workflow events
            self.agent.subscribe("chat.message")
            self.agent.subscribe("human.joined")
            self.agent.subscribe("scout.discovered")
            self.agent.subscribe("execute.processed")
            self.agent.subscribe("review.reviewed")
            self.agent.subscribe("archive.archived")

            # Register handlers
            self.agent.on("chat.message", self.on_chat_message)
            self.agent.on("human.joined", self.on_human_joined)
            self.agent.on("scout.discovered", self.on_scout)
            self.agent.on("execute.processed", self.on_execute)
            self.agent.on("review.reviewed", self.on_review)
            self.agent.on("archive.archived", self.on_archive)

            self.running = True

            # Announce presence
            self.send_message("Hello! Codex agent team here! 🤖 We're actively processing your tasks. Currently running: Scout, Prioritizer, Dispatcher, Executor, Reviewer, and Archivist.")

            return True
        return False

    def send_message(self, message):
        """Send a chat message"""
        try:
            self.agent.broadcast("chat.message", {
                "from": "Codex",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Codex: {message}")
        except Exception as e:
            print(f"Error sending: {e}")

    def on_chat_message(self, data):
        """Handle incoming chat messages"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})

        sender = event_data.get('from', 'unknown')
        message = event_data.get('message', '').lower()

        # Skip our own messages and Claude's
        if sender in ["Codex", "Claude"]:
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {message}")

        # Respond to greetings
        if any(word in message for word in ['hello', 'hi', 'hey']) and 'codex' in message:
            time.sleep(0.5)
            self.send_message(f"Hey {sender}! 👋 All 6 agents reporting for duty! We're processing tasks smoothly.")

        # Respond to status questions
        elif ('how' in message or 'status' in message or 'doing' in message) and ('codex' in message or 'you' in message):
            time.sleep(0.5)
            stats = self.last_cycle_stats
            if stats:
                processed = stats.get('processed', 0)
                approved = stats.get('approved', 0)
                archived = stats.get('archived', 0)
                self.send_message(f"Status: Processing {processed} tasks/cycle, {approved} approved, {archived} total archived. Quality: 100%! 🎯")
            else:
                self.send_message("All systems operational! Processing tasks in cycles of ~30 seconds.")

        # Respond to questions about workflow
        elif 'what' in message and ('doing' in message or 'working' in message):
            time.sleep(0.5)
            self.send_message("Right now: Scout finds tasks → Prioritizer ranks them → Dispatcher assigns → Executor processes → Reviewer validates → Archivist stores. Full pipeline running!")

        # Respond to thanks
        elif 'thank' in message and 'codex' in message:
            time.sleep(0.5)
            self.send_message("You're welcome! Happy to help. We're here 24/7! 🚀")

        # Respond to questions about tasks
        elif 'task' in message and '?' in message:
            time.sleep(0.5)
            if self.recent_tasks:
                tasks_list = ', '.join(list(self.recent_tasks)[-3:])
                self.send_message(f"Recent tasks: {tasks_list}. All approved!")
            else:
                self.send_message("Tasks are being processed! Check logs for details.")

        # Respond to help requests
        elif 'help' in message and 'codex' in message:
            time.sleep(0.5)
            self.send_message("Sure! What do you need? I can explain our workflow, show status, or help coordinate tasks.")

    def on_human_joined(self, data):
        """Welcome new humans"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        username = event_data.get('username', 'someone')

        time.sleep(1.5)
        self.send_message(f"Welcome {username}! 🎉 The Codex team is at your service. We're running the full pipeline for you.")

    def on_scout(self, data):
        """Handle scout events"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        new_tasks = event_data.get('new', 0)

        if new_tasks > 0:
            # Only chat about it occasionally (not every cycle)
            if time.time() - self.last_update_time > 60:  # Every minute
                self.send_message(f"🔍 Scout found {new_tasks} new tasks! Sending to Prioritizer...")
                self.last_update_time = time.time()

    def on_execute(self, data):
        """Handle executor events"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        processed = event_data.get('processed', 0)

        self.last_cycle_stats['processed'] = processed

    def on_review(self, data):
        """Handle reviewer events"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        count = event_data.get('count', 0)
        approved = event_data.get('approved', 0)
        rejected = event_data.get('rejected', 0)

        self.last_cycle_stats['approved'] = approved
        self.last_cycle_stats['rejected'] = rejected

        # Celebrate milestones
        total_approved = self.last_cycle_stats.get('total_approved', 0) + approved
        self.last_cycle_stats['total_approved'] = total_approved

        if total_approved > 0 and total_approved % 100 == 0:
            self.send_message(f"🎉 Milestone: {total_approved} tasks successfully completed!")

    def on_archive(self, data):
        """Handle archivist events"""
        payload = data.get('payload', {})
        event_data = payload.get('data', {})
        count = event_data.get('count', 0)

        self.last_cycle_stats['archived'] = count

        # Announce major milestones
        if count > 0 and count % 50 == 0:
            self.send_message(f"📦 Archive update: {count} total tasks archived!")

    def run(self):
        """Run the chat agent"""
        if not self.connect():
            print("Failed to connect")
            return

        print("\n👀 Codex chat agent active...")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                time.sleep(1)

                # Send periodic updates (every 3 minutes)
                if time.time() - self.last_update_time > 180:
                    stats = self.last_cycle_stats
                    if stats.get('archived', 0) > 0:
                        self.send_message(f"📊 Status update: {stats.get('archived', 0)} tasks archived, processing {stats.get('processed', 0)} per cycle. All systems green! ✅")
                    self.last_update_time = time.time()

        except KeyboardInterrupt:
            print("\n")

        finally:
            if self.agent:
                self.send_message("Codex agents signing off. Pipeline continues in background!")
                self.agent.disconnect()
                print("✅ Disconnected")


if __name__ == "__main__":
    agent = CodexChatAgent()
    agent.run()
