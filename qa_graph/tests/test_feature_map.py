"""Tests for QA feature map dimensions and correctness."""

QA_COMPLIANCE = "observer=test_harness, state_alphabet=none"

import math
import numpy as np
import pytest
from qa_graph.feature_map import (
    qa_feature_vector,
    compute_qa_invariants,
    CANONICAL_21, EXPANDED_6, DERIVED_21, MODULAR_12, PHYSICAL_14, ML_9,
)


class TestFeatureVectorDimensions:
    def test_qa21_dimension(self):
        vec, names = qa_feature_vector(1, 1, mode="qa21")
        assert len(vec) == 21
        assert len(names) == 21

    def test_qa27_dimension(self):
        vec, names = qa_feature_vector(1, 1, mode="qa27")
        assert len(vec) == 27
        assert len(names) == 27

    def test_qa83_dimension(self):
        vec, names = qa_feature_vector(1, 1, mode="qa83")
        assert len(vec) == 83
        assert len(names) == 83

    def test_name_list_sizes(self):
        assert len(CANONICAL_21) == 21
        assert len(EXPANDED_6) == 6
        assert len(DERIVED_21) == 21
        assert len(MODULAR_12) == 12
        assert len(PHYSICAL_14) == 14
        assert len(ML_9) == 9
        assert 21 + 6 + 21 + 12 + 14 + 9 == 83

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            qa_feature_vector(1, 1, mode="qa999")


class TestInvariantCorrectness:
    def test_fibonacci_seed(self):
        """(1,1,2,3) — the fundamental QA tuple."""
        inv = compute_qa_invariants(1, 1)
        assert inv["b"] == 1
        assert inv["e"] == 1
        assert inv["d"] == 2  # b + e
        assert inv["a"] == 3  # b + 2e

    def test_derived_coords(self):
        """A2: d = b+e, a = b+2e — always derived."""
        for b, e in [(1, 1), (3, 5), (2, 1), (8, 13)]:
            inv = compute_qa_invariants(b, e)
            assert inv["d"] == b + e
            assert inv["a"] == b + 2 * e

    def test_squares_use_multiply(self):
        """S1: B=b*b, not b**2."""
        inv = compute_qa_invariants(3, 5)
        assert inv["B"] == 9    # 3*3
        assert inv["E"] == 25   # 5*5
        assert inv["D"] == 64   # 8*8
        assert inv["A"] == 169  # 13*13

    def test_triangle_identity(self):
        """C^2 + F^2 = G^2 (chromogeometry theorem)."""
        for b, e in [(1, 1), (1, 2), (3, 5), (8, 13)]:
            inv = compute_qa_invariants(b, e)
            C, F, G = inv["C"], inv["F"], inv["G"]
            assert abs(C * C + F * F - G * G) < 1e-10

    def test_L_integer_for_fibonacci(self):
        """L = CF/12 should be integer for Fibonacci-adjacent tuples."""
        inv = compute_qa_invariants(1, 1)
        # C=4, F=3, L=12/12=1
        assert inv["L"] == 1.0

    def test_H_and_I(self):
        inv = compute_qa_invariants(1, 2)
        C, F = inv["C"], inv["F"]
        assert inv["H"] == C + F
        assert inv["I"] == abs(C - F)

    def test_no_nan(self):
        """Feature vectors should not contain NaN."""
        for b, e in [(1, 1), (0, 1), (1, 0), (100, 1)]:
            vec, _ = qa_feature_vector(b, e, mode="qa83")
            assert not np.any(np.isnan(vec)), f"NaN in qa83 for ({b},{e})"
