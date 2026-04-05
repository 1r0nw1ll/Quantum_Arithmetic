#!/usr/bin/env python3

from qa_core import (
    nearest_semiprime_norm_targets,
    obstructed_semiprime_residues,
    nearest_prime_norm_targets,
    obstructed_prime_residues,
    prime_residues,
    semiprime_residues,
    shortest_witness,
)


def test_shortest_witness_under_q_returns_explicit_trace() -> None:
    witness = shortest_witness(1, 1, 3, 5, 24, generators=("Q",))
    assert witness is not None
    assert witness["steps"] == 3
    assert witness["generator_trace"] == ["Q", "Q", "Q"]
    assert witness["witness_states"] == [(1, 1), (1, 2), (2, 3), (3, 5)]


def test_generator_set_changes_reachability() -> None:
    unreachable = shortest_witness(1, 1, 1, 2, 24, generators=("T",))
    assert unreachable is None

    reachable = shortest_witness(1, 1, 1, 2, 24, generators=("Q", "T"))
    assert reachable is not None
    assert reachable["steps"] == 1
    assert reachable["generator_trace"] == ["Q"]


def test_prime_norm_search_reports_nearest_prime_targets() -> None:
    candidates = nearest_prime_norm_targets(1, 1, 24, generators=("Q",), limit=3)
    assert candidates
    assert candidates[0]["prime"] == 23
    assert candidates[0]["target"] == (1, 2)
    assert candidates[0]["steps"] == 1

    assert prime_residues(24) == [2, 3, 5, 7, 11, 13, 17, 19, 23]
    assert obstructed_prime_residues(24) == [3, 7]


def test_semiprime_norm_search_reports_semiprime_targets() -> None:
    candidates = nearest_semiprime_norm_targets(2, 2, 24, generators=("Q", "T"), limit=3)
    assert candidates
    assert candidates[0]["semiprime"] == 4
    assert candidates[0]["target"] == (2, 2)
    assert candidates[0]["steps"] == 0

    assert semiprime_residues(24) == [4, 6, 9, 10, 14, 15, 21, 22]
    assert obstructed_semiprime_residues(24) == [6, 14, 15, 21]
