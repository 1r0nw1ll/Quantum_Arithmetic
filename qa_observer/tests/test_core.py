"""Tests for QA Observer Core primitives."""

QA_COMPLIANCE = "observer=test_harness, state_alphabet=none"

import numpy as np
import pytest
from qa_observer.core import qa_mod, compute_qci, classify_orbit


# ---- qa_mod: A1 compliance ----

class TestQaMod:
    def test_basic(self):
        assert qa_mod(1, 24) == 1
        assert qa_mod(24, 24) == 24
        assert qa_mod(25, 24) == 1

    def test_never_returns_zero(self):
        """A1: output must be in {1,...,m} for all inputs."""
        for m in [9, 24]:
            for x in range(-100, 200):
                result = qa_mod(x, m)
                assert 1 <= result <= m, f"qa_mod({x}, {m}) = {result}"

    def test_modulus_9(self):
        assert qa_mod(9, 9) == 9
        assert qa_mod(10, 9) == 1
        assert qa_mod(18, 9) == 9

    def test_zero_input(self):
        """qa_mod(0, m) should return m (wraps to top)."""
        assert qa_mod(0, 24) == 24
        assert qa_mod(0, 9) == 9

    def test_negative_input(self):
        """Negative inputs should still produce valid A1 output."""
        assert 1 <= qa_mod(-1, 24) <= 24
        assert 1 <= qa_mod(-24, 24) <= 24

    def test_matches_original_formula(self):
        """Verify matches the canonical formula from script 46."""
        for x in range(1, 100):
            assert qa_mod(x, 24) == ((x - 1) % 24) + 1


# ---- compute_qci ----

class TestComputeQci:
    def test_deterministic(self):
        labels = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
        cmap = {0: 8, 1: 16, 2: 24}
        r1 = compute_qci(labels, cmap, 24, 3)
        r2 = compute_qci(labels, cmap, 24, 3)
        np.testing.assert_array_equal(
            np.asarray(r1, dtype=float),
            np.asarray(r2, dtype=float),
        )

    def test_output_length(self):
        labels = list(range(20))
        cmap = {i: i + 1 for i in range(20)}
        result = compute_qci(labels, cmap, 24, 5)
        assert len(result) == 18  # len(labels) - 2

    def test_known_match_rate(self):
        """Verify QCI computes correct match rate for known sequence.

        Sequence [0,1,2] repeating with cmap {0:8, 1:16, 2:24}:
        - Triple (0,1,2): qa_mod(8+16,24)=24, actual=24 -> MATCH
        - Triple (1,2,0): qa_mod(16+24,24)=16, actual=8 -> NO
        - Triple (2,0,1): qa_mod(24+8,24)=8, actual=16 -> NO
        So 1/3 of triples match.
        """
        cmap = {0: 8, 1: 16, 2: 24}
        labels = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2]
        result = compute_qci(labels, cmap, 24, 3)
        arr = np.asarray(result, dtype=float)
        # Last value should be ~1/3 (1 match per 3 triples)
        assert abs(arr[-1] - 1.0 / 3.0) < 0.01

    def test_default_state_used(self):
        """Unmapped labels should use default_state."""
        labels = [0, 99, 0, 0, 0]  # 99 not in cmap
        cmap = {0: 8}
        result = compute_qci(labels, cmap, 24, 2, default_state=5)
        assert len(result) == 3  # len - 2

    def test_numpy_array_input(self):
        labels = np.array([0, 1, 2, 0, 1])
        cmap = {0: 8, 1: 16, 2: 24}
        result = compute_qci(labels, cmap, 24, 2)
        assert len(result) == 3


# ---- classify_orbit ----

class TestClassifyOrbit:
    def test_cosmos(self):
        assert classify_orbit(24) == "cosmos"

    def test_satellite(self):
        assert classify_orbit(8) == "satellite"

    def test_singularity(self):
        assert classify_orbit(1) == "singularity"

    def test_other(self):
        assert classify_orbit(12) == "orbit_12"
