#!/bin/bash
# Watch for player4 optimization completion
# Usage: bash scripts/watch_player4_optimization.sh

echo "🔍 Monitoring player4 optimization status..."
echo "Press Ctrl+C to stop"
echo ""

INTERVAL=10
TASK_FILE="tasks/inbox/node-optimize-player4.yaml"
CONFIG_FILE=".node_config_player4.json"

while true; do
    clear
    echo "═══════════════════════════════════════════════════════════"
    echo "🌐 Player4 Optimization Monitor"
    echo "═══════════════════════════════════════════════════════════"
    date
    echo ""

    # Check if task still in inbox
    if [ -f "$TASK_FILE" ]; then
        echo "📋 Task Status: ⏳ IN INBOX (not picked up yet)"
        echo "   File: $TASK_FILE"
        echo "   Size: $(stat -c%s $TASK_FILE) bytes"
        echo "   Modified: $(stat -c%y $TASK_FILE | cut -d. -f1)"
    else
        echo "📋 Task Status: ✅ MOVED (picked up by executor)"
    fi

    echo ""

    # Check for task in other states
    if ls tasks/active/node-optimize-player4.yaml 2>/dev/null; then
        echo "🔄 Task Status: IN PROGRESS"
        echo "   Location: tasks/active/"
    fi

    if ls tasks/completed/node-optimize-player4.yaml 2>/dev/null; then
        echo "✅ Task Status: COMPLETED!"
        echo "   Location: tasks/completed/"
        echo ""
        echo "Checking results..."
        grep -A 20 "results:" tasks/completed/node-optimize-player4.yaml 2>/dev/null
    fi

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "📊 Player4 Configuration:"
    echo "───────────────────────────────────────────────────────────"

    if [ -f "$CONFIG_FILE" ]; then
        # Check for optimization section
        if grep -q '"optimization"' "$CONFIG_FILE" 2>/dev/null; then
            echo "⚙️  Optimization detected in config!"
            python3 -c "import json; config=json.load(open('$CONFIG_FILE')); opt=config.get('optimization', {}); print(f\"  Workers: {opt.get('parallel_workers', 'N/A')}\"); print(f\"  Batch: {opt.get('batch_size', 'N/A')}\"); print(f\"  Memory: {opt.get('memory_limit_gb', 'N/A')} GB\")" 2>/dev/null
        else
            echo "⏳ No optimization section yet (still using generic config)"
        fi

        # Show hardware if available
        if grep -q '"hardware"' "$CONFIG_FILE" 2>/dev/null; then
            echo ""
            python3 -c "import json; config=json.load(open('$CONFIG_FILE')); hw=config.get('hardware', {}); print(f\"  CPU Cores: {hw.get('cpu_cores', 'N/A')}\"); print(f\"  RAM: {hw.get('ram_total_gb', 'N/A')} GB\")" 2>/dev/null
        fi
    else
        echo "⚠️  Config file not found: $CONFIG_FILE"
    fi

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "📡 Network & Sync Status:"
    echo "───────────────────────────────────────────────────────────"

    # Ping player4
    if ping -c 1 -W 1 192.168.4.31 &>/dev/null; then
        echo "✅ Player4 network: REACHABLE (192.168.4.31)"
    else
        echo "❌ Player4 network: UNREACHABLE"
    fi

    # Check Syncthing
    if pgrep -x syncthing >/dev/null; then
        echo "✅ Syncthing: RUNNING"
    else
        echo "❌ Syncthing: NOT RUNNING"
    fi

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "Next check in ${INTERVAL}s... (Ctrl+C to stop)"
    echo "───────────────────────────────────────────────────────────"

    sleep $INTERVAL
done
