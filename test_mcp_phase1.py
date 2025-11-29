#!/usr/bin/env python3
"""
Phase 1 MCP Integration Test
Tests MCP client and QA Right Triangle server
"""

import sys
import json
from pathlib import Path

# Add qa_agents to path
sys.path.insert(0, str(Path(__file__).parent))

from qa_agents.cli.mcp_client import MCPClient


def test_mcp_server_list_tools():
    """Test 1: MCP server lists tools correctly"""
    print("=" * 60)
    print("Test 1: List MCP Tools")
    print("=" * 60)

    server_path = Path(__file__).parent / "qa_mcp_servers/qa-right-triangle/server.py"

    try:
        with MCPClient(['python3', str(server_path)]) as client:
            tools = client.list_tools()

            print(f"✅ Server started successfully")
            print(f"✅ Found {len(tools)} tool(s)")

            for tool in tools:
                print(f"\n📦 Tool: {tool['name']}")
                print(f"   Description: {tool.get('description', 'N/A')}")
                print(f"   Input schema: {json.dumps(tool.get('inputSchema', {}), indent=6)}")

            return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_mcp_qa_compute_triangle():
    """Test 2: Call qa_compute_triangle with Fibonacci tuple"""
    print("\n" + "=" * 60)
    print("Test 2: Compute QA Triangle (Fibonacci: b=1, e=1)")
    print("=" * 60)

    server_path = Path(__file__).parent / "qa_mcp_servers/qa-right-triangle/server.py"

    try:
        with MCPClient(['python3', str(server_path)]) as client:
            result = client.call_tool("qa_compute_triangle", {"b": 1.0, "e": 1.0})

            print("✅ Tool call successful\n")

            # Extract JSON result
            if 'content' in result:
                for content_item in result['content']:
                    if content_item['type'] == 'json':
                        data = content_item['json']

                        print("QA Tuple:")
                        print(f"  b = {data['qa_tuple']['b']}")
                        print(f"  e = {data['qa_tuple']['e']}")
                        print(f"  d = {data['qa_tuple']['d']} (expected: 2.0)")
                        print(f"  a = {data['qa_tuple']['a']} (expected: 3.0)")

                        print("\nInvariants:")
                        for key, value in data['invariants'].items():
                            print(f"  {key} = {value}")

                        print("\nTriangle Properties:")
                        for key, value in data['triangle'].items():
                            print(f"  {key} = {value}")

                        print("\nModular Classification:")
                        for key, value in data['modular'].items():
                            print(f"  {key} = {value}")

                        print("\nMetadata:")
                        for key, value in data['metadata'].items():
                            print(f"  {key} = {value}")

                        # Verify QA invariants
                        assert data['qa_tuple']['d'] == 2.0, "d should be 2.0"
                        assert data['qa_tuple']['a'] == 3.0, "a should be 3.0"
                        assert data['invariants']['J'] == 2.0, "J should be 2.0 (b*d)"
                        assert data['invariants']['X'] == 2.0, "X should be 2.0 (e*d)"

                        print("\n✅ All QA invariants verified!")

            return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mcp_lucas_tuple():
    """Test 3: Call qa_compute_triangle with Lucas tuple"""
    print("\n" + "=" * 60)
    print("Test 3: Compute QA Triangle (Lucas: b=2, e=1)")
    print("=" * 60)

    server_path = Path(__file__).parent / "qa_mcp_servers/qa-right-triangle/server.py"

    try:
        with MCPClient(['python3', str(server_path)]) as client:
            result = client.call_tool("qa_compute_triangle", {"b": 2.0, "e": 1.0})

            print("✅ Tool call successful\n")

            if 'content' in result:
                for content_item in result['content']:
                    if content_item['type'] == 'json':
                        data = content_item['json']

                        print("QA Tuple:")
                        print(f"  b = {data['qa_tuple']['b']}")
                        print(f"  e = {data['qa_tuple']['e']}")
                        print(f"  d = {data['qa_tuple']['d']} (expected: 3.0)")
                        print(f"  a = {data['qa_tuple']['a']} (expected: 4.0)")

                        print(f"\nClassification: {data['modular']['classification']}")
                        print(f"Lucas-like: {data['metadata']['lucas_like']}")

                        # Verify
                        assert data['qa_tuple']['d'] == 3.0
                        assert data['qa_tuple']['a'] == 4.0
                        assert data['metadata']['lucas_like'] == True

                        print("\n✅ Lucas tuple verified!")

            return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_mcp_error_handling():
    """Test 4: Test error handling for invalid inputs"""
    print("\n" + "=" * 60)
    print("Test 4: Error Handling (negative values)")
    print("=" * 60)

    server_path = Path(__file__).parent / "qa_mcp_servers/qa-right-triangle/server.py"

    try:
        with MCPClient(['python3', str(server_path)]) as client:
            try:
                # This should raise an error
                result = client.call_tool("qa_compute_triangle", {"b": -1.0, "e": 1.0})
                print("❌ Should have raised an error for negative input")
                return False
            except Exception as e:
                print(f"✅ Correctly handled invalid input: {e}")
                return True

    except Exception as e:
        print(f"❌ Test failed unexpectedly: {e}")
        return False


def main():
    """Run all Phase 1 MCP tests"""
    print("\n" + "=" * 60)
    print("QA Lab MCP Integration - Phase 1 Tests")
    print("=" * 60)
    print()

    tests = [
        test_mcp_server_list_tools,
        test_mcp_qa_compute_triangle,
        test_mcp_lucas_tuple,
        test_mcp_error_handling
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"❌ {test_func.__name__} crashed: {e}")
            results.append((test_func.__name__, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All Phase 1 tests passed!")
        print("\nNext steps:")
        print("  1. Review QA_LAB_MCP_INTEGRATION_PLAN.md for Phase 2 (Docker)")
        print("  2. Run: cd qa_lab && make mcp-build")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
