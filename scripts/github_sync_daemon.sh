#!/usr/bin/env bash
# ============================================================
# QA Swarm: GitHub Sync Daemon
# ============================================================
# Continuously syncs local commits to GitHub
# Based on Network Chuck's ai-in-the-terminal automation patterns
#
# Usage:
#   ./scripts/github_sync_daemon.sh        # Run in foreground
#   ./scripts/github_sync_daemon.sh &      # Run in background
#
# Stop: pkill -f github_sync_daemon

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Configuration
SYNC_INTERVAL="${QA_GITHUB_SYNC_INTERVAL:-300}"  # 5 minutes default
REMOTE="${QA_GIT_REMOTE:-origin}"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")

echo "🔄 QA Swarm GitHub Sync Daemon Started"
echo "   Remote: $REMOTE"
echo "   Branch: $BRANCH"
echo "   Interval: ${SYNC_INTERVAL}s"
echo "   Press Ctrl+C to stop"
echo ""

# Trap to handle clean shutdown
trap 'echo ""; echo "🛑 GitHub sync daemon stopped"; exit 0' INT TERM

while true; do
    # Check if there are commits to push
    LOCAL_COMMITS=$(git rev-list --count "$REMOTE/$BRANCH..$BRANCH" 2>/dev/null || echo "0")

    if [ "$LOCAL_COMMITS" -gt 0 ]; then
        echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] 📤 Found $LOCAL_COMMITS unpushed commit(s)"

        # Pull with rebase first
        if git pull --rebase "$REMOTE" "$BRANCH" 2>/dev/null; then
            echo "   ✅ Rebased onto remote"
        else
            echo "   ⚠️  Rebase failed, trying direct push"
        fi

        # Push to remote
        if git push "$REMOTE" "$BRANCH" 2>/dev/null; then
            echo "   ✅ Pushed $LOCAL_COMMITS commit(s) to GitHub"
            echo "   🔗 https://github.com/1r0nw1ll/Quantum_Arithmetic"
        else
            echo "   ❌ Push failed - may need authentication"
            echo "   💡 Set up GitHub token: gh auth login"
        fi
    else
        echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] 💤 No unpushed commits (in sync)"
    fi

    echo ""
    sleep "$SYNC_INTERVAL"
done
