#!/usr/bin/env bash
# ============================================================
# QA Swarm: Automatic Git Snapshot Script
# ============================================================
# Creates timestamped git commits of swarm state
# Usage: ./scripts/git_autosnapshot.sh [message]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Default message if none provided
DEFAULT_MSG="autosnapshot: swarm state checkpoint"
SNAPSHOT_MSG="${1:-$DEFAULT_MSG}"

# Get timestamp and branch
TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")

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
else
    echo "⚠️  No changes to commit (swarm state unchanged)"
fi
