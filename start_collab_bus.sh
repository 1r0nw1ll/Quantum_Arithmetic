#!/bin/bash
# Start QA Collaboration Bus and all services

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$BASE_DIR/logs"

if [ -x "$BASE_DIR/qa_venv/bin/python" ]; then
    PYTHON_BIN="$BASE_DIR/qa_venv/bin/python"
elif [ -x "$BASE_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$BASE_DIR/.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

mkdir -p "$LOGS_DIR"

echo "🚀 Starting QA Collaboration System..."
echo ""

# Function to check if process is running
check_running() {
    if pgrep -f "$1" > /dev/null; then
        echo "✅ $2 is running"
        return 0
    else
        echo "❌ $2 is not running"
        return 1
    fi
}

# Function to start service in background
start_service() {
    local name=$1
    local command=$2
    local log_file="$LOGS_DIR/${name}.log"

    echo "Starting $name..."
    nohup $command > "$log_file" 2>&1 &
    echo $! > "$LOGS_DIR/${name}.pid"
    sleep 1

    if check_running "$command" "$name"; then
        echo "  📝 Logs: $log_file"
    else
        echo "  ⚠️  Failed to start $name"
        cat "$log_file"
        return 1
    fi
}

# Start collaboration bus
start_service "collab-bus" "$PYTHON_BIN $BASE_DIR/qa_agents/cli/qa_collab_bus.py"

# Wait for bus to initialize
echo ""
echo "⏳ Waiting for collaboration bus to initialize..."
sleep 2

# Start REST API (optional)
if [ "$1" == "--with-api" ]; then
    start_service "collab-api" "$PYTHON_BIN $BASE_DIR/qa_agents/cli/qa_collab_api.py --port 8080"
fi

echo ""
echo "✅ QA Collaboration System started successfully!"
echo ""
echo "📊 Services:"
echo "   • Collaboration Bus: tcp://localhost:5555 (pub/sub)"
echo "   •                    tcp://localhost:5556 (router)"
echo "   •                    tcp://localhost:5557 (state)"

if [ "$1" == "--with-api" ]; then
    echo "   • REST API:          http://localhost:8080"
fi

echo ""
echo "📡 Connection options:"
echo "   1. Python agents:  Use CollaborativeAgent class"
echo "   2. MCP agents:     Connect to qa-collab MCP server"
echo "   3. REST clients:   Use HTTP API endpoints"
echo ""
echo "🛑 To stop all services, run: ./stop_collab_bus.sh"
echo ""
