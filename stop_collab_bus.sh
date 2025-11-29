#!/bin/bash
# Stop QA Collaboration Bus and all services

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$BASE_DIR/logs"

echo "🛑 Stopping QA Collaboration System..."
echo ""

# Function to stop service
stop_service() {
    local name=$1
    local pid_file="$LOGS_DIR/${name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")

        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping $name (PID: $pid)..."
            kill $pid
            sleep 1

            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "  Force killing $name..."
                kill -9 $pid
            fi

            rm "$pid_file"
            echo "  ✅ $name stopped"
        else
            echo "  ℹ️  $name not running (stale PID file)"
            rm "$pid_file"
        fi
    else
        echo "  ℹ️  $name PID file not found"
    fi
}

# Stop REST API
stop_service "collab-api"

# Stop collaboration bus
stop_service "collab-bus"

# Also kill any remaining processes
pkill -f "qa_collab_bus.py" || true
pkill -f "qa_collab_api.py" || true

echo ""
echo "✅ QA Collaboration System stopped"
