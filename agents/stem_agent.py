"""
qa_lab.agents.stem_agent
========================
StemAgent — the totipotent (undifferentiated) cell in the QA Lab Levin architecture.

## Levin Analogy

  Stem cell     = StemAgent starting at (0,0) = singularity orbit
  Progenitor    = StemAgent after first successful task (satellite orbit)
  Differentiated = StemAgent after competency commitment (cosmos orbit)

## Lifecycle

  1. UNDIFFERENTIATED — starts at singularity (0,0), handles TaskType.STEM only
     Can accept ANY task type in TRIAL mode (no commitment, orbit doesn't advance)
  2. PROGENITOR — first successful trial → record competency_hint, advance to satellite
     Handles original task type + STEM; orbit = satellite
  3. COMMITTED — after COMMIT threshold (default 3 successes) → orbit advances to cosmos
     capabilities locked, orbit_family → cosmos, full agent status

## Dedifferentiation

  Any committed agent can call `dedifferentiate()` to reset to singularity.
  This is the metamorphosis trigger: satellite cycling → dediff → respec → rediff.
  Used when:
    - Agent OFR < 0.05 for 5 cycles (singularity trap)
    - Kernel detects N consecutive satellite cycles > threshold
    - Operator calls TaskType.DEDIFFERENTIATE

## QA Orbit Semantics

  singularity (0,0) → totipotent: no specialization, infinite potential
  satellite   (2,3) → cycling progenitor: has hint, needs confirmation
  cosmos      (1,1) → differentiated: specialized, productive, directed
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_AGENTS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _AGENTS_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from agents.base import QAAgent
from protocols.differentiation import (
    apply_transition,
    check_partial_fail,
    SINGULARITY_SEED, SATELLITE_SEED, COSMOS_SEED,
    COMMIT_THRESHOLD, MAX_CONSECUTIVE_FAILURES,
)


# Orbit seeds for each lifecycle stage — A1-compliant {1..m}.
# Per 2026-04-05 A1 refactor, QA state space is {1..9} not {0..8}.
# Singularity under A1 is the (m,m) fixed point: qa_step(9,9,9) = (9,9).
_SINGULARITY_SEED = (9, 9)   # A1 fixed point; qa_step(9,9,9) = (9,9)
_SATELLITE_SEED   = (2, 3)   # mod-9 satellite orbit representative
_COSMOS_SEED      = (1, 1)   # mod-9 cosmos orbit representative

# After this many trial successes, commit to competency
DEFAULT_COMMIT_THRESHOLD = 3


class StemAgent(QAAgent):
    """Totipotent agent that differentiates into any competency.

    Stages:
      undifferentiated → progenitor → committed

    Handles all task types in TRIAL mode until committed to a specific competency.
    """

    capabilities = ["stem", "dedifferentiate"]  # always handles these
    cert_family = None  # no cert family until committed

    def __init__(
        self,
        name: str = "stem_agent",
        modulus: int = 9,
        commit_threshold: int = DEFAULT_COMMIT_THRESHOLD,
    ):
        # Start at singularity
        super().__init__(
            name=name,
            modulus=modulus,
            initial_b=_SINGULARITY_SEED[0],
            initial_e=_SINGULARITY_SEED[1],
        )
        self.commit_threshold = commit_threshold
        self._stage = "undifferentiated"    # undifferentiated | progenitor | committed
        self._trial_type: Optional[str] = None       # task type being trialed
        self._trial_successes: int = 0
        self._trial_failures: int = 0
        self._consecutive_failures: int = 0
        self._committed_type: Optional[str] = None   # locked competency
        self._differentiation_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Stage properties
    # ------------------------------------------------------------------

    @property
    def stage(self) -> str:
        return self._stage

    @property
    def is_undifferentiated(self) -> bool:
        return self._stage == "undifferentiated"

    @property
    def is_progenitor(self) -> bool:
        return self._stage == "progenitor"

    @property
    def is_committed(self) -> bool:
        return self._stage == "committed"

    # ------------------------------------------------------------------
    # can_handle override — accept anything in TRIAL mode
    # ------------------------------------------------------------------

    def can_handle(self, task: Any) -> bool:
        """Accept any task in undifferentiated/progenitor mode (trial).
        In committed mode, only accept the committed task type + stem/dediff.
        """
        task_type_val = self._task_type_str(task)
        if task_type_val is None:
            return False

        # Always handle stem / dedifferentiate
        if task_type_val in ("stem", "dedifferentiate"):
            return True

        # Committed: only handle committed type
        if self._stage == "committed":
            return task_type_val == self._committed_type

        # Undifferentiated / progenitor: accept everything (trial mode)
        return True

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        task_type_val = self._task_type_str(task)

        # Dedifferentiation command
        if task_type_val == "dedifferentiate":
            return self._handle_dedifferentiate(task)

        # Stem identity query
        if task_type_val == "stem":
            return self._handle_stem_query(task)

        # Trial handling
        return self._handle_trial(task, task_type_val)

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _handle_dedifferentiate(self, task: Any) -> Dict[str, Any]:
        """Reset to singularity (totipotent) state — validated via differentiation protocol."""
        old_stage = self._stage
        old_type = self._committed_type or self._trial_type

        ok, event, msg = apply_transition(
            agent_name=self.name,
            transition="DEDIFFERENTIATE",
            from_stage=self._stage,
            task_type=old_type,
            orbit_before=self.orbit_state,
            evidence={"reason_code": "OPERATOR_COMMAND", "is_operator_command": True},
        )

        if not ok:
            return {"ok": False, "verdict": "INCONCLUSIVE", "message": f"DEDIFFERENTIATE blocked: {msg}"}

        self._stage = "undifferentiated"
        self._trial_type = None
        self._trial_successes = 0
        self._trial_failures = 0
        self._consecutive_failures = 0
        self._committed_type = None
        self.capabilities = ["stem", "dedifferentiate"]
        self.cert_family = None
        self._b, self._e = SINGULARITY_SEED

        self._differentiation_log.append(event.to_dict())

        return {
            "ok": True,
            "verdict": "CONSISTENT",
            "stage": "undifferentiated",
            "orbit_state": list(self.orbit_state),
            "orbit_family": self.orbit_family,
            "message": f"Dedifferentiated from {old_stage}/{old_type} → singularity",
            "event": event.to_dict(),
        }

    def _handle_stem_query(self, task: Any) -> Dict[str, Any]:
        """Return stem cell status."""
        return {
            "ok": True,
            "verdict": "CONSISTENT",
            "stage": self._stage,
            "trial_type": self._trial_type,
            "committed_type": self._committed_type,
            "trial_successes": self._trial_successes,
            "trial_failures": self._trial_failures,
            "commit_threshold": self.commit_threshold,
            "orbit_state": list(self.orbit_state),
            "orbit_family": self.orbit_family,
            "capabilities": self.capabilities,
            "differentiation_log": self._differentiation_log,
        }

    def _handle_trial(self, task: Any, task_type_val: str) -> Dict[str, Any]:
        """Try to handle task — advance differentiation on success."""
        # If this is a new task type, start trialing it
        if self._trial_type is None:
            self._trial_type = task_type_val
            self._advance_to_progenitor()

        elif self._trial_type != task_type_val and self._stage == "progenitor":
            # Different task type: restart trial
            self._trial_type = task_type_val
            self._trial_successes = 0
            self._trial_failures = 0

        # Attempt delegation: use base stub
        result = self._trial_execute(task, task_type_val)

        if result.get("ok"):
            self._trial_successes += 1
            self._consecutive_failures = 0
            if (self._stage == "progenitor"
                    and self._trial_successes >= self.commit_threshold):
                self._commit(task_type_val)
        else:
            self._trial_failures += 1
            self._consecutive_failures += 1
            # Check PARTIAL_FAIL via protocol
            should_fail, reason = check_partial_fail(
                stage=self._stage,
                consecutive_failures=self._consecutive_failures,
                max_consecutive=MAX_CONSECUTIVE_FAILURES,
            )
            if should_fail:
                self._partial_fail(task_type_val, reason)

        result["stem_stage"] = self._stage
        result["trial_type"] = self._trial_type
        result["trial_successes"] = self._trial_successes
        return result

    def _trial_execute(self, task: Any, task_type_val: str) -> Dict[str, Any]:
        """Execute task in trial mode — returns stub result (not specialized).

        In a full system, this would delegate to a dynamically loaded agent.
        Here it returns INCONCLUSIVE so the kernel can route to a real agent
        or REPLICATE to spawn one.
        """
        inputs = getattr(task, "inputs", {}) or {}
        description = getattr(task, "description", "") or ""

        # If the task provides a 'trial_result' in inputs, use it (test hook)
        if "trial_result" in inputs:
            return dict(inputs["trial_result"])

        # Default: INCONCLUSIVE stub — signals kernel to find a real handler
        return {
            "ok": False,
            "verdict": "INCONCLUSIVE",
            "stub": True,
            "message": (
                f"StemAgent [{self._stage}] trialing {task_type_val!r}: "
                f"no specialized handler yet. Kernel should route or spawn."
            ),
            "task_type": task_type_val,
            "description": description,
        }

    # ------------------------------------------------------------------
    # Stage transitions
    # ------------------------------------------------------------------

    def _advance_to_progenitor(self) -> None:
        """Undifferentiated → Progenitor via FIRST_TRIAL protocol."""
        ok, event, msg = apply_transition(
            agent_name=self.name,
            transition="FIRST_TRIAL",
            from_stage=self._stage,
            task_type=self._trial_type,
            orbit_before=self.orbit_state,
            evidence={},
        )
        if not ok:
            return  # blocked — stay undifferentiated
        self._stage = "progenitor"
        self._b, self._e = SATELLITE_SEED
        self._differentiation_log.append(event.to_dict())

    def _commit(self, task_type_val: str) -> None:
        """Progenitor → Committed via COMMIT protocol."""
        ok, event, msg = apply_transition(
            agent_name=self.name,
            transition="COMMIT",
            from_stage=self._stage,
            task_type=task_type_val,
            orbit_before=self.orbit_state,
            evidence={
                "trial_type": self._trial_type,
                "successes": self._trial_successes,
                "orbit_family": self.orbit_family,
                "commit_threshold": self.commit_threshold,
            },
        )
        if not ok:
            return  # blocked — stay progenitor
        self._stage = "committed"
        self._committed_type = task_type_val
        self.capabilities = ["stem", "dedifferentiate", task_type_val]
        self.cert_family = f"QA_STEM_COMMITMENT_{task_type_val.upper()}.v1"
        self._b, self._e = COSMOS_SEED
        self._differentiation_log.append(event.to_dict())

    def _partial_fail(self, task_type_val: str, reason: str) -> None:
        """Progenitor → Stem via PARTIAL_FAIL protocol."""
        ok, event, msg = apply_transition(
            agent_name=self.name,
            transition="PARTIAL_FAIL",
            from_stage=self._stage,
            task_type=task_type_val,
            orbit_before=self.orbit_state,
            evidence={
                "consecutive_failures": self._consecutive_failures,
                "max_consecutive": MAX_CONSECUTIVE_FAILURES,
                "reason": reason,
            },
        )
        if not ok:
            return
        self._stage = "undifferentiated"
        self._trial_type = None
        self._trial_successes = 0
        self._trial_failures = 0
        self._consecutive_failures = 0
        self._committed_type = None
        self.capabilities = ["stem", "dedifferentiate"]
        self.cert_family = None
        self._b, self._e = SINGULARITY_SEED
        self._differentiation_log.append(event.to_dict())

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _task_type_str(task: Any) -> Optional[str]:
        task_type = getattr(task, "task_type", None)
        if task_type is None:
            return None
        return task_type.value if hasattr(task_type, "value") else str(task_type)

    def status(self) -> Dict[str, Any]:
        s = super().status()
        s.update({
            "stage": self._stage,
            "trial_type": self._trial_type,
            "committed_type": self._committed_type,
            "trial_successes": self._trial_successes,
            "trial_failures": self._trial_failures,
            "commit_threshold": self.commit_threshold,
            "differentiation_log": self._differentiation_log,
        })
        return s

    def __repr__(self) -> str:
        return (
            f"<StemAgent name={self.name!r} stage={self._stage} "
            f"trial={self._trial_type!r} orbit={self.orbit_state} family={self.orbit_family}>"
        )
