#!/usr/bin/env python3
"""
Smoke Test for Specialized QA Agents

This script runs a series of simple checks on the specialized QA agents
(Vision, LIDAR, Spectral) to ensure they can be instantiated and can
load their respective data.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from qa_agents.cli.qa_vision_agent import VisionQAAgent
from qa_agents.cli.qa_lidar_agent import LidarQAAgent
from qa_agents.cli.qa_spectral_agent import SpectralQAAgent

def smoke_test_vision_agent(base_path):
    """Smoke test for the VisionQAAgent."""
    print("--- Testing VisionQAAgent ---")
    try:
        agent = VisionQAAgent(base_path)
        print("  [+] VisionQAAgent instantiated successfully.")
        
        # Test data loading
        can_load = agent.load_vision_data()
        if can_load:
            print("  [+] VisionQAAgent data loading successful.")
            return True
        else:
            print("  [-] VisionQAAgent data loading failed.")
            return False
    except Exception as e:
        print(f"  [-] VisionQAAgent test failed: {e}")
        return False

def smoke_test_lidar_agent(base_path):
    """Smoke test for the LidarQAAgent."""
    print("--- Testing LidarQAAgent ---")
    try:
        agent = LidarQAAgent(base_path)
        print("  [+] LidarQAAgent instantiated successfully.")
        
        # Test data loading
        can_load = agent.load_lidar_data()
        if can_load:
            print("  [+] LidarQAAgent data loading successful.")
            return True
        else:
            print("  [-] LidarQAAgent data loading failed.")
            return False
    except Exception as e:
        print(f"  [-] LidarQAAgent test failed: {e}")
        return False

def smoke_test_spectral_agent(base_path):
    """Smoke test for the SpectralQAAgent."""
    print("--- Testing SpectralQAAgent ---")
    try:
        agent = SpectralQAAgent(base_path)
        print("  [+] SpectralQAAgent instantiated successfully.")
        
        # Test data loading
        can_load = agent.load_hsi_data()
        if can_load:
            print("  [+] SpectralQAAgent data loading successful.")
            return True
        else:
            print("  [-] SpectralQAAgent data loading failed.")
            return False
    except Exception as e:
        print(f"  [-] SpectralQAAgent test failed: {e}")
        return False

def main():
    """Main function to run all smoke tests."""
    base_path = Path('.')
    
    print("--- Running Smoke Tests for Specialized QA Agents ---")
    
    vision_ok = smoke_test_vision_agent(base_path)
    lidar_ok = smoke_test_lidar_agent(base_path)
    spectral_ok = smoke_test_spectral_agent(base_path)
    
    print("\n--- Unified Status Report ---")
    print(f"  Vision Agent:   {'PASS' if vision_ok else 'FAIL'}")
    print(f"  LIDAR Agent:    {'PASS' if lidar_ok else 'FAIL'}")
    print(f"  Spectral Agent: {'PASS' if spectral_ok else 'FAIL'}")
    
    if vision_ok and lidar_ok and spectral_ok:
        print("\nAll specialized agents passed the smoke test.")
        sys.exit(0)
    else:
        print("\nOne or more specialized agents failed the smoke test.")
        sys.exit(1)

if __name__ == "__main__":
    main()
