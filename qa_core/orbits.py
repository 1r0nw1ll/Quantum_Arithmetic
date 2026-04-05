"""
qa_lab.qa_core.orbits
=====================
Orbit classification, reachability, and convergence metrics.

The orbit structure is the core reasoning substrate for QA Lab agents:
  - cosmos      (length 24 for mod-9 and mod-24): productive, full state space access
  - satellite   (length 8 for mod-9 and mod-24):  looping, limited reachability
  - singularity (length 1):            fixed point — degenerate state

Convention: A1-compliant {1,...,m} with qa_step=(e, qa_mod(b+e, m)).
Singularity at (m,m); satellite period 8; cosmos period 24. Matches
qa_arithmetic/qa_observer canonical packages.

An agent in 'singularity' orbit has converged (or is stuck).
An agent in 'satellite' orbit is cycling — needs perturbation.
An agent in 'cosmos' orbit has maximum reachability — full exploration mode.

This file is intentionally numpy-free so it can be imported anywhere.
"""

from __future__ import annotations

import functools
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple

from .algebra import (
    INERT_PRIMES,
    is_prime,
    is_prime_power,
    is_semiprime,
    qa_mod,
    qa_norm_mod,
    qa_step,
    v_p,
)


# ---------------------------------------------------------------------------
# Orbit computation
# ---------------------------------------------------------------------------

def orbit(b: int, e: int, m: int) -> List[Tuple[int, int]]:
    """Return the ordered orbit of (b, e) under Q mod m.

    The orbit is the cycle: (b,e) → Q(b,e) → Q²(b,e) → ... → (b,e).
    """
    states: List[Tuple[int, int]] = []
    cur = (qa_mod(b, m), qa_mod(e, m))
    seen: Dict[Tuple[int, int], int] = {}
    while cur not in seen:
        seen[cur] = len(states)
        states.append(cur)
        cur = qa_step(cur[0], cur[1], m)
    # If the cycle doesn't start at the first element, trim the tail
    cycle_start = seen[cur]
    return states[cycle_start:]


def orbit_length(b: int, e: int, m: int) -> int:
    """Length of the orbit containing (b, e) under Q mod m."""
    return len(orbit(b, e, m))


# ---------------------------------------------------------------------------
# Orbit family classification
# ---------------------------------------------------------------------------

def _max_orbit_length(m: int) -> int:
    """Largest orbit length in ({1..m})² under Q (A1-compliant)."""
    seen: Dict[Tuple[int, int], bool] = {}
    max_len = 1
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            if (b, e) in seen:
                continue
            o = orbit(b, e, m)
            for s in o:
                seen[s] = True
            if len(o) > max_len:
                max_len = len(o)
    return max_len


@functools.lru_cache(maxsize=16)
def _cached_max_orbit_length(m: int) -> int:
    return _max_orbit_length(m)


def classify_state(b: int, e: int, m: int) -> str:
    """Classify (b, e) mod m into orbit family.

    Returns one of: 'cosmos' | 'satellite' | 'singularity'

    Classification is by orbit length:
      singularity — length 1  (fixed point)
      cosmos      — maximum orbit length for this modulus
      satellite   — any other length

    For m=9:  cosmos=24, satellite=8, singularity=1
    For m=24: cosmos=24, satellite=8, singularity=1
    """
    length = orbit_length(b, e, m)
    if length == 1:
        return "singularity"
    if length == _cached_max_orbit_length(m):
        return "cosmos"
    return "satellite"


@functools.lru_cache(maxsize=16)
def precompute_all_families(m: int) -> Dict[Tuple[int, int], str]:
    """Return a dict mapping every (b, e) in {1..m}² to its orbit family.

    Result is cached — call once per modulus, reuse everywhere.
    """
    families: Dict[Tuple[int, int], str] = {}
    visited: Dict[Tuple[int, int], str] = {}
    max_len = _cached_max_orbit_length(m)

    for b in range(1, m + 1):
        for e in range(1, m + 1):
            if (b, e) in visited:
                families[(b, e)] = visited[(b, e)]
                continue
            o = orbit(b, e, m)
            length = len(o)
            if length == 1:
                family = "singularity"
            elif length == max_len:
                family = "cosmos"
            else:
                family = "satellite"
            for s in o:
                visited[s] = family
            families[(b, e)] = family

    return families


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------

def same_orbit(b1: int, e1: int, b2: int, e2: int, m: int) -> bool:
    """Return True if (b1,e1) and (b2,e2) are in the same orbit under Q mod m."""
    o = orbit(b1, e1, m)
    return (qa_mod(b2, m), qa_mod(e2, m)) in set(o)


def is_reachable(sb: int, se: int, tb: int, te: int, m: int) -> bool:
    """Return True if target (tb, te) is reachable from source (sb, se) under Q mod m.

    Reachability is orbit membership: states in the same orbit can reach each other
    (Q is a bijection on each orbit). States in different orbits are structurally
    unreachable — this is the failure algebra's geometric obstruction.
    """
    return same_orbit(sb, se, tb, te, m)


def structural_obstruction(target_r: int, m: int) -> bool:
    """Return True if target norm r is structurally unreachable in Z[φ]/mZ[φ].

    A norm r is unreachable if v_p(r) == 1 for any prime p inert in Z[φ].
    This is independent of the source state — it's a property of the target.
    """
    inert = INERT_PRIMES.get(m, [])
    return any(v_p(target_r, p) == 1 for p in inert)


def _normalize_generators(generators: Sequence[str]) -> Tuple[str, ...]:
    normalized = tuple(str(gen).strip().upper() for gen in generators if str(gen).strip())
    if not normalized:
        raise ValueError("At least one generator must be provided.")
    allowed = {"Q", "T"}
    unknown = sorted(set(normalized).difference(allowed))
    if unknown:
        raise ValueError(f"Unknown generators: {unknown}. Allowed generators: ['Q', 'T']")
    return normalized


def t_step(b: int, e: int, m: int) -> Tuple[int, int]:
    """One application of T = Q^2: (b, e) -> (d, a). A1-compliant."""
    d = qa_mod(b + e, m)
    a = qa_mod(b + 2 * e, m)
    return d, a


def state_successors(
    b: int,
    e: int,
    m: int,
    generators: Sequence[str] = ("Q",),
) -> List[Tuple[str, Tuple[int, int]]]:
    """Return deterministic successor states for the chosen generator set."""
    normalized = _normalize_generators(generators)
    successors: List[Tuple[str, Tuple[int, int]]] = []
    if "Q" in normalized:
        successors.append(("Q", qa_step(b, e, m)))
    if "T" in normalized:
        successors.append(("T", t_step(b, e, m)))
    return successors


def build_state_graph(
    m: int,
    generators: Sequence[str] = ("Q",),
) -> Dict[Tuple[int, int], List[Tuple[str, Tuple[int, int]]]]:
    """Build the directed QA state graph for the chosen generators."""
    _normalize_generators(generators)
    graph: Dict[Tuple[int, int], List[Tuple[str, Tuple[int, int]]]] = {}
    for b in range(1, m + 1):
        for e in range(1, m + 1):
            graph[(b, e)] = state_successors(b, e, m, generators=generators)
    return graph


def shortest_witness(
    sb: int,
    se: int,
    tb: int,
    te: int,
    m: int,
    generators: Sequence[str] = ("Q",),
) -> Optional[Dict[str, object]]:
    """Return a shortest-path witness from source to target, or None if unreachable."""
    normalized = _normalize_generators(generators)
    source = (qa_mod(sb, m), qa_mod(se, m))
    target = (qa_mod(tb, m), qa_mod(te, m))
    queue: Deque[Tuple[Tuple[int, int], List[Tuple[int, int]], List[str]]] = deque()
    queue.append((source, [source], []))
    visited = {source}

    while queue:
        state, witness_states, generator_trace = queue.popleft()
        if state == target:
            return {
                "source": source,
                "target": target,
                "reachable": True,
                "steps": len(generator_trace),
                "generator_trace": generator_trace,
                "witness_states": witness_states,
                "generator_set": list(normalized),
            }

        for generator_id, next_state in state_successors(
            state[0], state[1], m, generators=normalized
        ):
            if next_state in visited:
                continue
            visited.add(next_state)
            queue.append(
                (
                    next_state,
                    witness_states + [next_state],
                    generator_trace + [generator_id],
                )
            )

    return None


def reachable_states(
    sb: int,
    se: int,
    m: int,
    generators: Sequence[str] = ("Q",),
) -> List[Tuple[int, int]]:
    """Return all states reachable from the given source under the generator set."""
    normalized = _normalize_generators(generators)
    source = (qa_mod(sb, m), qa_mod(se, m))
    queue: Deque[Tuple[int, int]] = deque([source])
    visited = {source}

    while queue:
        state = queue.popleft()
        for _generator_id, next_state in state_successors(
            state[0], state[1], m, generators=normalized
        ):
            if next_state in visited:
                continue
            visited.add(next_state)
            queue.append(next_state)

    return sorted(visited)


def reachable_subgraph(
    sb: int,
    se: int,
    m: int,
    generators: Sequence[str] = ("Q",),
) -> Dict[str, object]:
    """Return a JSON-safe reachable subgraph rooted at the source state."""
    normalized = _normalize_generators(generators)
    states = reachable_states(sb, se, m, generators=normalized)
    reachable = set(states)
    edges: List[Dict[str, object]] = []

    for state in states:
        for generator_id, next_state in state_successors(
            state[0], state[1], m, generators=normalized
        ):
            if next_state not in reachable:
                continue
            edges.append(
                {
                    "source": [state[0], state[1]],
                    "generator": generator_id,
                    "target": [next_state[0], next_state[1]],
                }
            )

    nodes = []
    for b, e in states:
        norm_value = qa_norm_mod(b, e, m)
        nodes.append(
            {
                "state": [b, e],
                "orbit_family": classify_state(b, e, m),
                "norm_mod": norm_value,
                "norm_is_prime": is_prime(norm_value),
                "norm_is_semiprime": is_semiprime(norm_value),
                "norm_is_prime_power": is_prime_power(norm_value),
                "norm_is_obstructed": structural_obstruction(norm_value, m),
            }
        )

    return {
        "source": [qa_mod(sb, m), qa_mod(se, m)],
        "modulus": m,
        "generator_set": list(normalized),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def prime_residues(m: int) -> List[int]:
    """Prime residue classes in {0, ..., m-1} represented by positive primes < m."""
    return [value for value in range(2, m) if is_prime(value)]


def obstructed_prime_residues(m: int) -> List[int]:
    """Prime residues excluded by the inert-prime obstruction rule."""
    return [value for value in prime_residues(m) if structural_obstruction(value, m)]


def semiprime_residues(m: int) -> List[int]:
    """Semiprime residue classes in {0, ..., m-1} represented by positive semiprimes < m."""
    return [value for value in range(2, m) if is_semiprime(value)]


def obstructed_semiprime_residues(m: int) -> List[int]:
    """Semiprime residues excluded by the inert-prime obstruction rule."""
    return [value for value in semiprime_residues(m) if structural_obstruction(value, m)]


def _nearest_norm_targets(
    sb: int,
    se: int,
    m: int,
    generators: Sequence[str],
    limit: int,
    candidate_residues: Iterable[int],
    label_key: str,
) -> List[Dict[str, object]]:
    normalized = _normalize_generators(generators)
    if limit <= 0:
        return []

    source = (qa_mod(sb, m), qa_mod(se, m))
    queue: Deque[Tuple[Tuple[int, int], List[Tuple[int, int]], List[str]]] = deque()
    queue.append((source, [source], []))
    visited = {source}
    candidate_set = set(candidate_residues)
    found_residues = set()
    results: List[Dict[str, object]] = []

    while queue and len(results) < limit and found_residues != candidate_set:
        state, witness_states, generator_trace = queue.popleft()
        norm_value = qa_norm_mod(state[0], state[1], m)
        if norm_value in candidate_set and norm_value not in found_residues:
            found_residues.add(norm_value)
            results.append(
                {
                    label_key: norm_value,
                    "target": state,
                    "steps": len(generator_trace),
                    "generator_trace": generator_trace,
                    "witness_states": witness_states,
                }
            )

        for generator_id, next_state in state_successors(
            state[0], state[1], m, generators=normalized
        ):
            if next_state in visited:
                continue
            visited.add(next_state)
            queue.append(
                (
                    next_state,
                    witness_states + [next_state],
                    generator_trace + [generator_id],
                )
            )

    return results


def nearest_prime_norm_targets(
    sb: int,
    se: int,
    m: int,
    generators: Sequence[str] = ("Q",),
    limit: int = 5,
) -> List[Dict[str, object]]:
    """Return shortest witnesses to the nearest distinct prime QA norm residues."""
    return _nearest_norm_targets(
        sb,
        se,
        m,
        generators=generators,
        limit=limit,
        candidate_residues=set(prime_residues(m)).difference(obstructed_prime_residues(m)),
        label_key="prime",
    )


def nearest_semiprime_norm_targets(
    sb: int,
    se: int,
    m: int,
    generators: Sequence[str] = ("Q",),
    limit: int = 5,
) -> List[Dict[str, object]]:
    """Return shortest witnesses to the nearest distinct semiprime QA norm residues."""
    return _nearest_norm_targets(
        sb,
        se,
        m,
        generators=generators,
        limit=limit,
        candidate_residues=set(semiprime_residues(m)).difference(obstructed_semiprime_residues(m)),
        label_key="semiprime",
    )


# ---------------------------------------------------------------------------
# Convergence metrics (Track C — Finite-Orbit Descent)
# ---------------------------------------------------------------------------

def kappa(b: int, e: int, m: int, lr: float) -> float:
    """Curvature metric κ for state (b, e) at learning rate lr.

    κ = 1 − (1 − lr * H_QA)²  ≈ 2·lr·H_QA for small lr·H_QA

    where H_QA is the QA Harmonic Index proxy:
      H_QA = |f(b,e)| / m   (normalised norm magnitude)

    κ ∈ [0, 1]: κ close to 1 → fast convergence; κ close to 0 → slow/stalled.
    """
    h = abs(qa_norm_mod(b, e, m)) / m
    kappa_val = 1.0 - (1.0 - lr * h) * (1.0 - lr * h)
    return float(kappa_val)


def orbit_contraction_factor(b_start: int, e_start: int, m: int, lr: float) -> float:
    """ρ(O) = ∏(1−κ_t)²  over one full orbit.

    From the Finite-Orbit Descent Theorem (Unified Curvature paper):
      L_{t+L} = ρ(O) · L_t   (exact for scalar quadratic loss)

    ρ(O) < 1  iff  κ_min > 0  iff  convergence is guaranteed.
    ρ(O) close to 0 → very fast convergence.
    """
    o = orbit(b_start, e_start, m)
    rho = 1.0
    for (b, e) in o:
        k = kappa(b, e, m, lr)
        factor = (1.0 - k) * (1.0 - k)
        rho *= factor
    return rho


def orbit_family_score(family: str) -> float:
    """Scalar score for orbit family: higher = more capable agent state.

    cosmos      → 1.0  (full reachability, maximum exploration)
    satellite   → 0.5  (partial reachability, looping)
    singularity → 0.0  (fixed point, no movement)
    """
    return {"cosmos": 1.0, "satellite": 0.5, "singularity": 0.0}.get(family, 0.0)
