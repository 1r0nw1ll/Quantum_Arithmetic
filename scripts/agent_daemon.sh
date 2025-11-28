#!/usr/bin/env bash
set -euo pipefail

# Source environment configuration if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
fi

interval="${QA_DAEMON_INTERVAL:-300}"
# Optional run duration (in minutes). If set, the daemon will exit after this many minutes.
max_minutes="${QA_DAEMON_DURATION_MIN:-}"
start_epoch=$(date +%s)

# Sensible defaults (override with environment)
: "${QA_ANALYSIS_AGENT:=claude}"
: "${QA_PUBLISH_EACH_LOOP:=1}"
: "${QA_SANDBOX_ENABLE:=1}"
: "${QA_AGENT_NAME:=qa_daemon}"
# External agents default to artifact-producing ACK helper
# If QA_COLLAB_LIVE=1, prefer collab_broadcast; else default to external_ack
if [ "${QA_COLLAB_LIVE:-0}" = "1" ] && [ -x "./collab_broadcast" ]; then
  : "${GEMINI_CMD:=./collab_broadcast}"
  : "${CODEX_CMD:=./collab_broadcast}"
  : "${OPENCODE_CMD:=./collab_broadcast}"
  : "${CLAUDE_CMD:=./collab_broadcast}"
else
  : "${GEMINI_CMD:=python3 scripts/external_ack.py}"
  : "${CODEX_CMD:=python3 scripts/external_ack.py}"
  : "${OPENCODE_CMD:=python3 scripts/external_ack.py}"
  : "${CLAUDE_CMD:=python3 scripts/external_ack.py}"
fi
echo "🔁 QA Agent Daemon starting (interval=${interval}s)"

trap 'echo "Exiting daemon"; exit 0' INT TERM

while true; do
  echo
  echo "["$(date '+%F %T')"] Running qa loop..."
  # Optional Obsidian ingestion per loop
  if [ "${QA_INGEST_OBSIDIAN:-0}" = "1" ] && [ -d "${OB_VAULT_DIR:-vault}" ]; then
    echo "["$(date '+%F %T')"] Ingesting Obsidian vault..."
    OB_VAULT_DIR="${OB_VAULT_DIR:-vault}" python3 qa_agents/cli/obsidian_ingest.py || true
  fi
  # Run the full agent loop from the project root via Makefile
  make -C "$PROJECT_DIR" agent_loop || true
  # Optional publish step per loop (enable with QA_PUBLISH_EACH_LOOP=1; default on)
  if [ "${QA_PUBLISH_EACH_LOOP:-1}" = "1" ]; then
    echo "["$(date '+%F %T')"] Publishing artifacts..."
    python3 scripts/aggregate_artifacts_delta.py || true
    python3 scripts/publish_run.py || true
  fi
  echo "Sleeping ${interval}s..."
  sleep "${interval}"
  if [ -n "$max_minutes" ]; then
    now=$(date +%s)
    elapsed=$(( (now - start_epoch) / 60 ))
    if [ "$elapsed" -ge "$max_minutes" ]; then
      echo "⏰ Max duration reached (${max_minutes} min). Exiting daemon."
      break
    fi
  fi
done
