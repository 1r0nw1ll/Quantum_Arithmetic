#!/usr/bin/env python3
"""
test_rust_backend.py - Pure PyO3 test for Rust backend

Tests qa_lab_rs.compute_bundle_py against manual formula calculations.
No torch, no numpy - pure Python and Rust.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_compute_bundle_py():
    """Test that Rust compute_bundle_py matches manual calculations"""
    try:
        import qa_lab_rs
    except ImportError as e:
        print(f"❌ Rust backend not available: {e}")
        return False

    # Test cases: (b, e, d, a)
    test_cases = [
        (1.0, 2.0, 3.0, 5.0),  # Grant's LRT
        (3.0, 5.0, 8.0, 13.0), # Satellite family
        (9.0, 9.0, 18.0, 27.0), # Singularity
        (0.5, 1.5, 2.0, 3.5),  # Random valid
    ]

    for b, e, d, a in test_cases:
        print(f"Testing QA tuple: ({b}, {e}, {d}, {a})")

        # Get Rust result
        rust_result = qa_lab_rs.compute_bundle_py(b, e, d, a)

        # Manual calculations (canonical invariants)
        manual = {
            'b': b,
            'e': e,
            'd': d,
            'a': a,
            'J': b * d,           # perigee
            'K': d * a,           # apogee
            'X': e * d,           # half focal distance
            'W': (e * d) + (d * a),  # X + K
            'Y': (a * a) - (d * d),  # A - D
            'Z': (e * e) + (d * a),  # E + K
            'C': 2.0 * e * d,     # focal separation
            'F': b * a,           # altitude
            'G': (e * e) + (d * d),  # hypotenuse
        }

        # Check all invariants match
        for key in ['J', 'K', 'X', 'W', 'Y', 'Z', 'C', 'F', 'G']:
            rust_val = rust_result.get(key)
            manual_val = manual[key]
            if abs(rust_val - manual_val) > 1e-10:
                print(f"❌ Mismatch in {key}: Rust={rust_val}, Manual={manual_val}")
                return False

        print(f"✅ All invariants match for ({b}, {e}, {d}, {a})")

    return True

def test_ping():
    """Test basic Rust module availability"""
    try:
        import qa_lab_rs
        result = qa_lab_rs.ping()
        expected = "qa_lab_rs:ok"
        if result == expected:
            print(f"✅ Ping successful: {result}")
            return True
        else:
            print(f"❌ Ping failed: got {result}, expected {expected}")
            return False
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Rust Backend (qa_lab_rs)")
    print("=" * 40)

    tests = [
        ("Ping Test", test_ping),
        ("Compute Bundle Test", test_compute_bundle_py),
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
        print("🎉 All Rust backend tests PASSED!")
        return 0
    else:
        print("💥 Some tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())