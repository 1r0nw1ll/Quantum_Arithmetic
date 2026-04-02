"""Tests for PIM-style kernels."""

import numpy as np
from qa_pim.kernels import (
    RESIDUE_SELECT, TORUS_SHIFT, RADD_m, RMUL_m,
    MIRROR4, ROLLING_SUM_PHASE,
)


def test_residue_select():
    sectors = np.array([0, 1, 2, 1, 0, 3, 2, 1])
    mask = {1, 3}
    result = RESIDUE_SELECT(sectors, mask)
    expected = np.array([False, True, False, True, False, True, False, True])
    assert np.array_equal(result, expected)


def test_torus_shift():
    arr = np.array([10, 20, 30])
    result = TORUS_SHIFT(arr, 5, 25)
    expected = np.array([15, 0, 10])
    assert np.array_equal(result, expected)


def test_radd_m():
    a = np.array([5, 10, 15])
    b = np.array([3, 7, 2])
    result = RADD_m(a, b, 12)
    expected = np.array([8, 5, 5])
    assert np.array_equal(result, expected)


def test_rmul_m():
    a = np.array([5, 10, 15])
    b = np.array([3, 7, 2])
    result = RMUL_m(a, b, 12)
    expected = np.array([3, 10, 6])
    assert np.array_equal(result, expected)


def test_radd_scalar():
    assert RADD_m(5, 8, 9) == 4


def test_rmul_scalar():
    assert RMUL_m(5, 7, 12) == 11


def test_mirror4():
    arr = np.array([1, 2, 3, 4, 5, 6, 7, 8])
    result = MIRROR4(arr)
    assert len(result) == len(arr)
    # q1=[3,4] q3=[7,8] reversed=[8,7]
    # fold: (3+8)//2=5, (4+7)//2=5
    assert result[2] == 5
    assert result[3] == 5


def test_mirror4_rejects_bad_length():
    import pytest
    with pytest.raises(ValueError):
        MIRROR4(np.array([1, 2, 3]))


def test_rolling_sum_phase():
    values = np.array([1, 2, 3, 4, 5])
    result = ROLLING_SUM_PHASE(values, width=3)
    assert len(result) == 5
    assert result[0] == 6  # 1+2+3


def test_rolling_sum_phase_with_modulus():
    values = np.array([10, 20, 30, 40, 50])
    result = ROLLING_SUM_PHASE(values, width=3, m=24)
    assert len(result) == 5
    # 10+20+30=60, 60%24=12
    assert result[0] == 12


def test_rolling_sum_full_width():
    values = np.array([1, 2, 3])
    result = ROLLING_SUM_PHASE(values, width=5)
    assert np.all(result == 6)
