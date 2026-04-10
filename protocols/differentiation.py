"""
qa_lab.protocols.differentiation
==================================
Formal differentiation / redifferentiation protocol for QA Lab agents.

This module is the machine-checkable spec for how agents move through
developmental stages in the Levin morphogenetic architecture.

## Stage Graph

    singularity ──[first_trial]──▶ satellite ──[commit]──▶ cosmos
         ▲                             │                      │
         │                             │                      │
         └──────[dediff]───────────────┴──────[dediff]────────┘

Four one-way transitions + two reversal paths:

  FIRST_TRIAL     stem (singularity) → progenitor (satellite)
  COMMIT          progenitor (satellite) → committed (cosmos)
  PARTIAL_FAIL    progenitor → back to stem (too many failures during trial)
  DEDIFFERENTIATE committed → stem (structural failure or operator command)

## Transition Rules

### FIRST_TRIAL  (stem → progenitor)
Trigger:   agent receives any non-stem task
Evidence:  task_type is valid + agent is in undifferentiated stage
Orbit:     reset to satellite seed (2,3)
Reversible: yes (PARTIAL_FAIL or DEDIFFERENTIATE)

### COMMIT  (progenitor → committed)
Trigger:   trial_successes >= commit_threshold (default 3)
Evidence:
  - All N successes must be for the SAME task_type
  - No more than max_trial_failures consecutive failures (default 5)
  - Agent orbit must not be in singularity at commit time
Orbit:     advance to cosmos seed (1,1)
Reversible: yes (DEDIFFERENTIATE)

### PARTIAL_FAIL  (progenitor → stem, auto)
Trigger:   consecutive_failures >= max_consecutive_failures (default 5) during trial
Evidence:  failure log shows N consecutive failed tasks for same type
Orbit:     reset to singularity (0,0)
Reversible: yes (new FIRST_TRIAL)

### DEDIFFERENTIATE  (committed → stem, operator/kernel)
Trigger (any of):
  A. success_rate < min_success_rate (default 0.4) over min_eval_window (default 10 tasks)
  B. orbit_drift_count > max_drift_count (default 3) consecutive satellite cycles
  C. kernel metamorphosis fires (N consecutive satellite kernel cycles)
  D. explicit operator command (TaskType.DEDIFFERENTIATE)
Evidence:  performance record + reason code
Orbit:     reset to singularity (0,0)
Reversible: yes (new FIRST_TRIAL)

## Organ Membership  (committed → organ)
A committed agent can join an organ if:
  - Its orbit_signature == cosmos (differentiated cell)
  - The organ has at least one spine agent (cosmos, guaranteed convergence)
  - The agent's competency cert ([123]) passes V8 CELL_ORBIT_MISMATCH check
  - The organ's combined failure_modes don't include the agent's failure mode as a blocker

## Constants (defaults — all overridable per-agent)

  COMMIT_THRESHOLD          = 3    # successes needed to commit
  MAX_TRIAL_FAILURES        = 5    # consecutive failures → PARTIAL_FAIL
  MIN_SUCCESS_RATE          = 0.4  # committed agent min rate → DEDIFFERENTIATE
  MIN_EVAL_WINDOW           = 10   # tasks before rate-based dediff triggers
  MAX_DRIFT_COUNT           = 3    # consecutive satellite cycles → DEDIFFERENTIATE
  MAX_CONSECUTIVE_FAILURES  = 5    # trial failures before PARTIAL_FAIL

## Transition Record Schema  (QA_DIFFERENTIATION_EVENT.v1)

  {
    "schema":         "QA_DIFFERENTIATION_EVENT.v1",
    "agent_name":     str,
    "transition":     "FIRST_TRIAL" | "COMMIT" | "PARTIAL_FAIL" | "DEDIFFERENTIATE",
    "from_stage":     "undifferentiated" | "progenitor" | "committed",
    "to_stage":       "undifferentiated" | "progenitor" | "committed",
    "task_type":      str | None,
    "evidence":       dict,          # counts, rates, reason_code
    "orbit_before":   [b, e],
    "orbit_after":    [b, e],
    "timestamp":      ISO8601 str,
  }
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

QA_COMPLIANCE = "qa_lab_protocol — stage transition rules; orbit labels are protocol spec values, not empirical state variables"

# ---------------------------------------------------------------------------
# Default thresholds (all overridable per-agent instance)
# ---------------------------------------------------------------------------

COMMIT_THRESHOLD         = 3
MAX_TRIAL_FAILURES       = 5
MIN_SUCCESS_RATE         = 0.4
MIN_EVAL_WINDOW          = 10
MAX_DRIFT_COUNT          = 3
MAX_CONSECUTIVE_FAILURES = 5

# QA orbit seeds per stage
SINGULARITY_SEED = (0, 0)
SATELLITE_SEED   = (2, 3)
COSMOS_SEED      = (1, 1)

# Valid transitions
VALID_TRANSITIONS = frozenset([
    "FIRST_TRIAL",      # stem → progenitor
    "COMMIT",           # progenitor → committed
    "PARTIAL_FAIL",     # progenitor → stem
    "DEDIFFERENTIATE",  # committed → stem
])

# Valid reasons for DEDIFFERENTIATE
DEDIFF_REASONS = frozenset([
    "LOW_SUCCESS_RATE",       # rule A
    "ORBIT_DRIFT",            # rule B
    "METAMORPHOSIS",          # rule C
    "OPERATOR_COMMAND",       # rule D
])


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------

@dataclass
class DifferentiationEvent:
    """A single stage transition for a QA Lab agent."""
    agent_name:    str
    transition:    str
    from_stage:    str
    to_stage:      str
    task_type:     Optional[str]
    evidence:      Dict[str, Any]
    orbit_before:  Tuple[int, int]
    orbit_after:   Tuple[int, int]
    timestamp:     str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )
    schema: str = "QA_DIFFERENTIATION_EVENT.v1"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["orbit_before"] = list(data["orbit_before"])
        data["orbit_after"]  = list(data["orbit_after"])
        return data


# ---------------------------------------------------------------------------
# Transition validators
# ---------------------------------------------------------------------------

def check_first_trial(
    stage: str,
    task_type: Optional[str],
) -> Tuple[bool, str]:
    """Check if FIRST_TRIAL transition is valid.

    Returns (ok, reason).
    """
    if stage != "undifferentiated":
        return False, f"FIRST_TRIAL requires undifferentiated stage, got {stage!r}"
    if not task_type:
        return False, "FIRST_TRIAL requires a non-empty task_type"
    if task_type in ("stem", "dedifferentiate"):
        return False, f"FIRST_TRIAL cannot trial meta-task {task_type!r}"
    return True, "ok"


def check_commit(
    stage: str,
    task_type: Optional[str],
    trial_type: Optional[str],
    successes: int,
    orbit_family: str,
    commit_threshold: int = COMMIT_THRESHOLD,
) -> Tuple[bool, str]:
    """Check if COMMIT transition is valid.

    Returns (ok, reason).
    """
    if stage != "progenitor":
        return False, f"COMMIT requires progenitor stage, got {stage!r}"
    if task_type != trial_type:
        return False, f"COMMIT requires task_type {trial_type!r} == trial_type, got {task_type!r}"
    if successes < commit_threshold:
        return False, f"COMMIT requires {commit_threshold} successes, got {successes}"
    if orbit_family == "singularity":
        return False, "COMMIT blocked: agent in singularity orbit at commit time"
    return True, "ok"


def check_partial_fail(
    stage: str,
    consecutive_failures: int,
    max_consecutive: int = MAX_CONSECUTIVE_FAILURES,
) -> Tuple[bool, str]:
    """Check if PARTIAL_FAIL auto-reversal should trigger.

    Returns (should_trigger, reason).
    """
    if stage != "progenitor":
        return False, f"PARTIAL_FAIL only applies to progenitor stage, got {stage!r}"
    if consecutive_failures < max_consecutive:
        return False, f"only {consecutive_failures}/{max_consecutive} consecutive failures — not yet"
    return True, f"PARTIAL_FAIL: {consecutive_failures} consecutive failures >= {max_consecutive}"


def check_dedifferentiate(
    stage: str,
    reason_code: str,
    success_rate: float = 1.0,
    total_tasks: int = 0,
    orbit_drift_count: int = 0,
    is_operator_command: bool = False,
    is_metamorphosis: bool = False,
    min_success_rate: float = MIN_SUCCESS_RATE,
    min_eval_window: int = MIN_EVAL_WINDOW,
    max_drift_count: int = MAX_DRIFT_COUNT,
) -> Tuple[bool, str]:
    """Check if DEDIFFERENTIATE transition is valid.

    Returns (ok, reason).
    """
    if stage not in ("committed", "progenitor"):
        return False, f"DEDIFFERENTIATE requires committed or progenitor stage, got {stage!r}"
    if reason_code not in DEDIFF_REASONS:
        return False, f"unknown reason_code {reason_code!r}, must be one of {sorted(DEDIFF_REASONS)}"

    if reason_code == "LOW_SUCCESS_RATE":
        if total_tasks < min_eval_window:
            return False, f"LOW_SUCCESS_RATE requires {min_eval_window} tasks, only {total_tasks}"
        if success_rate >= min_success_rate:
            return False, f"success_rate {success_rate:.2f} >= {min_success_rate} — no dediff needed"
        return True, f"LOW_SUCCESS_RATE: rate={success_rate:.2f} < {min_success_rate} over {total_tasks} tasks"

    if reason_code == "ORBIT_DRIFT":
        if orbit_drift_count <= max_drift_count:
            return False, f"drift {orbit_drift_count} <= {max_drift_count} — threshold not met"
        return True, f"ORBIT_DRIFT: {orbit_drift_count} consecutive satellite cycles > {max_drift_count}"

    if reason_code == "METAMORPHOSIS":
        if not is_metamorphosis:
            return False, "METAMORPHOSIS reason requires is_metamorphosis=True"
        return True, "METAMORPHOSIS: kernel-level satellite loop triggered redifferentiation"

    if reason_code == "OPERATOR_COMMAND":
        if not is_operator_command:
            return False, "OPERATOR_COMMAND reason requires is_operator_command=True"
        return True, "OPERATOR_COMMAND: explicit operator dedifferentiation"

    return False, f"unhandled reason_code {reason_code!r}"


# ---------------------------------------------------------------------------
# Protocol runner — applies transition + returns event record
# ---------------------------------------------------------------------------

def apply_transition(
    agent_name: str,
    transition: str,
    from_stage: str,
    task_type: Optional[str],
    orbit_before: Tuple[int, int],
    evidence: Dict[str, Any],
) -> Tuple[bool, Optional[DifferentiationEvent], str]:
    """Validate and apply a differentiation transition.

    Returns (ok, event_or_None, message).
    """
    if transition not in VALID_TRANSITIONS:
        return False, None, f"unknown transition {transition!r}"

    # Determine target stage and orbit
    stage_map = {
        "FIRST_TRIAL":    ("undifferentiated", "progenitor", SATELLITE_SEED),
        "COMMIT":         ("progenitor",        "committed",  COSMOS_SEED),
        "PARTIAL_FAIL":   ("progenitor",        "undifferentiated", SINGULARITY_SEED),
        "DEDIFFERENTIATE":("committed",          "undifferentiated", SINGULARITY_SEED),
    }
    # DEDIFFERENTIATE also valid from progenitor
    if transition == "DEDIFFERENTIATE" and from_stage == "progenitor":
        expected_from, to_stage, orbit_after = "progenitor", "undifferentiated", SINGULARITY_SEED
    else:
        expected_from, to_stage, orbit_after = stage_map[transition]

    # Route to appropriate checker
    if transition == "FIRST_TRIAL":
        ok, msg = check_first_trial(from_stage, task_type)
    elif transition == "COMMIT":
        ok, msg = check_commit(
            stage=from_stage,
            task_type=task_type,
            trial_type=evidence.get("trial_type"),
            successes=evidence.get("successes", 0),
            orbit_family=evidence.get("orbit_family", "cosmos"),
            commit_threshold=evidence.get("commit_threshold", COMMIT_THRESHOLD),
        )
    elif transition == "PARTIAL_FAIL":
        ok, msg = check_partial_fail(
            stage=from_stage,
            consecutive_failures=evidence.get("consecutive_failures", 0),
            max_consecutive=evidence.get("max_consecutive", MAX_CONSECUTIVE_FAILURES),
        )
    elif transition == "DEDIFFERENTIATE":
        ok, msg = check_dedifferentiate(
            stage=from_stage,
            reason_code=evidence.get("reason_code", "OPERATOR_COMMAND"),
            success_rate=evidence.get("success_rate", 1.0),
            total_tasks=evidence.get("total_tasks", 0),
            orbit_drift_count=evidence.get("orbit_drift_count", 0),
            is_operator_command=evidence.get("is_operator_command", False),
            is_metamorphosis=evidence.get("is_metamorphosis", False),
            min_success_rate=evidence.get("min_success_rate", MIN_SUCCESS_RATE),
            min_eval_window=evidence.get("min_eval_window", MIN_EVAL_WINDOW),
            max_drift_count=evidence.get("max_drift_count", MAX_DRIFT_COUNT),
        )
    else:
        return False, None, f"unhandled transition {transition!r}"

    if not ok:
        return False, None, msg

    event = DifferentiationEvent(
        agent_name=agent_name,
        transition=transition,
        from_stage=from_stage,
        to_stage=to_stage,
        task_type=task_type,
        evidence=evidence,
        orbit_before=orbit_before,
        orbit_after=orbit_after,
    )
    return True, event, msg


# ---------------------------------------------------------------------------
# Organ membership check
# ---------------------------------------------------------------------------

def check_organ_eligibility(
    agent_orbit_sig: str,
    agent_levin_type: str,
    organ_has_spine: bool,
    failure_modes: List[str],
    organ_blocked_failures: List[str],
) -> Tuple[bool, List[str]]:
    """Check if a committed agent can join an organ.

    Returns (eligible, list_of_blocking_reasons).
    """
    reasons = []

    if agent_orbit_sig != "cosmos":
        reasons.append(f"agent orbit_sig={agent_orbit_sig!r} must be cosmos to join organ")
    if agent_levin_type != "differentiated":
        reasons.append(f"agent levin_type={agent_levin_type!r} must be differentiated to join organ")
    if not organ_has_spine:
        reasons.append("organ has no cosmos spine agent — organ cannot be formed without a spine")
    for fm in failure_modes:
        if fm in organ_blocked_failures:
            reasons.append(f"agent failure_mode {fm!r} is blocked by organ")

    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def run_self_test() -> bool:
    print("Differentiation Protocol self-test")
    ok = True

    # 1. FIRST_TRIAL valid
    r, ev, msg = apply_transition(
        "test_agent", "FIRST_TRIAL", "undifferentiated", "query",
        (0, 0), {}
    )
    assert r and ev and ev.to_stage == "progenitor" and ev.orbit_after == SATELLITE_SEED, \
        f"FIRST_TRIAL failed: {msg}"
    print(f"  FIRST_TRIAL (stem→progenitor): PASS")

    # 2. FIRST_TRIAL blocked — wrong stage
    r, ev, msg = apply_transition(
        "test_agent", "FIRST_TRIAL", "committed", "query", (1, 1), {}
    )
    assert not r, f"FIRST_TRIAL should fail for committed stage"
    print(f"  FIRST_TRIAL blocked (committed): PASS")

    # 3. COMMIT valid
    r, ev, msg = apply_transition(
        "test_agent", "COMMIT", "progenitor", "query",
        (2, 3), {
            "trial_type": "query", "successes": 3,
            "orbit_family": "cosmos", "commit_threshold": 3,  # noqa: ORBIT-2 — test fixture
        }
    )
    assert r and ev and ev.to_stage == "committed" and ev.orbit_after == COSMOS_SEED, \
        f"COMMIT failed: {msg}"
    print(f"  COMMIT (progenitor→committed): PASS")

    # 4. COMMIT blocked — insufficient successes
    r, ev, msg = apply_transition(
        "test_agent", "COMMIT", "progenitor", "query",
        (2, 3), {
            "trial_type": "query", "successes": 1,
            "orbit_family": "cosmos", "commit_threshold": 3,  # noqa: ORBIT-2 — test fixture
        }
    )
    assert not r, f"COMMIT should fail with only 1 success"
    print(f"  COMMIT blocked (1 success < 3): PASS")

    # 5. COMMIT blocked — singularity orbit
    r, ev, msg = apply_transition(
        "test_agent", "COMMIT", "progenitor", "query",
        (0, 0), {
            "trial_type": "query", "successes": 3,
            "orbit_family": "singularity", "commit_threshold": 3,  # noqa: ORBIT-2 — test fixture
        }
    )
    assert not r, f"COMMIT should fail in singularity orbit"
    print(f"  COMMIT blocked (singularity orbit): PASS")

    # 6. PARTIAL_FAIL valid
    r, ev, msg = apply_transition(
        "test_agent", "PARTIAL_FAIL", "progenitor", "query",
        (2, 3), {"consecutive_failures": 5, "max_consecutive": 5}
    )
    assert r and ev and ev.to_stage == "undifferentiated" and ev.orbit_after == SINGULARITY_SEED, \
        f"PARTIAL_FAIL failed: {msg}"
    print(f"  PARTIAL_FAIL (progenitor→stem): PASS")

    # 7. PARTIAL_FAIL not yet — only 3 failures
    r, ev, msg = apply_transition(
        "test_agent", "PARTIAL_FAIL", "progenitor", "query",
        (2, 3), {"consecutive_failures": 3, "max_consecutive": 5}
    )
    assert not r, f"PARTIAL_FAIL should not trigger at 3/5"
    print(f"  PARTIAL_FAIL blocked (3/5 failures): PASS")

    # 8. DEDIFFERENTIATE — LOW_SUCCESS_RATE
    r, ev, msg = apply_transition(
        "test_agent", "DEDIFFERENTIATE", "committed", "query",
        (1, 1), {
            "reason_code": "LOW_SUCCESS_RATE",
            "success_rate": 0.25, "total_tasks": 12,
            "min_success_rate": 0.4, "min_eval_window": 10,
        }
    )
    assert r and ev and ev.to_stage == "undifferentiated", f"DEDIFF LOW_RATE failed: {msg}"
    print(f"  DEDIFFERENTIATE LOW_SUCCESS_RATE: PASS")

    # 9. DEDIFFERENTIATE blocked — not enough tasks
    r, ev, msg = apply_transition(
        "test_agent", "DEDIFFERENTIATE", "committed", "query",
        (1, 1), {
            "reason_code": "LOW_SUCCESS_RATE",
            "success_rate": 0.1, "total_tasks": 5,
            "min_success_rate": 0.4, "min_eval_window": 10,
        }
    )
    assert not r, f"DEDIFF should be blocked with only 5 tasks"
    print(f"  DEDIFFERENTIATE blocked (5 < 10 tasks): PASS")

    # 10. DEDIFFERENTIATE — OPERATOR_COMMAND
    r, ev, msg = apply_transition(
        "test_agent", "DEDIFFERENTIATE", "committed", "query",
        (1, 1), {"reason_code": "OPERATOR_COMMAND", "is_operator_command": True}
    )
    assert r and ev, f"DEDIFF OPERATOR_COMMAND failed: {msg}"
    print(f"  DEDIFFERENTIATE OPERATOR_COMMAND: PASS")

    # 11. Organ eligibility — valid
    eligible, reasons = check_organ_eligibility(
        agent_orbit_sig="cosmos",
        agent_levin_type="differentiated",
        organ_has_spine=True,
        failure_modes=["out of memory"],
        organ_blocked_failures=["stack overflow"],
    )
    assert eligible, f"Organ eligibility failed: {reasons}"
    print(f"  Organ eligibility (cosmos/differentiated): PASS")

    # 12. Organ eligibility — no spine
    eligible, reasons = check_organ_eligibility(
        agent_orbit_sig="cosmos",
        agent_levin_type="differentiated",
        organ_has_spine=False,
        failure_modes=[],
        organ_blocked_failures=[],
    )
    assert not eligible, "Organ should be blocked without spine"
    print(f"  Organ eligibility blocked (no spine): PASS")

    print(f"\nAll 12 checks passed — differentiation protocol ok")
    return True


if __name__ == "__main__":
    import sys
    ok = run_self_test()
    sys.exit(0 if ok else 1)
