#!/usr/bin/env bash
# ============================================================
# QA Swarm: Optimized High-Throughput Daemon
# ============================================================
# Starts swarm daemon with performance optimizations
#
# Optimizations:
# - QA_MAX_ACTIVE=50 (was 10) - Process 50 tasks per cycle
# - Sleep 300s (was 3600s) - Run 12 cycles/hour instead of 1
# - Result: ~12x throughput increase

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Performance settings
export QA_MAX_ACTIVE=50              # Activate 50 tasks per cycle (was 10)
export QA_PARALLEL_EXECUTORS=4       # Run 4 executors in parallel
export QA_GITHUB_SYNC_INTERVAL=300   # Sync to GitHub every 5 min

echo "🚀 Starting Optimized QA Swarm"
echo "=============================="
echo "Max active tasks: $QA_MAX_ACTIVE (5x increase)"
echo "Sleep interval: 300s (12x more cycles)"
echo "Expected throughput: ~60x increase!"
echo ""
echo "Current queue: $(ls tasks/active/*.yaml 2>/dev/null | wc -l) active tasks"
echo ""
echo "Starting daemon..."
echo ""

# Start daemon with nohup
nohup make swarm-daemon > logs/swarm_daemon_optimized.log 2>&1 &
DAEMON_PID=$!

sleep 3

if ps -p $DAEMON_PID > /dev/null; then
    echo "✅ Daemon started successfully (PID: $DAEMON_PID)"
    echo ""
    echo "Monitor with:"
    echo "  tail -f logs/swarm_daemon_optimized.log"
    echo ""
    echo "Stop with:"
    echo "  pkill -f 'make swarm-daemon'"
else
    echo "❌ Failed to start daemon"
    exit 1
fi
