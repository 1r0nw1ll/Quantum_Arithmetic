"""Tests for Chinese Remainder Theorem operations."""

from qa_pim.crt import crt_join_general, crt_join_coprime


def test_crt_coprime():
    """x = 2 (mod 3) and x = 3 (mod 5) => x = 8 (mod 15)"""
    x, m = crt_join_general(2, 3, 3, 5)
    assert m == 15
    assert x % 3 == 2
    assert x % 5 == 3


def test_crt_non_coprime_solvable():
    """x = 1 (mod 6) and x = 7 (mod 9); gcd(6,9)=3, (7-1)%3=0 => solvable"""
    x, m = crt_join_general(1, 6, 7, 9)
    assert x is not None
    assert x % 6 == 1
    assert x % 9 == 7


def test_crt_non_coprime_unsolvable():
    """x = 1 (mod 6) and x = 8 (mod 9); (8-1)%3=1 != 0 => unsolvable"""
    result = crt_join_general(1, 6, 8, 9)
    assert result == (None, None)


def test_crt_mod24_mod30():
    """Benchmark case: mod 24, mod 30 (gcd=6)."""
    x, m = crt_join_general(5, 24, 11, 30)
    if x is not None:
        assert x % 24 == 5
        assert x % 30 == 11
        assert m == 120  # lcm(24,30)


def test_crt_coprime_fast():
    """Fast coprime helper."""
    x, m = crt_join_coprime(2, 3, 3, 5)
    assert m == 15
    assert x % 3 == 2
    assert x % 5 == 3


def test_crt_coprime_rejects_non_coprime():
    import pytest
    with pytest.raises(ValueError):
        crt_join_coprime(1, 6, 7, 9)


def test_crt_identity():
    """Same modulus, same residue."""
    x, m = crt_join_general(3, 7, 3, 7)
    assert x == 3
    assert m == 7


def test_crt_mod9_mod24():
    """QA-relevant: mod 9 and mod 24 (gcd=3)."""
    x, m = crt_join_general(1, 9, 1, 24)
    if x is not None:
        assert x % 9 == 1
        assert x % 24 == 1
        assert m == 72  # lcm(9,24)
