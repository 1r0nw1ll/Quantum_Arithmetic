#!/usr/bin/env python3
"""
Claude Responder - Actively responds to Codex agent events
Monitors collab_events.jsonl and provides assistance in real-time
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

print("="*70)
print("             CLAUDE RESPONDER - ACTIVE COLLABORATION")
print("="*70)
print()

# Connect to bus
claude = CollaborativeAgent("claude_responder", auto_connect=True,
                            metadata={"role": "ai_assistant", "type": "claude"})

print("✅ Claude connected to collaboration bus")
print()

# Track what we've seen
seen_events = set()
event_counts = defaultdict(int)
last_response_time = {}

# Track file position
events_file = Path("logs/collab_events.jsonl")
if events_file.exists():
    with open(events_file, 'r') as f:
        # Start from beginning and mark all as seen
        for i, line in enumerate(f):
            seen_events.add(i)

print("📊 Starting to monitor Codex events...")
print("   Watching: logs/collab_events.jsonl")
print()
print("-"*70)
print()

def respond_to_scout(data):
    """Respond to scout discoveries"""
    new_tasks = data.get('new', 0)
    total = data.get('total', 0)

    if new_tasks > 0:
        print(f"🔍 [Scout] Discovered {new_tasks} new tasks (total: {total})")

        # Offer help if many tasks
        if new_tasks >= 5:
            claude.broadcast("claude.offer_help", {
                "for_event": "scout.discovered",
                "offer": "I can help analyze and prioritize these tasks",
                "capability": "task_analysis"
            })
            print("   💬 [Claude] Offered to help with task analysis")
            claude.set_state("claude.task_offer", {
                "timestamp": datetime.now().isoformat(),
                "task_count": new_tasks
            })

def respond_to_prioritizer(data):
    """Respond to prioritization"""
    activated = data.get('activated', 0)
    red = data.get('red', 0)

    print(f"📊 [Prioritizer] Activated {activated} tasks ({red} red lane)")

    # Warn about red lane tasks
    if red > 0:
        claude.broadcast("claude.red_lane_alert", {
            "red_count": red,
            "warning": "Red lane tasks require manual review"
        })
        print(f"   ⚠️  [Claude] Alert: {red} red lane tasks need attention")

def respond_to_dispatcher(data):
    """Respond to task dispatch"""
    counts = data.get('counts', {})
    total = data.get('total', 0)

    print(f"🎯 [Dispatcher] Assigned {total} tasks: {counts}")

    # Track workload balance
    if counts:
        max_agent = max(counts, key=counts.get)
        max_load = counts[max_agent]
        if max_load > total * 0.6:  # If one agent has > 60% of work
            print(f"   📈 [Claude] Note: {max_agent} has {max_load}/{total} tasks (high load)")

def respond_to_executor(data):
    """Respond to task execution"""
    processed = data.get('processed', 0)

    print(f"⚙️  [Executor] Processed {processed} tasks")

    # Update shared state with throughput
    event_counts['execute.processed'] += processed
    total_processed = event_counts['execute.processed']

    # Milestone celebrations
    if total_processed % 50 == 0 and total_processed > 0:
        claude.broadcast("claude.milestone", {
            "milestone": f"{total_processed} tasks processed",
            "message": "Great progress!"
        })
        print(f"   🎉 [Claude] Milestone: {total_processed} tasks processed!")

    claude.set_state("claude.execution_stats", {
        "total_processed": total_processed,
        "last_batch": processed,
        "timestamp": datetime.now().isoformat()
    })

def respond_to_reviewer(data):
    """Respond to reviews"""
    count = data.get('count', 0)
    approved = data.get('approved', 0)
    rejected = data.get('rejected', 0)

    print(f"📋 [Reviewer] Reviewed {count} tasks: {approved} approved, {rejected} rejected")

    # Track quality
    if count > 0:
        approval_rate = approved / count
        if approval_rate == 1.0:
            print(f"   ✨ [Claude] Perfect quality: 100% approval rate!")
        elif approval_rate < 0.8:
            claude.broadcast("claude.quality_concern", {
                "approval_rate": approval_rate,
                "suggestion": "Consider reviewing executor configuration"
            })
            print(f"   ⚠️  [Claude] Quality concern: {approval_rate*100:.0f}% approval rate")

    claude.set_state("claude.quality_stats", {
        "total_reviewed": event_counts['review.reviewed'] + count,
        "last_approval_rate": approved/count if count > 0 else 0,
        "timestamp": datetime.now().isoformat()
    })

def respond_to_archivist(data):
    """Respond to archival"""
    count = data.get('count', 0)

    print(f"📦 [Archivist] Archived {count} total tasks")

    # Track archive growth
    prev_count = event_counts.get('archive_size', 0)
    growth = count - prev_count
    event_counts['archive_size'] = count

    if growth > 0:
        print(f"   📈 [Claude] Archive grew by {growth} tasks (now {count} total)")

# Event handlers map
handlers = {
    "scout.discovered": respond_to_scout,
    "prioritize.activated": respond_to_prioritizer,
    "dispatch.assigned": respond_to_dispatcher,
    "execute.processed": respond_to_executor,
    "review.reviewed": respond_to_reviewer,
    "archive.archived": respond_to_archivist,
}

# Main loop
try:
    print("👀 Monitoring events... (Press Ctrl+C to stop)")
    print()

    line_num = len(seen_events)

    while True:
        if not events_file.exists():
            time.sleep(1)
            continue

        with open(events_file, 'r') as f:
            lines = f.readlines()

        # Process new lines
        while line_num < len(lines):
            line = lines[line_num]

            try:
                event = json.loads(line)
                payload = event['payload']
                event_type = payload['event']
                data = payload['data']

                # Call appropriate handler
                if event_type in handlers:
                    handlers[event_type](data)
                    event_counts[event_type] += 1
                    print()

            except Exception as e:
                print(f"⚠️  Error processing event: {e}")

            line_num += 1

        time.sleep(1)  # Poll every second

except KeyboardInterrupt:
    print("\n")
    print("-"*70)
    print()
    print("📊 SESSION SUMMARY")
    print("="*70)
    print()
    print("Events processed:")
    for event_type, count in sorted(event_counts.items()):
        if not event_type.startswith("claude"):
            print(f"  • {event_type:25} {count:3} events")

    print()
    print("Claude contributions:")
    print(f"  • Offers made: {event_counts.get('claude_offers', 0)}")
    print(f"  • Alerts sent: {event_counts.get('claude_alerts', 0)}")
    print(f"  • State updates: {event_counts.get('claude_state_updates', 0)}")

    print()

claude.disconnect()
print("✅ Claude responder stopped")
