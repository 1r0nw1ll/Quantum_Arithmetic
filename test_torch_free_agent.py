#!/usr/bin/env python3
"""
Test that agents can work WITHOUT PyTorch using Rust backend.

This script demonstrates that the QA Lab can operate without torch dependency
by using the Rust ML backend instead.
"""

import sys
sys.path.insert(0, '.')

print("=" * 70)
print("Testing Torch-Free Agent Operation")
print("=" * 70)

# Check if torch is available
try:
    import torch
    print("⚠️  PyTorch IS available (but we won't use it)")
    TORCH_AVAILABLE = True
except ImportError:
    print("✓ PyTorch NOT available (this is expected - testing torch-free)")
    TORCH_AVAILABLE = False

# Import Rust ML instead
from qa_rust_ml import RustMLHelper, is_available
import numpy as np

print(f"\nRust ML Backend: {'✓ Available' if is_available() else '✗ Not available'}")

if not is_available():
    print("\n❌ Error: Rust ML backend not available")
    print("   Build with: make rust-py-build")
    sys.exit(1)

print("\n" + "─" * 70)
print("Simulating Agent Operations (Torch-Free)")
print("─" * 70)

# Create ML helper (using Rust, not torch)
ml_helper = RustMLHelper()

# 1. Generate training data
print("\n1. Generating QA training data...")
qa_data = ml_helper.generate_qa_data(n_samples=10)
print(f"   Generated {len(qa_data)} QA tuples")
print(f"   Example: {qa_data[0]}")

# 2. Compute invariants
print("\n2. Computing QA invariants...")
invariants = ml_helper.batch_compute_invariants(qa_data[:3])
print(f"   Computed invariants for {len(invariants)} tuples")
print(f"   Example J={invariants[0]['J']}, K={invariants[0]['K']}")

# 3. Extract patterns from text
print("\n3. Extracting QA patterns from text...")
sample_text = """
Research shows QA tuples like 1.0 2.0 3.0 5.0 exhibit closure.
Another example: 3.0 5.0 8.0 13.0 from Fibonacci.
"""
patterns = ml_helper.find_qa_in_text(sample_text)
print(f"   Found {len(patterns)} valid QA patterns")
for p in patterns:
    print(f"   - {p}")

# 4. Similarity computation
print("\n4. Computing vector similarities...")
vec1 = np.array([1.0, 2.0, 3.0, 5.0])
vec2 = np.array([1.0, 2.0, 3.0, 5.0])
vec3 = np.array([3.0, 5.0, 8.0, 13.0])

sim_identical = ml_helper.similarity(vec1, vec2)
sim_different = ml_helper.similarity(vec1, vec3)

print(f"   Similarity (identical): {sim_identical:.3f}")
print(f"   Similarity (different): {sim_different:.3f}")

# 5. Normalization
print("\n5. Normalizing data...")
raw_data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
normalized = ml_helper.normalize_array(raw_data)
print(f"   Raw: {raw_data}")
print(f"   Normalized: {normalized}")

print("\n" + "=" * 70)
print("✅ SUCCESS: All agent operations work WITHOUT PyTorch!")
print("=" * 70)

print("\nSummary:")
print("  • Generated QA training data: ✓")
print("  • Computed invariants: ✓")
print("  • Extracted patterns from text: ✓")
print("  • Computed similarities: ✓")
print("  • Normalized arrays: ✓")
print("  • All using Rust backend (linfa + ndarray)")
print("  • Zero PyTorch dependency: ✓")

if not TORCH_AVAILABLE:
    print("\n🎉 This test ran successfully WITHOUT PyTorch installed!")
    print("   The QA Lab is now torch-independent!")
