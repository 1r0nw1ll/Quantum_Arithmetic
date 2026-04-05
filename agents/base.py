"""
qa_lab.agents.base
==================
QAAgent — base class for all QA Lab micro-agents.

Every agent in QA Lab:
  1. Has a QA orbit state (b, e) — its position in Z[φ]/mZ[φ]
  2. Declares capabilities — list of TaskTypes it can handle
  3. Implements handle(task) → dict — produces a certified output
  4. Can certify any result as a [122] QA_EMPIRICAL_OBSERVATION_CERT artifact
  5. Steps its own orbit after each handled task (orbit-tracked cognition)

Agent spawn protocol
--------------------
When the kernel's REPLICATE step fires, it produces a QA_AGENT_SPAWN_SPEC.v1.
That spec drives Codex to:
  1. Create a new cert family under qa_alphageometry_ptolemy/
  2. Implement the validator (with --self-test)
  3. Add fixtures (pass + fail)
  4. Register a new QAAgent subclass
  5. Onboard into meta-validator FAMILY_SWEEPS

This means a new QA Lab capability = a new cert family = a new agent.
The cert ecosystem IS the agent spawning protocol.

Composition protocol
--------------------
Two agents compose into a macro-agent by cert inheritance:
  MacroAgent.parent_certs = [AgentA.cert_family, AgentB.cert_family]
  MacroAgent inherits Gate policies from both parents (QA_INHERITANCE_COMPAT_CERT [109])

This is already machine-checkable via the existing cert ecosystem.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod

QA_COMPLIANCE = "qa_lab_agent — orbit state tracks agent position; orbit_family is a class property, not a canonical orbit call"
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_AGENTS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _AGENTS_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from qa_core import (
    qa_step, classify_state, orbit_family_score,
    kappa, orbit_contraction_factor,
    canonical_json, domain_sha256,
)


class QAAgent(ABC):
    """Abstract base for all QA Lab micro-agents.

    Subclasses must implement:
      - capabilities: list of TaskType strings this agent handles
      - handle(task) → dict: execute the task, return {ok, ...}

    The base class provides:
      - Orbit state tracking (b, e) — advances one Q-step after each handle()
      - certify(result) → [122] cert artifact
      - can_handle(task) check
    """

    # Subclasses declare which task types they handle
    capabilities: List[str] = []

    # Subclass declares its cert family name (for spawn protocol)
    cert_family: Optional[str] = None

    def __init__(
        self,
        name: str,
        modulus: int = 9,
        initial_b: int = 1,
        initial_e: int = 1,
    ):
        self.name = name
        self.modulus = modulus
        # A1-compliant reduction: map any input int to {1..m}.  Bare `% m`
        # would map m → 0, which is outside the A1 state space and breaks
        # downstream _families lookups (same class of bug as kernel K-002).
        self._b = ((int(initial_b) - 1) % modulus) + 1
        self._e = ((int(initial_e) - 1) % modulus) + 1
        self._handled_count = 0

    # ------------------------------------------------------------------
    # Orbit state
    # ------------------------------------------------------------------

    @property
    def orbit_state(self) -> Tuple[int, int]:
        return (self._b, self._e)

    @property
    def orbit_family(self) -> str:
        return classify_state(self._b, self._e, self.modulus)

    @property
    def orbit_score(self) -> float:
        return orbit_family_score(self.orbit_family)

    @property
    def convergence_rate(self) -> float:
        """κ — curvature metric for current orbit state (proxy for task throughput)."""
        return kappa(self._b, self._e, self.modulus, lr=0.1)

    def _advance_orbit(self) -> None:
        """Advance agent's orbit state one Q-step after handling a task."""
        self._b, self._e = qa_step(self._b, self._e, self.modulus)

    # ------------------------------------------------------------------
    # Capability check
    # ------------------------------------------------------------------

    def can_handle(self, task: Any) -> bool:
        """Return True if this agent's capabilities include the task type."""
        task_type = getattr(task, "task_type", None)
        if task_type is None:
            return False
        task_type_val = task_type.value if hasattr(task_type, "value") else str(task_type)
        return task_type_val in self.capabilities

    # ------------------------------------------------------------------
    # Handle (abstract)
    # ------------------------------------------------------------------

    @abstractmethod
    def handle(self, task: Any) -> Dict[str, Any]:
        """Execute the task. Return dict with at minimum {"ok": bool}.

        The returned dict becomes the ACT output in the kernel cycle.
        For CERTIFY tasks: include {"validator_path": str} for VERIFY step.
        """

    def safe_handle(self, task: Any) -> Dict[str, Any]:
        """Wrap handle() with orbit advancement and error catching."""
        try:
            result = self.handle(task)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        finally:
            self._advance_orbit()
            self._handled_count += 1
        return result

    # ------------------------------------------------------------------
    # Certify
    # ------------------------------------------------------------------

    def certify(
        self,
        observation_body: str,
        verdict: str,
        evidence: List[Dict[str, Any]],
        parent_cert_name: str = "QA_CORE_SPEC.v1",
        observation_source: str = "experiment_script",
        fail_ledger: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Produce a [122] QA_EMPIRICAL_OBSERVATION_CERT.v1 artifact.

        This is the standard output format for any empirical result.
        verdict must be one of: CONSISTENT, CONTRADICTS, PARTIAL, INCONCLUSIVE
        """
        if verdict not in {"CONSISTENT", "CONTRADICTS", "PARTIAL", "INCONCLUSIVE"}:
            raise ValueError(f"Invalid verdict: {verdict}")
        if verdict == "CONTRADICTS" and not fail_ledger:
            raise ValueError("CONTRADICTS verdict requires a non-empty fail_ledger")

        cert = {
            "schema_version": "QA_EMPIRICAL_OBSERVATION_CERT.v1",
            "observation": {
                "source": observation_source,
                "body": observation_body,
                "agent": self.name,
                "agent_orbit_state": list(self.orbit_state),
                "agent_orbit_family": self.orbit_family,
            },
            "parent_cert": {
                "schema_version": parent_cert_name,
            },
            "verdict": verdict,
            "evidence": evidence,
            "fail_ledger": fail_ledger or [],
            "result": "PASS",
        }

        # Compute cert hash
        payload = canonical_json(cert)
        cert["cert_hash"] = domain_sha256("QA_EMPIRICAL_OBSERVATION_CERT.v1", payload)

        return cert

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cert_family": self.cert_family,
            "capabilities": self.capabilities,
            "orbit_state": self.orbit_state,
            "orbit_family": self.orbit_family,
            "orbit_score": self.orbit_score,
            "handled_count": self._handled_count,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} orbit={self.orbit_state} family={self.orbit_family}>"
