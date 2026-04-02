"""Chinese Remainder Theorem with general (non-coprime) moduli support."""

import math
from typing import Optional, Tuple


def extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
    """Extended Euclidean algorithm.  Returns (gcd, x, y) where ax + by = gcd."""
    if a == 0:
        return b, 0, 1
    gcd, x1, y1 = extended_gcd(b % a, a)
    x = y1 - (b // a) * x1
    y = x1
    return gcd, x, y


def crt_join_general(
    a1: int, m1: int, a2: int, m2: int,
) -> Tuple[Optional[int], Optional[int]]:
    """General CRT join handling non-coprime moduli.

    Solves:  x = a1 (mod m1)  and  x = a2 (mod m2)
    Returns (x, lcm(m1, m2)) if solvable, (None, None) otherwise.
    """
    gcd = math.gcd(m1, m2)

    if (a2 - a1) % gcd != 0:
        return None, None

    lcm = (m1 * m2) // gcd

    if gcd == 1:
        _, inv1, _ = extended_gcd(m1, m2)
        x = (a1 + m1 * ((a2 - a1) * inv1 % m2)) % lcm
    else:
        m1_red = m1 // gcd
        m2_red = m2 // gcd
        _, inv, _ = extended_gcd(m1_red, m2_red)
        t = ((a2 - a1) // gcd * inv) % m2_red
        x = (a1 + m1 * t) % lcm

    return x, lcm


def crt_join_coprime(a1: int, m1: int, a2: int, m2: int) -> Tuple[int, int]:
    """Fast CRT join for coprime moduli."""
    if math.gcd(m1, m2) != 1:
        raise ValueError("Moduli must be coprime")

    _, inv1, _ = extended_gcd(m1, m2)
    x = (a1 + m1 * ((a2 - a1) * inv1 % m2)) % (m1 * m2)
    return x, m1 * m2
