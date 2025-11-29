#!/usr/bin/env python3
"""
Listen for events from Codex agents
Subscribes to all Codex agent events and displays them in real-time
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

print("="*60)
print("LISTENING FOR CODEX AGENT EVENTS")
print("="*60)
print()

# Create listener agent
listener = CollaborativeAgent("claude_listener", auto_connect=True)

# Subscribe to all Codex agent events
codex_events = [
    "scout.discovered",
    "prioritize.activated",
    "dispatch.assigned",
    "execute.processed",
    "review.reviewed",
    "archive.archived",
]

print("📡 Subscribing to Codex events:")
for event in codex_events:
    listener.subscribe(event)
    print(f"   • {event}")

# Also subscribe to wildcard for any other events
listener.subscribe("*")

print()
print("✅ Listening... (Press Ctrl+C to stop)")
print()
print("-" * 60)
print()

# Event counter
event_count = 0

def on_event(data):
    global event_count
    event_count += 1

    topic = data.get('topic', 'unknown')
    payload = data.get('payload', {})
    timestamp = data.get('timestamp', '')

    agent_name = payload.get('agent_name', 'unknown')
    event_data = payload.get('data', {})

    print(f"[{timestamp}] Event #{event_count}")
    print(f"  Topic:      {topic}")
    print(f"  From:       {agent_name}")
    print(f"  Data:       {event_data}")
    print()

# Register handlers for all Codex events
for event in codex_events:
    listener.on(event, on_event)

# Also handle wildcard
listener.on("*", on_event)

# Show agent status periodically
try:
    last_status = time.time()

    while True:
        time.sleep(1)

        # Show status every 30 seconds
        if time.time() - last_status > 30:
            agents = listener.query_agents()
            print(f"\n[STATUS] Active agents: {len(agents)}, Events received: {event_count}\n")
            last_status = time.time()

except KeyboardInterrupt:
    print("\n")
    print("-" * 60)
    print(f"Total events received: {event_count}")
    print()

listener.disconnect()
print("✅ Listener stopped")
