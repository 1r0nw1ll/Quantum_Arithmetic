"""
qa_lab.qa_core.algebra
======================
Canonical QA mathematical primitives.

These are the bedrock of QA Lab. Every agent, every cert, every theorem
operates on these definitions. No external dependencies — stdlib only.

Mathematical foundation:
  QA = dynamical system in Z[φ]/mZ[φ]  (ring of integers of Q(√5) mod m)
  Generator Q: Q(b, e) = (e, b+e)  — Fibonacci map, same as ×φ in Z[φ]
  Generator T = Q²: T(b, e) = (b+e, b+2e) = (d, a)
  Norm: f(b, e) = b² + be - e²  = N(b + eφ)  (norm in Q(√5))

Orbit lengths under Q (mod 9):
  cosmos      — length 24   (72 starting pairs)
  satellite   — length 8    (8 pairs)
  singularity — length 1    (1 pair: (m, m))

A1 (No-Zero): states live in {1,...,m}, never {0,...,m-1}.
Substrate rule: ALWAYS use b*b, b*e, e*e — NEVER b**2, e**2
(CPython pow() dispatches to libm; multiplication is exact integer arithmetic)
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Dict, List, Tuple
import math

# Canonical A1-compliant primitives are sourced from the published `qa_arithmetic`
# package (PyPI: qa-arithmetic). qa_lab does NOT re-implement these — we re-export
# them so that qa_lab, qa_observer, and all QA tooling share one source of truth.
from qa_arithmetic import (
    qa_mod as _qa_mod,
    qa_step as _qa_step,
    qa_tuple as _qa_tuple,
    norm_f as _norm_f,
)


# ---------------------------------------------------------------------------
# Canonical moduli and their inert primes in Z[φ]
# ---------------------------------------------------------------------------

INERT_PRIMES: Dict[int, List[int]] = {
    9:  [3],
    24: [3, 7],
    72: [3, 7],
}


# ---------------------------------------------------------------------------
# Core arithmetic
# ---------------------------------------------------------------------------

# Re-exports from qa_arithmetic (canonical source).
qa_mod = _qa_mod
qa_step = _qa_step
qa_tuple = _qa_tuple
qa_norm = _norm_f  # f(b,e) = b²+be−e², N(b+eφ) in Z[φ]


def qa_norm_mod(b: int, e: int, m: int) -> int:
    """Q(√5) norm reduced modulo m."""
    return qa_norm(b, e) % m


def v_p(n: int, p: int) -> int:
    """p-adic valuation of n: largest k such that p^k divides |n|.
    Returns 0 for n == 0.
    """
    if n == 0:
        return 0
    n = abs(n)
    k = 0
    while n % p == 0:
        k += 1
        n //= p
    return k


def is_obstructed(target_r: int, inert_primes: List[int]) -> bool:
    """Return True if v_p(target_r) == 1 for any inert prime p.

    A target norm r with v_p(r) == 1 is NOT in Im(f) mod m, so the
    corresponding state is structurally unreachable — a geometric obstruction.
    """
    return any(v_p(target_r, p) == 1 for p in inert_primes)


def factor_integer(n: int) -> List[Tuple[int, int]]:
    """Prime factorization of |n| as [(p, e), ...] with p ascending."""
    n = abs(int(n))
    if n < 2:
        return []

    factors: List[Tuple[int, int]] = []
    exponent = 0
    while n % 2 == 0:
        exponent += 1
        n //= 2
    if exponent:
        factors.append((2, exponent))

    divisor = 3
    while divisor * divisor <= n:
        exponent = 0
        while n % divisor == 0:
            exponent += 1
            n //= divisor
        if exponent:
            factors.append((divisor, exponent))
        divisor += 2

    if n > 1:
        factors.append((n, 1))
    return factors


def is_prime(n: int) -> bool:
    """Return True if n is prime in Z."""
    factors = factor_integer(n)
    return len(factors) == 1 and factors[0][1] == 1


def is_composite(n: int) -> bool:
    """Return True if n is composite in Z."""
    return abs(int(n)) > 1 and not is_prime(int(n))


def omega(n: int) -> int:
    """Number of distinct prime factors of |n|."""
    return len(factor_integer(n))


def big_omega(n: int) -> int:
    """Number of prime factors of |n| counted with multiplicity."""
    return sum(exponent for _prime, exponent in factor_integer(n))


def is_semiprime(n: int) -> bool:
    """Return True if |n| has exactly two prime factors counted with multiplicity."""
    return big_omega(n) == 2


def is_prime_power(n: int) -> bool:
    """Return True if |n| = p^k with prime p and k >= 2."""
    factors = factor_integer(n)
    return len(factors) == 1 and factors[0][1] >= 2


def is_squarefree(n: int) -> bool:
    """Return True if |n| is not divisible by any p*p."""
    return all(exponent == 1 for _prime, exponent in factor_integer(n))


def smallest_prime_factor(n: int) -> int | None:
    """Smallest prime factor of |n|, or None for |n| < 2."""
    factors = factor_integer(n)
    return None if not factors else factors[0][0]


def largest_prime_factor(n: int) -> int | None:
    """Largest prime factor of |n|, or None for |n| < 2."""
    factors = factor_integer(n)
    return None if not factors else factors[-1][0]


def _allowed_factor_primes(n: int, prime_max: int | None) -> List[int]:
    if prime_max is not None and prime_max < 2:
        return []
    primes = [prime for prime, exponent in factor_integer(n) for _ in range(exponent)]
    if prime_max is None:
        return sorted(primes)
    return sorted(prime for prime in primes if prime <= prime_max)


def largest_prime_leq(limit: int) -> int | None:
    """Largest prime <= limit, or None if no such prime exists."""
    limit = int(limit)
    if limit < 2:
        return None
    candidate = limit
    if candidate == 2:
        return 2
    if candidate % 2 == 0:
        candidate -= 1
    while candidate >= 2:
        if is_prime(candidate):
            return candidate
        candidate -= 2
    return None


def local_certificate_prime_horizon(n: int) -> int:
    """Minimal prime_max needed to certify primehood by absence of witnesses.

    For n < 4, prime/composite status is already exact without checking any
    witness prime, so the horizon is 0. Otherwise this is the largest prime
    <= floor(sqrt(n)).
    """
    n = abs(int(n))
    if n < 4:
        return 0
    horizon = largest_prime_leq(math.isqrt(n))
    return 0 if horizon is None else horizon


def local_certificate_exact_radius(n: int) -> int | None:
    """Smallest local witness radius that yields exact prime/composite status.

    - primes require the full no-witness horizon up to largest prime <= sqrt(n)
    - composites become exact as soon as their smallest prime factor is visible
    - n < 2 has no prime/composite certificate radius
    """
    n = abs(int(n))
    if n < 2:
        return None
    if is_composite(n):
        return smallest_prime_factor(n)
    return local_certificate_prime_horizon(n)


def local_certificate_neighborhood_decision(n: int, prime_max: int) -> str | None:
    """Local bounded-witness decision for a single integer.

    Returns one of:
      - "COMPOSITE": a lawful factor witness exists within the neighborhood
      - "PRIME": no witness exists and the neighborhood reaches the full prime horizon
      - "UNDECIDED": no witness exists, but the neighborhood is too small
      - None: n < 2
    """
    n = abs(int(n))
    if n < 2:
        return None
    if factor_certificate_edges(n, prime_max=prime_max):
        return "COMPOSITE"
    if prime_max >= local_certificate_prime_horizon(n):
        return "PRIME"
    return "UNDECIDED"


def factor_certificate_edges(n: int, prime_max: int | None = None) -> List[Dict[str, int | str]]:
    """Exact divisibility-certificate edges from n to smaller witnesses.

    For composite n, these edges certify explicit factor witnesses:
      - divide_smallest_prime: n -> n / spf(n)
      - divide_largest_prime: n -> n / lpf(n)
      - extract_smallest_prime: n -> spf(n)
      - extract_largest_prime: n -> lpf(n)

    If prime_max is set, only witnesses using primes <= prime_max are allowed.
    Primes and n < 2 have no outgoing composite-certificate edges.
    """
    n = abs(int(n))
    if n < 2 or is_prime(n):
        return []

    allowed_primes = _allowed_factor_primes(n, prime_max)
    if not allowed_primes:
        return []
    spf = allowed_primes[0]
    lpf = allowed_primes[-1]

    edges: List[Dict[str, int | str]] = []
    seen: set[tuple[str, int]] = set()

    candidates = [
        ("divide_smallest_prime", n // spf, spf),
        ("divide_largest_prime", n // lpf, lpf),
        ("extract_smallest_prime", spf, spf),
        ("extract_largest_prime", lpf, lpf),
    ]
    for generator, target, witness_prime in candidates:
        if target < 2:
            continue
        key = (generator, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "source": n,
                "generator": generator,
                "target": target,
                "witness_prime": witness_prime,
            }
        )
    return edges


@lru_cache(maxsize=None)
def _bounded_decomposition_depth(n: int, prime_max: int | None) -> int | None:
    n = abs(int(n))
    if n < 2:
        return None
    if is_prime(n):
        return 0

    next_depths = []
    for edge in factor_certificate_edges(n, prime_max=prime_max):
        target = int(edge["target"])
        depth = _bounded_decomposition_depth(target, prime_max)
        if depth is not None:
            next_depths.append(1 + depth)
    if not next_depths:
        return None
    return min(next_depths)


def decomposition_depth_to_prime_terminal(n: int, prime_max: int | None = None) -> int | None:
    """Shortest exact divisibility-certificate depth from n to a prime terminal.

    Returns:
      - None for n < 2
      - 0 for primes
      - shortest lawful divide-step depth to any prime terminal
      - None if no lawful witness sequence exists under prime_max
    """
    return _bounded_decomposition_depth(abs(int(n)), prime_max)


def factor_chain_to_prime(
    n: int,
    strategy: str = "smallest",
    prime_max: int | None = None,
) -> List[int]:
    """Repeated exact factor-certificate chain from n down to a prime terminal."""
    n = abs(int(n))
    if n < 2:
        return []
    strategy = strategy.strip().lower()
    if strategy not in {"smallest", "largest"}:
        raise ValueError("strategy must be 'smallest' or 'largest'")

    chain = [n]
    current = n
    while current >= 2 and not is_prime(current):
        allowed_primes = _allowed_factor_primes(current, prime_max)
        if not allowed_primes:
            break
        prime = allowed_primes[0] if strategy == "smallest" else allowed_primes[-1]
        current //= prime
        chain.append(current)
    return chain


def tau(n: int) -> int:
    """Number of positive divisors of |n|."""
    if n == 0:
        return 0
    total = 1
    for _prime, exponent in factor_integer(n):
        total *= exponent + 1
    return total


def sigma(n: int) -> int:
    """Sum of positive divisors of |n|."""
    if n == 0:
        return 0
    total = 1
    for prime, exponent in factor_integer(n):
        numerator = prime ** (exponent + 1) - 1
        denominator = prime - 1
        total *= numerator // denominator
    return total


def mobius(n: int) -> int:
    """Mobius mu(n) for integer n."""
    if abs(int(n)) == 1:
        return 1
    factors = factor_integer(n)
    if any(exponent > 1 for _prime, exponent in factors):
        return 0
    return -1 if len(factors) % 2 else 1


def totient(n: int) -> int:
    """Euler phi(|n|)."""
    n = abs(int(n))
    if n == 0:
        return 0
    if n == 1:
        return 1
    result = n
    for prime, _exponent in factor_integer(n):
        result = (result // prime) * (prime - 1)
    return result


# ---------------------------------------------------------------------------
# Canonical serialisation and hashing (substrate rules)
# ---------------------------------------------------------------------------

def canonical_json(obj: object) -> str:
    """Deterministic JSON: sorted keys, no whitespace, unicode preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_sha256(domain: str, payload: str) -> str:
    """Domain-separated SHA-256.

    hash = SHA-256(domain.encode('utf-8') + b'\\x00' + payload.encode('utf-8'))

    The null-byte separator prevents length-extension across domain boundaries.
    """
    h = hashlib.sha256()
    h.update(domain.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


HEX64_ZERO = "0" * 64  # manifest hash placeholder (never the string "placeholder")
