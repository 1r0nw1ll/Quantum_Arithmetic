#!/usr/bin/env python3
"""
Real-Time Collaboration Demo
Demonstrates all agents working together in real-time
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

print("="*60)
print("QA AGENT REAL-TIME COLLABORATION DEMO")
print("="*60)
print()

# Create agents representing different roles
print("🚀 Initializing agents...")
print()

scout = CollaborativeAgent("scout", metadata={"role": "discovery"})
prioritizer = CollaborativeAgent("prioritizer", metadata={"role": "analysis"})
executor = CollaborativeAgent("executor", metadata={"role": "execution"})
reviewer = CollaborativeAgent("reviewer", metadata={"role": "validation"})

time.sleep(1)

# Set up subscriptions
print("📡 Setting up event subscriptions...")
prioritizer.subscribe("tasks_discovered")
executor.subscribe("tasks_prioritized")
reviewer.subscribe("task_completed")

# Event handlers
print("🔧 Registering event handlers...")

def on_tasks_discovered(data):
    payload = data.get('payload', {})
    agent_data = payload.get('data', {})
    task_count = agent_data.get('count', 0)
    print(f"   [Prioritizer] 📥 Received {task_count} tasks from Scout")

    # Prioritize tasks
    time.sleep(0.5)
    prioritizer.broadcast("tasks_prioritized", {
        "count": task_count,
        "priority_order": ["TASK-001", "TASK-002", "TASK-003"]
    })
    print(f"   [Prioritizer] ✅ Prioritized {task_count} tasks")

def on_tasks_prioritized(data):
    payload = data.get('payload', {})
    agent_data = payload.get('data', {})
    tasks = agent_data.get('priority_order', [])
    print(f"   [Executor] 📥 Received {len(tasks)} prioritized tasks")

    # Execute first task
    if tasks:
        task_id = tasks[0]
        time.sleep(0.5)
        executor.set_state(f"task:{task_id}:status", "completed")
        executor.broadcast("task_completed", {
            "task_id": task_id,
            "result": "success",
            "output": "Implementation complete"
        })
        print(f"   [Executor] ✅ Completed {task_id}")

def on_task_completed(data):
    payload = data.get('payload', {})
    agent_data = payload.get('data', {})
    task_id = agent_data.get('task_id')
    print(f"   [Reviewer] 📥 Reviewing {task_id}")

    time.sleep(0.5)
    reviewer.broadcast("task_reviewed", {
        "task_id": task_id,
        "approved": True,
        "comments": "Code quality good, tests passing"
    })
    print(f"   [Reviewer] ✅ Approved {task_id}")

prioritizer.on("tasks_discovered", on_tasks_discovered)
executor.on("tasks_prioritized", on_tasks_prioritized)
reviewer.on("task_completed", on_task_completed)

print()
print("="*60)
print("DEMONSTRATION: Coordinated Workflow")
print("="*60)
print()

# Scout discovers tasks
print("1️⃣  Scout discovering tasks...")
scout.broadcast("tasks_discovered", {
    "count": 3,
    "tasks": ["TASK-001", "TASK-002", "TASK-003"],
    "source": "code_analysis"
})

# Wait for workflow to complete
print()
print("⏳ Watching collaboration in real-time...")
print()
time.sleep(3)

print()
print("="*60)
print("DEMONSTRATION: Shared State")
print("="*60)
print()

# Demonstrate shared state
print("2️⃣  Agents sharing state...")
print()

scout.set_state("project_status", "active")
scout.set_state("last_scan", datetime.now().isoformat())
print("   [Scout] Set project_status = active")

time.sleep(0.3)

status = executor.get_state("project_status")
last_scan = executor.get_state("last_scan")
print(f"   [Executor] Read project_status = {status}")
print(f"   [Executor] Read last_scan = {last_scan}")

print()
print("="*60)
print("DEMONSTRATION: Agent Discovery")
print("="*60)
print()

# Query agents
print("3️⃣  Querying active agents...")
print()

all_agents = scout.query_agents()
print(f"   Total active agents: {len(all_agents)}")
for agent_info in all_agents:
    role = agent_info.get('metadata', {}).get('role', 'unknown')
    print(f"      • {agent_info['name']} - {role}")

print()
print("="*60)
print("DEMONSTRATION: Activity Monitoring")
print("="*60)
print()

# Log activities
print("4️⃣  Logging agent activities...")
print()

scout.log_activity("scan_completed", {"tasks_found": 3})
executor.log_activity("task_execution", {"task_id": "TASK-001", "status": "success"})
reviewer.log_activity("review_completed", {"task_id": "TASK-001", "approved": True})

print("   [Scout] Logged scan_completed")
print("   [Executor] Logged task_execution")
print("   [Reviewer] Logged review_completed")

# Retrieve activities
time.sleep(1)
scout_activities = scout.get_state(f"activities:{scout.agent_id}")
if scout_activities:
    print(f"\n   Scout's recent activities:")
    for activity in scout_activities[-3:]:
        print(f"      • {activity['action']} at {activity['timestamp']}")

print()
print("="*60)
print("DEMONSTRATION: Help Request")
print("="*60)
print()

# Demonstrate help request
print("5️⃣  Agent requesting help...")
print()

def on_help_response(data):
    payload = data.get('payload', {})
    agent_data = payload.get('data', {})
    helper = payload.get('agent_name')
    solution = agent_data.get('solution', 'No solution')
    print(f"   [Executor] 📥 Help received from {helper}: {solution}")

executor.subscribe("help_offered")
executor.on("help_offered", on_help_response)

executor.broadcast("help_needed", {
    "problem": "Need algorithm optimization",
    "context": {"algorithm": "E8 alignment"}
})
print("   [Executor] 🆘 Requested help with algorithm optimization")

# Simulate helper response
time.sleep(0.5)
reviewer.broadcast("help_offered", {
    "problem": "Need algorithm optimization",
    "solution": "Use cached E8 projections to reduce computation"
})
print("   [Reviewer] 💡 Offered solution")

time.sleep(1)

print()
print("="*60)
print("DEMONSTRATION COMPLETE")
print("="*60)
print()

# Final statistics
print("📊 Final Statistics:")
print()

all_agents = scout.query_agents()
print(f"   • Total agents: {len(all_agents)}")
print(f"   • Events broadcasted: ~15+")
print(f"   • State operations: ~10+")
print(f"   • Activity logs: 3+")

print()
print("✅ All agents collaborated successfully in real-time!")
print()

# Cleanup
print("🧹 Disconnecting agents...")
scout.disconnect()
prioritizer.disconnect()
executor.disconnect()
reviewer.disconnect()

print()
print("✨ Demo complete!")
