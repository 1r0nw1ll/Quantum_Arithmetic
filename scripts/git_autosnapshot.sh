#!/usr/bin/env bash
# ============================================================
# QA Swarm: Automatic Git Snapshot Script
# ============================================================
# Creates timestamped git commits of swarm state
# Usage: ./scripts/git_autosnapshot.sh [message]
#
# Environment variables:
#   QA_GIT_PUSH=1     - Enable auto-push to GitHub
#   QA_GIT_REMOTE     - Remote name (default: origin)
#   QA_GIT_BRANCH     - Branch to push (default: current branch)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Configuration
ENABLE_PUSH="${QA_GIT_PUSH:-0}"
REMOTE="${QA_GIT_REMOTE:-origin}"
DEFAULT_MSG="autosnapshot: swarm state checkpoint"
SNAPSHOT_MSG="${1:-$DEFAULT_MSG}"

# Get timestamp and branch
TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")
PUSH_BRANCH="${QA_GIT_BRANCH:-$BRANCH}"

# Add only tracked code/config files (not runtime state)
echo "📸 Creating git snapshot..."
git add \
  qa_agents/ \
  qa_fast_eval.py \
  qa_equations.py \
  qa_config.yaml \
  docker-compose.yml \
  qa_mcp_config.yaml \
  scripts/ \
  Makefile \
  *.md \
  .gitignore \
  tasks/.gitkeep \
  tasks/*/.gitkeep \
  2>/dev/null || true

# Add MCP server code
git add qa_mcp_servers/ 2>/dev/null || true

# Create commit
FULL_MSG="$SNAPSHOT_MSG @ $TS ($BRANCH)"
if git commit -m "$FULL_MSG"; then
    echo "✅ Snapshot created: $FULL_MSG"

    # Show what was committed
    echo ""
    echo "Files in this snapshot:"
    git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "(initial commit)"

    # Show commit hash
    COMMIT_HASH=$(git rev-parse --short HEAD)
    echo ""
    echo "Commit: $COMMIT_HASH"

    # Push to GitHub if enabled
    if [ "$ENABLE_PUSH" = "1" ]; then
        echo ""
        echo "🔄 Syncing to GitHub ($REMOTE/$PUSH_BRANCH)..."

        # Pull with rebase to handle remote changes
        if git pull --rebase "$REMOTE" "$PUSH_BRANCH" 2>/dev/null; then
            echo "📥 Pulled latest changes from $REMOTE/$PUSH_BRANCH"
        else
            echo "⚠️  Pull failed or no remote tracking - attempting force push"
        fi

        # Push to remote
        if git push "$REMOTE" "$PUSH_BRANCH"; then
            echo "✅ Pushed to GitHub: https://github.com/1r0nw1ll/Quantum_Arithmetic"
        else
            echo "❌ Push failed - you may need to authenticate or force push"
            echo "   Try: git push -u $REMOTE $PUSH_BRANCH"
            exit 1
        fi
    else
        echo ""
        echo "💡 To enable GitHub sync: export QA_GIT_PUSH=1"
    fi
else
    echo "⚠️  No changes to commit (swarm state unchanged)"
fi
