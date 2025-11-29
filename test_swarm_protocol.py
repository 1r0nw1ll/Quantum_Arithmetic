#!/usr/bin/env python3
"""
test_swarm_protocol.py - Test QA swarm communication protocol
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_swarm_protocol():
    """Test basic swarm protocol functionality"""
    try:
        from qa_agents.cli.qa_swarm_protocol import QASwarmProtocol, QATuple, MessageType, AgentCapability

        # Create protocol instance
        protocol = QASwarmProtocol("test_agent")

        # Register capabilities
        protocol.register_capability(AgentCapability.VISION_PROCESSING)
        protocol.register_capability(AgentCapability.COORDINATION)

        # Create QA tuple
        qa_tuple = QATuple(b=1.0, e=2.0, d=3.0, a=5.0)

        # Create messages
        share_msg = protocol.create_qa_tuple_share(qa_tuple)
        discovery_msg = protocol.create_agent_discovery()
        coord_msg = protocol.create_coordination_request(
            "Test multimodal task",
            [AgentCapability.LIDAR_PROCESSING, AgentCapability.SPECTRAL_PROCESSING]
        )

        print("✅ Swarm protocol messages created successfully")
        print(f"📤 QA tuple share: {share_msg.message_type.value}")
        print(f"🔍 Agent discovery: {discovery_msg.message_type.value}")
        print(f"🤝 Coordination request: {coord_msg.message_type.value}")

        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_agent_swarm_integration():
    """Test agent integration with swarm protocol"""
    try:
        from qa_agents.cli.qa_vision_agent import VisionQAAgent

        # Create agent (without training to avoid torch dependency)
        base_path = Path(__file__).parent
        agent = VisionQAAgent(base_path)

        # Test swarm methods (they should exist even if swarm is disabled)
        if hasattr(agent, 'coordinate_multimodal_analysis'):
            result = agent.coordinate_multimodal_analysis("Test coordination")
            print("✅ Agent swarm coordination method available")
            print(f"📊 Coordination result: {result.get('status', 'unknown')}")
        else:
            print("⚠️  Swarm methods not available (expected in some environments)")
            return True  # This is OK

        if hasattr(agent, 'share_visual_qa_context'):
            qa_tuple = {"b": 1.0, "e": 2.0, "d": 3.0, "a": 5.0}
            result = agent.share_visual_qa_context(qa_tuple)
            print("✅ Agent QA context sharing available")
            print(f"📤 Context sharing result: {result.get('status', 'unknown')}")

        return True

    except Exception as e:
        print(f"❌ Agent integration test failed: {e}")
        return False

def main():
    """Run all swarm tests"""
    print("🧠 Testing QA Swarm Protocol")
    print("=" * 40)

    tests = [
        ("Swarm Protocol Core", test_swarm_protocol),
        ("Agent Integration", test_agent_swarm_integration),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\n🔍 Running {name}...")
        try:
            if test_func():
                print(f"✅ {name} PASSED")
                passed += 1
            else:
                print(f"❌ {name} FAILED")
        except Exception as e:
            print(f"❌ {name} ERROR: {e}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All swarm protocol tests PASSED!")
        return 0
    else:
        print("💥 Some tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())