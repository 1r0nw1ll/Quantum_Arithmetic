# QA Lab Swarm Daemon: Monitoring Guide

**Status:** 🟢 RUNNING
**Started:** 2025-11-26 20:30 EST
**PID:** See `/tmp/qa_swarm_daemon.pid`

---

## Quick Status Check

```bash
# Check if daemon is running
ps -p $(cat /tmp/qa_swarm_daemon.pid) -o pid,cmd

# View live log output
tail -f logs/swarm_daemon_*.log

# Count completed tasks
ls tasks/completed/*.yaml | wc -l

# Count active tasks
ls tasks/active/*.yaml | wc -l

# View latest experiment generator results
cat logs/experiment_generator_*.json | tail -20
```

---

## Daemon Control Commands

### Check Status
```bash
# Is daemon running?
if ps -p $(cat /tmp/qa_swarm_daemon.pid 2>/dev/null) > /dev/null 2>&1; then
    echo "✅ Swarm daemon is RUNNING"
else
    echo "❌ Swarm daemon is NOT running"
fi
```

### View Logs
```bash
# Live tail (Ctrl+C to exit)
tail -f logs/swarm_daemon_$(ls -t logs/swarm_daemon_*.log | head -1 | xargs basename)

# Last 100 lines
tail -100 logs/swarm_daemon_*.log | tail -100

# Search for errors
grep -i error logs/swarm_daemon_*.log | tail -20
```

### Stop Daemon
```bash
# Graceful stop
kill $(cat /tmp/qa_swarm_daemon.pid)

# Force stop (if needed)
kill -9 $(cat /tmp/qa_swarm_daemon.pid)

# Or use pkill
pkill -f swarm-daemon
```

### Restart Daemon
```bash
# Stop
kill $(cat /tmp/qa_swarm_daemon.pid 2>/dev/null)

# Start
nohup make swarm-daemon > logs/swarm_daemon_$(date +%Y%m%d_%H%M%S).log 2>&1 &
echo $! > /tmp/qa_swarm_daemon.pid
```

---

## Monitoring Metrics

### Task Throughput
```bash
# Tasks completed per hour (approximate)
completed_count=$(ls tasks/completed/*.yaml 2>/dev/null | wc -l)
hours_running=1  # Update based on actual runtime
echo "Throughput: $((completed_count / hours_running)) tasks/hour"
```

### Task Queue Status
```bash
echo "📊 Task Queue Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Inbox:     $(ls tasks/inbox/*.yaml 2>/dev/null | wc -l) tasks"
echo "Active:    $(ls tasks/active/*.yaml 2>/dev/null | wc -l) tasks"
echo "Completed: $(ls tasks/completed/*.yaml 2>/dev/null | wc -l) tasks"
echo "Rejected:  $(ls tasks/rejected/*.yaml 2>/dev/null | wc -l) tasks"
```

### Artifact Generation
```bash
echo "📁 Artifact Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Plots:     $(ls plots/*.png 2>/dev/null | wc -l) files"
echo "CSVs:      $(find target -name '*.csv' 2>/dev/null | wc -l) files"
echo "JSONs:     $(find artifacts -name '*.json' 2>/dev/null | wc -l) files"
echo "Ingestion: $(ls artifacts/ingestion/*.md 2>/dev/null | wc -l) files"
```

### Recent Activity
```bash
echo "🕒 Recent Task Completions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ls -lt tasks/completed/*.yaml 2>/dev/null | head -5 | awk '{print $9}'
```

---

## Daemon Cycle Breakdown

Each 1-hour cycle runs:

1. **Experiment Generator** (~5s)
   - Reads roadmap
   - Scans ingestion papers
   - Generates new tasks (if needed)

2. **Scout** (~10s)
   - Scans codebase for TODOs
   - Finds incomplete work

3. **Prioritizer** (~5s)
   - Ranks all inbox tasks
   - Computes priority scores

4. **Planner** (~10s)
   - Creates execution plans
   - Identifies dependencies

5. **Builder** (~5s)
   - Scaffolds new agents (if needed)

6. **Self-Improver** (~5s)
   - Generates code quality tasks

7. **Dispatcher** (~5s)
   - Assigns tasks to agents
   - Moves inbox → active

8. **Executor** (~variable, up to 10min)
   - Processes active tasks
   - Runs Rust bins
   - Extracts ingestion papers

9. **Reviewer** (~10s)
   - Validates completed work
   - Approves/rejects tasks

10. **Archivist** (~5s)
    - Updates knowledge base

11. **Port-Rust-All** (~2min)
    - Benchmarks Rust code

12. **Metrics** (~30s)
    - Generates metric summaries

**Total Cycle Time:** ~3-15 minutes (depending on executor workload)
**Sleep Between Cycles:** 1 hour (3600s)

---

## Health Checks

### Daemon Alive?
```bash
if [ -f /tmp/qa_swarm_daemon.pid ] && kill -0 $(cat /tmp/qa_swarm_daemon.pid) 2>/dev/null; then
    echo "✅ Daemon is alive (PID: $(cat /tmp/qa_swarm_daemon.pid))"
else
    echo "❌ Daemon is dead or not started"
fi
```

### Is It Making Progress?
```bash
# Check if log file is being updated
log_file=$(ls -t logs/swarm_daemon_*.log 2>/dev/null | head -1)
if [ -f "$log_file" ]; then
    age=$(($(date +%s) - $(stat -c %Y "$log_file")))
    if [ $age -lt 3600 ]; then
        echo "✅ Log updated $age seconds ago"
    else
        echo "⚠️  Log not updated in $((age/60)) minutes"
    fi
fi
```

### Are Tasks Being Completed?
```bash
# Check for recently completed tasks (last hour)
recent=$(find tasks/completed -name "*.yaml" -mmin -60 2>/dev/null | wc -l)
if [ $recent -gt 0 ]; then
    echo "✅ $recent tasks completed in last hour"
else
    echo "⏳ No tasks completed recently"
fi
```

---

## Alerts & Notifications

### High Task Backlog
```bash
active=$(ls tasks/active/*.yaml 2>/dev/null | wc -l)
if [ $active -gt 100 ]; then
    echo "⚠️  WARNING: High task backlog ($active active tasks)"
fi
```

### Executor Failures
```bash
failed=$(grep -i "failed\|error" logs/swarm_daemon_*.log 2>/dev/null | wc -l)
if [ $failed -gt 10 ]; then
    echo "⚠️  WARNING: $failed errors detected in logs"
fi
```

### Disk Space
```bash
usage=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $usage -gt 90 ]; then
    echo "⚠️  WARNING: Disk usage at ${usage}%"
fi
```

---

## Expected Behavior (First 24 Hours)

**Hour 1:**
- Process existing 5 active tasks
- Extract all 5 ingestion papers
- Generate follow-up experiment tasks

**Hour 2-6:**
- Execute ingestion-derived experiments
- Begin Rust bin experiments (if binaries exist)
- Accumulate artifacts (CSV, plots)

**Hour 6-12:**
- Process any new roadmap experiments
- Self-improvement cycles (if trainer tasks generated)
- Metrics aggregation

**Hour 12-24:**
- Continuous experiment execution
- Knowledge base updates
- Artifact bundling

**Expected Throughput:**
- ~3-5 tasks per hour (depending on complexity)
- ~1-2 ingestion papers per hour
- ~1 experiment per 2 hours (Rust bins)

---

## Troubleshooting

### Daemon Won't Start
```bash
# Check for conflicting processes
ps aux | grep swarm-daemon

# Check Makefile syntax
make -n swarm-daemon

# Check Python environment
qa_venv/bin/python --version
```

### Daemon Crashes
```bash
# Check exit code
tail -20 logs/swarm_daemon_*.log

# Check for Python errors
grep -i "traceback\|exception" logs/swarm_daemon_*.log | tail -20

# Restart with verbose logging
QA_DEBUG=1 make swarm-daemon
```

### Tasks Not Executing
```bash
# Check task states
grep "^state:" tasks/active/*.yaml | sort | uniq -c

# Check executor output
grep "Processing task" logs/swarm_daemon_*.log | tail -10

# Check dispatcher assignments
grep "Assigned" logs/swarm_daemon_*.log | tail -10
```

---

## Performance Tuning

### Faster Cycles (30min instead of 1hr)
Edit `Makefile`:
```makefile
swarm-daemon:
    @while true; do \
        $(MAKE) agent_loop || true; \
        sleep 1800; \  # Changed from 3600 to 1800
    done
```

### Skip Slow Components
```makefile
# Remove port-rust-all and metrics from agent_loop
agent_loop: experiment-gen scout prioritize dispatch executor review
```

### Limit Executor Timeout
Set environment variable:
```bash
QA_EXECUTOR_TIMEOUT=300 make swarm-daemon  # 5 min max per task
```

---

## Integration with External Tools

### Prometheus Metrics
```bash
# Export task counts
cat > /tmp/qa_swarm_metrics.prom <<EOF
qa_tasks_active $(ls tasks/active/*.yaml 2>/dev/null | wc -l)
qa_tasks_completed $(ls tasks/completed/*.yaml 2>/dev/null | wc -l)
qa_artifacts_plots $(ls plots/*.png 2>/dev/null | wc -l)
EOF
```

### Webhook Notifications (Optional)
Add to executor.py:
```python
import requests
requests.post(WEBHOOK_URL, json={"task": task_id, "status": "completed"})
```

---

## Daemon Lifecycle

**Startup:** `nohup make swarm-daemon > logs/... &`
**Running:** Infinite loop with 1-hour sleep
**Shutdown:** `kill $(cat /tmp/qa_swarm_daemon.pid)`

**Logs:** `logs/swarm_daemon_YYYYMMDD_HHMMSS.log`
**PID:** `/tmp/qa_swarm_daemon.pid`
**Restart:** Automatic on reboot if added to systemd/cron

---

## Adding to Systemd (Optional)

```bash
# Create service file
sudo tee /etc/systemd/system/qa-swarm.service <<EOF
[Unit]
Description=QA Lab Autonomous Swarm
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/make swarm-daemon
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable qa-swarm
sudo systemctl start qa-swarm

# Check status
sudo systemctl status qa-swarm
```

---

**Status:** 🟢 Daemon running autonomously
**Monitor:** `tail -f logs/swarm_daemon_*.log`
**Stop:** `kill $(cat /tmp/qa_swarm_daemon.pid)`
