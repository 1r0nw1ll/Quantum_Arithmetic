"""
qa_lab.qa_core
==============
Canonical QA mathematical substrate for QA Lab.

Single import point for all QA arithmetic. Every agent, every cert validator,
every kernel operation imports from here — never from ad-hoc re-implementations.

Quick start
-----------
    from qa_lab.qa_core import qa_step, classify_state, orbit_contraction_factor
    from qa_lab.qa_core import precompute_all_families, is_reachable
    from qa_lab.qa_core import canonical_json, domain_sha256

Layer structure
---------------
  algebra.py  — pure math, stdlib only (qa_norm, qa_step, qa_tuple, v_p, hashes)
  orbits.py   — orbit classification + reachability + convergence metrics
"""

from .algebra import (
    # Constants
    INERT_PRIMES,
    HEX64_ZERO,
    # Core arithmetic (A1-compliant)
    qa_mod,
    qa_norm,
    qa_norm_mod,
    qa_step,
    qa_tuple,
    # Number theory
    big_omega,
    decomposition_depth_to_prime_terminal,
    factor_integer,
    factor_certificate_edges,
    factor_chain_to_prime,
    largest_prime_leq,
    is_composite,
    local_certificate_exact_radius,
    local_certificate_neighborhood_decision,
    local_certificate_prime_horizon,
    v_p,
    is_prime,
    is_obstructed,
    is_prime_power,
    is_semiprime,
    is_squarefree,
    largest_prime_factor,
    mobius,
    omega,
    sigma,
    smallest_prime_factor,
    tau,
    totient,
    # Canonical serialisation
    canonical_json,
    domain_sha256,
)

from .orbits import (
    # Orbit computation
    orbit,
    orbit_length,
    # Classification
    classify_state,
    precompute_all_families,
    # Reachability
    build_state_graph,
    obstructed_semiprime_residues,
    obstructed_prime_residues,
    nearest_semiprime_norm_targets,
    nearest_prime_norm_targets,
    prime_residues,
    reachable_states,
    reachable_subgraph,
    semiprime_residues,
    same_orbit,
    is_reachable,
    shortest_witness,
    state_successors,
    structural_obstruction,
    t_step,
    # Convergence metrics (Track C)
    kappa,
    orbit_contraction_factor,
    orbit_family_score,
)

__version__ = "1.0.0"

__all__ = [
    # algebra
    "INERT_PRIMES", "HEX64_ZERO",
    "qa_mod", "qa_norm", "qa_norm_mod", "qa_step", "qa_tuple",
    "big_omega", "decomposition_depth_to_prime_terminal", "factor_integer",
    "factor_certificate_edges", "factor_chain_to_prime", "largest_prime_leq",
    "is_composite", "local_certificate_exact_radius", "local_certificate_neighborhood_decision",
    "local_certificate_prime_horizon", "v_p", "is_prime",
    "is_obstructed", "is_prime_power", "is_semiprime", "is_squarefree",
    "largest_prime_factor", "mobius", "omega", "sigma",
    "smallest_prime_factor", "tau", "totient",
    "canonical_json", "domain_sha256",
    # orbits
    "orbit", "orbit_length",
    "classify_state", "precompute_all_families",
    "build_state_graph", "obstructed_semiprime_residues",
    "obstructed_prime_residues", "nearest_semiprime_norm_targets",
    "nearest_prime_norm_targets", "prime_residues", "reachable_states",
    "reachable_subgraph", "semiprime_residues", "same_orbit", "is_reachable",
    "shortest_witness", "state_successors", "structural_obstruction", "t_step",
    "kappa", "orbit_contraction_factor", "orbit_family_score",
]
