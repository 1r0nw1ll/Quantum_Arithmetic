#!/bin/bash
# Watch for events in real-time

echo "👀 Watching for Codex events..."
echo "Press Ctrl+C to stop"
echo ""

# Follow the listener log and also the collab events if they exist
if [ -f logs/claude_listener.log ]; then
    tail -f logs/claude_listener.log
elif [ -f logs/collab_events.jsonl ]; then
    tail -f logs/collab_events.jsonl | while read line; do
        echo "📥 Event: $line"
    done
else
    echo "No events yet. Waiting..."
    sleep 2
    tail -f logs/claude_listener.log 2>/dev/null || tail -f logs/collab-bus.log
fi
