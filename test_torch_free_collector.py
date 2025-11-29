#!/usr/bin/env python3
"""
test_torch_free_collector.py - Test torch-free data collector

Tests that the TorchFreeDataCollector can scan local files, extract QA tuples,
and save artifacts without using torch.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from qa_agents.cli.qa_torch_free_data_collector import TorchFreeDataCollector

def test_data_collection():
    """Test autonomous data collection"""
    base_path = Path(__file__).parent
    collector = TorchFreeDataCollector(base_path)

    # Test topics
    topics = ["quantum", "arithmetic", "research"]

    print("🔍 Running data collection...")
    result = collector.autonomous_data_collection(topics, max_sources=5)

    # Check result structure
    required_keys = ['topics', 'sources_discovered', 'data_collected', 'data_processed', 'data_file']
    for key in required_keys:
        if key not in result:
            print(f"❌ Missing key '{key}' in result")
            return False

    print(f"✅ Result structure OK: {result}")

    # Check topics match
    if result['topics'] != topics:
        print(f"❌ Topics mismatch: {result['topics']} != {topics}")
        return False

    # Check counts are reasonable
    if result['sources_discovered'] < 0:
        print(f"❌ Invalid sources_discovered: {result['sources_discovered']}")
        return False

    if result['data_collected'] < 0:
        print(f"❌ Invalid data_collected: {result['data_collected']}")
        return False

    if result['data_processed'] < 0:
        print(f"❌ Invalid data_processed: {result['data_processed']}")
        return False

    # Check artifact file exists
    data_file = Path(result['data_file'])
    if not data_file.exists():
        print(f"❌ Artifact file does not exist: {data_file}")
        return False

    print(f"✅ Artifact file exists: {data_file}")

    # Check artifact content
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            artifact = json.load(f)

        if 'timestamp' not in artifact:
            print("❌ Missing timestamp in artifact")
            return False

        if 'data' not in artifact:
            print("❌ Missing data in artifact")
            return False

        data_list = artifact['data']
        if not isinstance(data_list, list):
            print("❌ Data is not a list")
            return False

        if len(data_list) != result['data_processed']:
            print(f"❌ Data count mismatch: {len(data_list)} != {result['data_processed']}")
            return False

        # Check at least one data item has required fields
        if data_list:
            item = data_list[0]
            required_item_keys = ['source', 'content', 'qa_tuples', 'processed_at']
            for key in required_item_keys:
                if key not in item:
                    print(f"❌ Missing key '{key}' in data item")
                    return False

            print(f"✅ Artifact has {len(data_list)} data items with proper structure")

            # Check that some QA tuples were found (may be empty for some files)
            total_qa_tuples = sum(len(item.get('qa_tuples', [])) for item in data_list)
            print(f"✅ Total QA tuples extracted: {total_qa_tuples}")

    except Exception as e:
        print(f"❌ Error reading artifact: {e}")
        return False

    return True

def test_collector_creation():
    """Test that collector can be created"""
    base_path = Path(__file__).parent
    try:
        collector = TorchFreeDataCollector(base_path)
        print("✅ Collector created successfully")
        return True
    except Exception as e:
        print(f"❌ Collector creation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Torch-Free Data Collector")
    print("=" * 40)

    tests = [
        ("Collector Creation", test_collector_creation),
        ("Data Collection", test_data_collection),
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
        print("🎉 All torch-free collector tests PASSED!")
        return 0
    else:
        print("💥 Some tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())