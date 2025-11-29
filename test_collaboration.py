#!/usr/bin/env python3
"""
End-to-End Collaboration System Test
Tests all components of the real-time collaboration infrastructure
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "qa_agents" / "cli"))

from qa_agent_base import CollaborativeAgent

# Test results
results = {
    "tests_run": 0,
    "tests_passed": 0,
    "tests_failed": 0,
    "failures": []
}


def test(name):
    """Decorator for test functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            results["tests_run"] += 1
            print(f"\n{'='*60}")
            print(f"TEST {results['tests_run']}: {name}")
            print('='*60)
            try:
                func(*args, **kwargs)
                results["tests_passed"] += 1
                print(f"✅ PASSED: {name}")
                return True
            except Exception as e:
                results["tests_failed"] += 1
                results["failures"].append({"test": name, "error": str(e)})
                print(f"❌ FAILED: {name}")
                print(f"   Error: {e}")
                import traceback
                traceback.print_exc()
                return False
        return wrapper
    return decorator


@test("Agent Connection")
def test_agent_connection():
    """Test basic agent connection to collaboration bus"""
    print("Creating test agent...")
    agent = CollaborativeAgent("test_agent_1", auto_connect=True)

    assert agent.connected, "Agent not connected to bus"
    assert agent.collaborative, "Agent not in collaborative mode"
    print(f"   Agent ID: {agent.agent_id}")
    print(f"   Agent Name: {agent.name}")
    print(f"   Connected: {agent.connected}")

    agent.disconnect()
    print("   Disconnected successfully")


@test("Multiple Agent Registration")
def test_multiple_agents():
    """Test multiple agents connecting simultaneously"""
    print("Creating 3 test agents...")
    agents = []

    for i in range(3):
        agent = CollaborativeAgent(f"test_agent_{i+2}", auto_connect=True)
        agents.append(agent)
        print(f"   Agent {i+1}: {agent.name} (ID: {agent.agent_id})")
        time.sleep(0.5)

    # First agent queries all others
    all_agents = agents[0].query_agents()
    print(f"   Total agents visible: {len(all_agents)}")

    for agent_info in all_agents:
        print(f"      • {agent_info['name']} - {agent_info['status']}")

    assert len(all_agents) >= 3, f"Expected at least 3 agents, got {len(all_agents)}"

    # Cleanup
    for agent in agents:
        agent.disconnect()


@test("Event Broadcasting and Subscription")
def test_events():
    """Test event broadcasting and subscription"""
    print("Setting up publisher and subscriber...")

    # Create publisher
    publisher = CollaborativeAgent("publisher", auto_connect=True)
    time.sleep(1)

    # Create subscriber
    subscriber = CollaborativeAgent("subscriber", auto_connect=True)
    time.sleep(1)

    # Subscribe to test topic
    subscriber.subscribe("test_event")
    print("   Subscriber listening to: test_event")

    # Track received events
    received_events = []

    def event_handler(data):
        received_events.append(data)
        print(f"   📨 Event received: {data.get('payload', {}).get('data', {})}")

    subscriber.on("test_event", event_handler)

    # Give subscriber time to set up
    time.sleep(1)

    # Publish event
    print("   📤 Publishing event...")
    publisher.broadcast("test_event", {
        "message": "Hello from publisher!",
        "timestamp": datetime.now().isoformat()
    })

    # Wait for event delivery
    time.sleep(2)

    print(f"   Events received: {len(received_events)}")

    assert len(received_events) > 0, "No events received"

    # Cleanup
    publisher.disconnect()
    subscriber.disconnect()


@test("Shared State Management")
def test_shared_state():
    """Test shared state get/set operations"""
    print("Testing shared state...")

    agent1 = CollaborativeAgent("state_writer", auto_connect=True)
    time.sleep(0.5)

    agent2 = CollaborativeAgent("state_reader", auto_connect=True)
    time.sleep(0.5)

    # Agent 1 writes state
    test_key = "test_key_" + str(int(time.time()))
    test_value = {"data": "test_value", "number": 42}

    print(f"   Agent 1 writing: {test_key} = {test_value}")
    success = agent1.set_state(test_key, test_value)
    assert success, "Failed to set state"

    time.sleep(1)

    # Agent 2 reads state
    print(f"   Agent 2 reading: {test_key}")
    retrieved = agent2.get_state(test_key)
    print(f"   Retrieved: {retrieved}")

    assert retrieved is not None, "Failed to retrieve state"
    assert retrieved == test_value, f"State mismatch: {retrieved} != {test_value}"

    # Cleanup
    agent1.disconnect()
    agent2.disconnect()


@test("Agent Discovery and Filtering")
def test_agent_discovery():
    """Test querying agents with filters"""
    print("Creating agents with different roles...")

    scout = CollaborativeAgent("scout", auto_connect=True,
                               metadata={"role": "discovery"})
    time.sleep(0.5)

    executor = CollaborativeAgent("executor", auto_connect=True,
                                  metadata={"role": "execution"})
    time.sleep(0.5)

    reviewer = CollaborativeAgent("reviewer", auto_connect=True,
                                  metadata={"role": "validation"})
    time.sleep(0.5)

    # Query all agents
    all_agents = scout.query_agents()
    print(f"   Total agents: {len(all_agents)}")

    # Query by name
    scouts = scout.query_agents({"name": "scout"})
    print(f"   Scouts found: {len(scouts)}")
    assert len(scouts) >= 1, "Scout not found"

    # Cleanup
    scout.disconnect()
    executor.disconnect()
    reviewer.disconnect()


@test("Activity Logging")
def test_activity_logging():
    """Test activity logging functionality"""
    print("Testing activity logging...")

    agent = CollaborativeAgent("logger", auto_connect=True)
    time.sleep(1)

    # Log some activities
    activities = [
        ("task_started", {"task_id": "TASK-001"}),
        ("processing", {"progress": 50}),
        ("task_completed", {"task_id": "TASK-001", "result": "success"})
    ]

    for action, details in activities:
        print(f"   Logging: {action}")
        agent.log_activity(action, details)
        time.sleep(0.3)

    # Retrieve logged activities
    time.sleep(1)
    logged = agent.get_state(f"activities:{agent.agent_id}")

    print(f"   Activities logged: {len(logged) if logged else 0}")

    if logged:
        for activity in logged:
            print(f"      • {activity['action']} - {activity['timestamp']}")

    assert logged is not None, "No activities retrieved"
    assert len(logged) >= 3, f"Expected 3+ activities, got {len(logged)}"

    agent.disconnect()


@test("Concurrent Operations")
def test_concurrent_operations():
    """Test multiple agents operating concurrently"""
    print("Testing concurrent operations...")

    agents = []
    num_agents = 5

    # Create multiple agents
    for i in range(num_agents):
        agent = CollaborativeAgent(f"concurrent_{i}", auto_connect=True)
        agents.append(agent)
        time.sleep(0.2)

    print(f"   Created {num_agents} concurrent agents")

    # Each agent broadcasts an event
    print("   All agents broadcasting...")
    for i, agent in enumerate(agents):
        agent.broadcast("concurrent_test", {
            "agent_index": i,
            "message": f"Message from agent {i}"
        })

    time.sleep(1)

    # Each agent sets a state value
    print("   All agents setting state...")
    for i, agent in enumerate(agents):
        agent.set_state(f"concurrent_key_{i}", f"value_{i}")

    time.sleep(1)

    # Verify all states
    print("   Verifying states...")
    for i in range(num_agents):
        value = agents[0].get_state(f"concurrent_key_{i}")
        assert value == f"value_{i}", f"State mismatch for key {i}"

    print("   All concurrent operations successful!")

    # Cleanup
    for agent in agents:
        agent.disconnect()


@test("Heartbeat and Connection Monitoring")
def test_heartbeat():
    """Test heartbeat mechanism"""
    print("Testing heartbeat...")

    agent = CollaborativeAgent("heartbeat_test", auto_connect=True)
    time.sleep(2)

    # Query to see if agent is still registered
    agents = agent.query_agents({"name": "heartbeat_test"})

    assert len(agents) > 0, "Agent not found in registry"

    agent_info = agents[0]
    print(f"   Agent status: {agent_info['status']}")
    print(f"   Last heartbeat: {agent_info.get('last_heartbeat', 'N/A')}")

    assert agent_info['status'] == 'active', "Agent not active"

    agent.disconnect()


@test("MCP Server Availability")
def test_mcp_server():
    """Test MCP server can be started"""
    print("Testing MCP server...")

    mcp_server_path = Path(__file__).parent / "qa_mcp_servers" / "qa-collab" / "server.py"

    assert mcp_server_path.exists(), f"MCP server not found at {mcp_server_path}"
    print(f"   MCP server exists: {mcp_server_path}")

    # Try to import it
    import subprocess

    # Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": "test_client"
            }
        }
    }

    print("   Starting MCP server...")
    proc = subprocess.Popen(
        ["python3", str(mcp_server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give it time to start
    time.sleep(2)

    try:
        # Send initialize request
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()

        # Try to read response (with timeout)
        import select
        ready, _, _ = select.select([proc.stdout], [], [], 3)

        if ready:
            response = proc.stdout.readline()
            print(f"   MCP Response received: {len(response)} bytes")

            if response:
                data = json.loads(response)
                print(f"   MCP Protocol: {data.get('result', {}).get('protocolVersion', 'N/A')}")
                print(f"   MCP Server: {data.get('result', {}).get('serverInfo', {}).get('name', 'N/A')}")
        else:
            print("   ⚠️  No response from MCP server (timeout)")

    finally:
        proc.terminate()
        proc.wait(timeout=2)

    print("   MCP server test completed")


def run_all_tests():
    """Run all tests and generate report"""
    print("\n" + "="*60)
    print("QA COLLABORATION SYSTEM - END-TO-END TEST SUITE")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Run all tests
    test_agent_connection()
    test_multiple_agents()
    test_events()
    test_shared_state()
    test_agent_discovery()
    test_activity_logging()
    test_concurrent_operations()
    test_heartbeat()
    test_mcp_server()

    # Generate report
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Tests:  {results['tests_run']}")
    print(f"Passed:       {results['tests_passed']} ✅")
    print(f"Failed:       {results['tests_failed']} ❌")
    print(f"Success Rate: {(results['tests_passed']/results['tests_run']*100):.1f}%")

    if results['failures']:
        print("\nFailed Tests:")
        for failure in results['failures']:
            print(f"  ❌ {failure['test']}")
            print(f"     {failure['error']}")

    print("\n" + "="*60)
    print(f"Completed: {datetime.now().isoformat()}")
    print("="*60)

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": results['tests_run'],
            "passed": results['tests_passed'],
            "failed": results['tests_failed'],
            "success_rate": results['tests_passed']/results['tests_run']*100
        },
        "failures": results['failures']
    }

    report_file = Path(__file__).parent / "logs" / "collab_test_report.json"
    report_file.write_text(json.dumps(report, indent=2))
    print(f"\n📄 Report saved to: {report_file}")

    return results['tests_failed'] == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
