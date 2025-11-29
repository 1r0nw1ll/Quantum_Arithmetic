#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))
from qa_agent_base import CollaborativeAgent

agent = CollaborativeAgent("status_check", auto_connect=True)
agents = agent.query_agents()
print(f"\n✅ Active agents: {len(agents)}")
for a in agents:
    print(f"   • {a['name']} ({a['status']})")
agent.disconnect()
