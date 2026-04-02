"""QA Observer Core — shared topographic observer primitives.

Provides qa_mod() and compute_qci() used across all 6 empirical domains
(finance, EEG, audio, seismology, climate, ERA5 reanalysis).
"""

QA_COMPLIANCE = "observer=core_library, state_alphabet=generic_topographic"

from .core import qa_mod, compute_qci, classify_orbit

__all__ = ["qa_mod", "compute_qci", "classify_orbit"]
