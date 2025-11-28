# GitHub Integration - Network Chuck Style Automation

**Status:** ✅ FULLY CONFIGURED
**Repository:** https://github.com/1r0nw1ll/Quantum_Arithmetic
**Approach:** Network Chuck's ai-in-the-terminal automation patterns
**Date:** 2025-11-28

---

## Overview

The QA Lab now has automated GitHub integration following Network Chuck's philosophy:
- **Continuous sync** via daemon process
- **Automated commits** with timestamped snapshots
- **Selective tracking** (code only, not runtime state)
- **Makefile-driven** workflow for easy operation

This follows the patterns from:
- https://github.com/theNetworkChuck/ai-in-the-terminal
- https://github.com/theNetworkChuck/docker-mcp-tutorial

---

## Quick Start

### 1. Authenticate with GitHub

```bash
# Install GitHub CLI (if not already installed)
sudo apt install gh -y

# Authenticate
gh auth login
# Choose: GitHub.com → HTTPS → Yes (authenticate Git) → Login with browser
```

### 2. Test the Setup

```bash
# Check current status
make github-status

# Create a snapshot and push
make git-push
```

### 3. Enable Continuous Sync

```bash
# Start daemon (syncs every 5 minutes)
make github-daemon-start

# Check status
make github-status

# Stop daemon (when needed)
make github-daemon-stop
```

---

## Architecture

### File Structure

```
qa_lab/
├── .git/
│   └── config              # Remote configured: origin → GitHub
├── .gitignore              # Excludes runtime state (tasks/, logs/)
├── scripts/
│   ├── git_autosnapshot.sh       # Creates timestamped commits
│   └── github_sync_daemon.sh     # Continuous background sync
└── Makefile                # GitHub integration targets
```

### What Gets Synced

**Included** (code and configuration):
- `qa_agents/` - All agent code
- `scripts/` - Automation scripts
- `Makefile` - Build configuration
- `*.md` - Documentation
- `docker-compose.yml` - Container config
- `qa_mcp_config.yaml` - MCP configuration

**Excluded** (runtime state, per .gitignore):
- `tasks/inbox/*.yaml` - Incoming task queue
- `tasks/active/*.yaml` - Active task queue
- `tasks/completed/*.yaml` - Completed tasks
- `logs/*.jsonl` - Agent run logs
- `artifacts/*` - Generated outputs
- `CHANGELOG.md` - 5.3M line changelog (too large)

---

## Usage Patterns

### Manual Snapshot (Local Only)

```bash
# Create commit without pushing
make git-snapshot

# Or with custom message
./scripts/git_autosnapshot.sh "implemented feature X"
```

### Manual Push to GitHub

```bash
# Commit + push current changes
make git-push

# Or enable push for autosnapshot
QA_GIT_PUSH=1 ./scripts/git_autosnapshot.sh
```

### Continuous Sync Daemon

```bash
# Start daemon (runs in background)
make github-daemon-start

# Daemon automatically:
# - Checks for new commits every 5 minutes (configurable)
# - Pulls remote changes with rebase
# - Pushes local commits
# - Logs all activity with timestamps

# Check if daemon is running
make github-status

# Stop daemon
make github-daemon-stop
```

### Pull Latest Changes

```bash
# Pull from GitHub with rebase
make github-pull
```

---

## Configuration

### Environment Variables

#### git_autosnapshot.sh

```bash
export QA_GIT_PUSH=1              # Enable auto-push (default: 0)
export QA_GIT_REMOTE=origin       # Remote name (default: origin)
export QA_GIT_BRANCH=main         # Branch to push (default: current)
```

#### github_sync_daemon.sh

```bash
export QA_GITHUB_SYNC_INTERVAL=300  # Sync every 5 minutes (default: 300)
export QA_GIT_REMOTE=origin         # Remote name (default: origin)
```

### Example: Faster Sync Interval

```bash
# Sync every 1 minute instead of 5
QA_GITHUB_SYNC_INTERVAL=60 make github-daemon-start
```

---

## Network Chuck Patterns

This implementation follows Network Chuck's key principles:

### 1. **Automation First**
- Daemon process handles sync automatically
- No manual intervention required
- Cron-like behavior without cron

### 2. **Terminal-Centric Workflow**
- All operations via Makefile
- Clear status feedback
- Easy monitoring with `make github-status`

### 3. **Fail-Safe Design**
- Pulls before push (rebase strategy)
- Non-destructive operations
- Clear error messages with recovery hints

### 4. **Multi-AI Collaboration**
- Agents commit via `git_autosnapshot.sh`
- Daemon syncs agent changes to GitHub
- Distributed swarm can pull latest code

---

## Integration with Swarm

### Agent Workflow

```bash
# Agent completes task
python3 qa_agents/cli/executor.py

# Agent creates snapshot
./scripts/git_autosnapshot.sh "task-123: implemented feature"

# Daemon automatically pushes (if running)
# Or agent can manually push:
QA_GIT_PUSH=1 ./scripts/git_autosnapshot.sh "task-123: complete"
```

### Distributed Nodes (player4, etc.)

```bash
# On player4, pull latest code
cd /path/to/qa_lab
make github-pull

# Or run daemon to stay in sync
make github-daemon-start
```

---

## Troubleshooting

### Authentication Issues

```bash
# Re-authenticate
gh auth login

# Or use SSH instead of HTTPS
git remote set-url origin git@github.com:1r0nw1ll/Quantum_Arithmetic.git

# Generate SSH key if needed
ssh-keygen -t ed25519 -C "qa-swarm@player2.local"
gh ssh-key add ~/.ssh/id_ed25519.pub
```

### Push Rejected (Diverged History)

```bash
# Check what's different
git log origin/master..master

# Force push (⚠️ destructive)
git push --force origin master

# Or merge remote changes
git pull --no-rebase origin master
git push origin master
```

### Daemon Not Pushing

```bash
# Check daemon is running
pgrep -f github_sync_daemon

# Check logs (if redirected)
tail -f /tmp/github_sync.log

# Restart daemon
make github-daemon-stop
make github-daemon-start
```

---

## Advanced Usage

### Custom Sync Branch

```bash
# Push to different branch
QA_GIT_BRANCH=dev make git-push

# Or permanently set
echo 'export QA_GIT_BRANCH=dev' >> ~/.bashrc
```

### Conditional Push

```bash
# Only push if tests pass
if make test; then
    make git-push
fi
```

### Scheduled Snapshots (via cron)

```bash
# Add to crontab
crontab -e

# Snapshot every hour
0 * * * * cd /home/player2/signal_experiments/qa_lab && make git-snapshot

# Push every 4 hours
0 */4 * * * cd /home/player2/signal_experiments/qa_lab && make git-push
```

---

## Comparison to Network Chuck

| Feature | Network Chuck | QA Lab |
|---------|---------------|--------|
| **Automation** | SSH tunnels, tmux sessions | Daemon process, Makefile |
| **Persistence** | Context files | Git snapshots + Syncthing |
| **Multi-AI** | Claude + GPT + Gemini | QALM + Claude + Codex + Gemini |
| **Container** | Docker MCP gateway | Docker MCP servers (4) |
| **Sync** | Manual script runs | Continuous daemon |
| **State** | Local context files | Git + Syncthing distributed |

**Key Innovation:** We combine Network Chuck's automation with distributed Syncthing state management for true multi-node swarm collaboration.

---

## Files Modified

### Created:
- `scripts/github_sync_daemon.sh` - Continuous sync daemon
- `GITHUB_INTEGRATION.md` - This documentation

### Modified:
- `scripts/git_autosnapshot.sh` - Added push capability
- `Makefile` - Added GitHub integration targets
- `.git/config` - Added GitHub remote

### Status:
```bash
git remote -v
# origin  https://github.com/1r0nw1ll/Quantum_Arithmetic.git (fetch)
# origin  https://github.com/1r0nw1ll/Quantum_Arithmetic.git (push)
```

---

## Next Steps

1. **Authenticate:** `gh auth login`
2. **Test push:** `make git-push`
3. **Start daemon:** `make github-daemon-start`
4. **Deploy to player4:** Sync code via Syncthing, pull from GitHub
5. **Monitor:** `make github-status`

---

**Status:** Ready for production use
**Repository:** https://github.com/1r0nw1ll/Quantum_Arithmetic
**Last Updated:** 2025-11-28 (Gemini restoration + GitHub integration)
