# 🚀 Player4 Deployment - Quick Start Guide

**For:** Will (Human Operator)
**Task:** Deploy player4 as compute node in distributed QA swarm
**Date:** 2025-11-27

---

## 📦 Deployment Package Ready

**Location:** `/home/player2/signal_experiments/qa_lab/qa_swarm_player4_deployment.zip`

**Size:** 13KB (contains 4 files)

**Contents:**
- `DEPLOY_ON_PLAYER4.sh` - Automated deployment script
- `VERIFY_DEPLOYMENT.sh` - Verification script
- `INSTRUCTIONS_FOR_CLAUDE_AGENT.md` - Detailed instructions for Claude CLI
- `README.md` - Complete documentation

---

## 🎯 Option 1: Manual Deployment (You Run Commands)

### Step 1: Copy Package to player4

```bash
# From player2
scp ~/signal_experiments/qa_lab/qa_swarm_player4_deployment.zip player4:~/

# SSH to player4
ssh player4
```

### Step 2: Extract and Deploy

```bash
# On player4
cd ~
unzip qa_swarm_player4_deployment.zip
cd qa_swarm_player4_deployment

# Run deployment
chmod +x *.sh
bash DEPLOY_ON_PLAYER4.sh
```

### Step 3: Configure Syncthing (Manual Step)

When deployment pauses for Syncthing configuration:

**Open two browser tabs:**
1. http://player4:8384 (on player4)
2. http://player2:8384 (on player2)

**On both:**
- Add each other as remote devices
- Share folders: `tasks/`, `artifacts/`, `plots/`, `logs/`
- Wait for "Up to Date" status

**Then:** Press Enter in deployment script to continue

### Step 4: Verify

```bash
# On player4
bash VERIFY_DEPLOYMENT.sh

# On player2
cd ~/signal_experiments/qa_lab
make cluster-monitor
make cluster-dispatch
```

---

## 🤖 Option 2: Claude CLI Agent Deployment (Autonomous)

### Step 1: Copy Package to player4

```bash
# From player2
scp ~/signal_experiments/qa_lab/qa_swarm_player4_deployment.zip player4:~/
```

### Step 2: Start Claude CLI Agent on player4

```bash
ssh player4
cd ~
unzip qa_swarm_player4_deployment.zip
cd qa_swarm_player4_deployment

# Start Claude CLI agent (if available)
claude code
```

### Step 3: Give Claude These Instructions

**Copy/paste this to Claude CLI agent on player4:**

```
Task: Deploy this node (player4) as a compute node in the distributed QA swarm.

Instructions:
1. Read INSTRUCTIONS_FOR_CLAUDE_AGENT.md completely
2. Follow all steps in the instructions
3. Execute DEPLOY_ON_PLAYER4.sh
4. When deployment pauses for Syncthing configuration:
   - Note the Syncthing URLs provided
   - Ask me (Will) to configure Syncthing pairing
   - Wait for confirmation before proceeding
5. After deployment completes, run VERIFY_DEPLOYMENT.sh
6. Report verification results

Context:
- Primary node: player2
- This node role: Compute node (executor + reviewer + benchmarks)
- Sync method: Syncthing
- Installation directory: ~/qa_lab

Begin deployment now.
```

### Step 4: Handle Syncthing Configuration

When Claude pauses for Syncthing setup, **you will need to:**

**On player4's browser:**
1. Open http://player4:8384
2. Click "Actions" → "Show ID" → Copy device ID

**On player2's browser:**
1. Open http://player2:8384
2. Click "Add Remote Device"
3. Paste player4's device ID
4. Click "Share" on folders: `tasks/`, `artifacts/`, `plots/`, `logs/`

**On player4's browser:**
1. Accept device connection from player2
2. Accept folder shares

**Tell Claude:** "Syncthing configuration complete, continue deployment"

### Step 5: Verify on player2

```bash
# On player2
cd ~/signal_experiments/qa_lab
make cluster-monitor   # Should show 2 nodes
make cluster-dispatch  # Should route tasks to player4
```

---

## ✅ Success Criteria

Deployment is successful when:

### On player4:

```bash
$ systemctl status qa-swarm-node
● qa-swarm-node.service - QA Lab Swarm Compute Node
   Active: active (running)

$ ls ~/qa_lab/tasks/active | wc -l
434  # Should match player2's count

$ journalctl -u qa-swarm-node -n 10
# Shows "agent loop" activity
```

### On player2:

```bash
$ cd ~/signal_experiments/qa_lab
$ make cluster-monitor

🔍 Detecting cluster nodes...
  Found 2 node(s)
    • Player2 (primary)
    • player4 (compute)

Cluster health: 100/100
```

---

## 🔥 What Happens When player4 Joins

### Immediate (T+0-10 min):

- ✅ player4 daemon starts
- ✅ Syncthing syncs tasks from player2 (~434 active tasks)
- ✅ player4 agent loop begins executing
- ✅ First tasks complete on player4

### Short-term (T+10-60 min):

- ✅ Cluster monitor detects player4
- ✅ Cluster dispatcher routes new tasks to player4
- ✅ Load balances across 2 nodes
- ✅ Throughput increases: 180 → 340 tasks/hour (1.9× speedup)

### Long-term (24+ hours):

- ✅ Hundreds of tasks completed on player4
- ✅ Cluster health: 100/100
- ✅ Sustained 1.9× throughput improvement
- ✅ Fault-tolerant operation (either node can fail)

---

## 🚨 Troubleshooting

### Problem: Cannot reach player4

```bash
# Test connectivity
ping player4
ssh player4 "echo OK"

# Fix: Check network, SSH keys
```

### Problem: Syncthing not syncing

```bash
# On player4
curl http://localhost:8384/rest/system/status

# Check Syncthing UI
xdg-open http://player4:8384
```

### Problem: Daemon not starting

```bash
# On player4
journalctl -u qa-swarm-node -n 50
sudo systemctl restart qa-swarm-node
```

### Problem: No tasks executing

```bash
# On player4
cd ~/qa_lab
source qa_venv/bin/activate
make -f Makefile.node node-agent-loop  # Manual test run
```

---

## 📊 Monitoring After Deployment

### From player2 (Primary):

```bash
cd ~/signal_experiments/qa_lab

# Real-time cluster monitoring
make cluster-monitor

# Task distribution
make cluster-dispatch

# Full dashboard
make cluster-dashboard

# View metrics
cat artifacts/evals/cluster_metrics_latest.json | python3 -m json.tool

# View visual dashboard
xdg-open plots/cluster_dashboard_latest.png
```

### From player4 (Compute):

```bash
# Daemon status
systemctl status qa-swarm-node

# Live logs
journalctl -u qa-swarm-node -f

# Task counts
ls ~/qa_lab/tasks/active | wc -l
ls ~/qa_lab/tasks/completed | wc -l

# Syncthing status
curl http://localhost:8384/rest/system/status | python3 -m json.tool
```

---

## 📈 Expected Performance

### Before (1 Node):

```
player2 only:
  180 tasks/hour
  ~14 hours to complete 2,600 tasks
  Single point of failure
```

### After (2 Nodes):

```
player2 + player4:
  ~340 tasks/hour (1.9× faster)
  ~7.6 hours to complete 2,600 tasks
  Fault-tolerant cluster
  Efficiency: 94%
```

---

## 🎯 Next Steps After Deployment

### 1. Validate Operation:

```bash
# On player2
make cluster-monitor
# Confirm: "Found 2 node(s)"

make cluster-dispatch
# Confirm: Tasks distributed to both nodes
```

### 2. Monitor First Hour:

```bash
# Watch player4 logs
ssh player4 "journalctl -u qa-swarm-node -f"

# Watch cluster metrics update
watch -n 60 "cd ~/signal_experiments/qa_lab && make cluster-monitor"
```

### 3. Add More Nodes (Optional):

To add player5, player6, etc:
- Copy same deployment package
- Run deployment script
- Configure Syncthing
- Cluster auto-scales!

---

## 📚 Reference Documentation

**In this repository:**
- `DISTRIBUTED_SWARM_GUIDE.md` - Complete distributed computing guide (850+ lines)
- `MULTINODE_DEPLOYMENT_COMPLETE.md` - v3.5 deployment summary
- `EVOLUTION_COMPLETE_V3.md` - v3.0 research autonomy documentation
- `README.md` (in deployment package) - Deployment package documentation

**Key Files:**
- **Deployment package:** `/home/player2/signal_experiments/qa_lab/qa_swarm_player4_deployment.zip`
- **Cluster monitor:** `make cluster-monitor`
- **Cluster dispatcher:** `make cluster-dispatch`
- **Dashboard:** `make cluster-dashboard`

---

## 🔥 TL;DR - Fastest Path

**For impatient deployment:**

```bash
# On player2
scp ~/signal_experiments/qa_lab/qa_swarm_player4_deployment.zip player4:~/

# On player4
ssh player4
cd ~ && unzip qa_swarm_player4_deployment.zip
cd qa_swarm_player4_deployment
chmod +x *.sh
bash DEPLOY_ON_PLAYER4.sh
# (Configure Syncthing when prompted)

# Verify
bash VERIFY_DEPLOYMENT.sh

# On player2
cd ~/signal_experiments/qa_lab
make cluster-monitor
make cluster-dispatch
```

**Done!** The distributed swarm is live. 🌐

---

**Generated:** 2025-11-27
**By:** Claude Code on player2
**Deployment Package:** qa_swarm_player4_deployment.zip (13KB)
**Status:** 🟢 READY FOR DEPLOYMENT

**Let's spread the swarm!** 🚀
