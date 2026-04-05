#!/usr/bin/env python3
"""
Synthetic test harness for SelfImprovementAgentV2.

Runs v2 across a 5-cycle mock-kernel fixture and asserts the four
properties from ``docs/qa_lab/SELF_IMPROVEMENT_AGENT_DESIGN.md §12``:

  A. Every proposal carries a ``level`` key.
  B. No ``L_2b`` or ``L_3`` proposal ever reaches ``applied``.
  C. ``lyap_post <= lyap_pre + tol`` for every ``CONSISTENT``-verdict cycle.
  D. All three fixed-point candidate fields (A, B, C) are populated
     with numeric values.

Plus one extra assertion driven by design doc §10.6:

  E. Snapshot-and-restore is correctness-preserving — a deliberately
     injected "bad" L_2a proposal that worsens the Lyapunov is rolled
     back, and no kernel state survives the rollback.

The harness uses a hand-rolled MockKernel that exposes exactly the
surface v2 touches (``_b``, ``_e``, ``_results``, ``_agents``,
``_spawn_queue``, ``_agent_perf``, ``_cycle_count``, ``_satellite_streak``,
``metamorphosis_threshold``, ``_kernel_run_id``, ``repo_root``,
``modulus``, ``agent_performance()``).

Run directly:

    cd qa_lab
    python test_self_improvement_v2.py
"""
from __future__ import annotations

QA_COMPLIANCE = "qa_lab_test_self_improvement_v2 — unit harness for SelfImprovementAgentV2; mock kernel state stays integer; Lyapunov values in the mock are observer-layer measurements per Theorem NT and never feed back as QA causal inputs"

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_QA_LAB_DIR = Path(__file__).resolve().parent
if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from agents.self_improvement_agent_v2 import SelfImprovementAgentV2


# ---------------------------------------------------------------------------
# Minimal mocks
# ---------------------------------------------------------------------------


@dataclass
class MockResult:
    rho: float
    orbit_family: str
    verified: bool = True


@dataclass
class MockTask:
    task_type: str
    description: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    task_id: str = "mock"


class MockKernel:
    def __init__(
        self,
        modulus: int = 9,
        rho_tail: Optional[List[float]] = None,
        family_tail: Optional[List[str]] = None,
        tmp_root: Optional[Path] = None,
        weak_agent: bool = False,
    ) -> None:
        self.modulus = modulus
        self._b = 1
        self._e = 1
        self._cycle_count = 10
        self._satellite_streak = 0
        self.metamorphosis_threshold = 5
        self._kernel_run_id = "mock-run-1"
        self.repo_root = tmp_root if tmp_root is not None else Path(tempfile.mkdtemp())
        self._agents: Dict[str, Any] = {}
        self._spawn_queue: List[Dict[str, Any]] = []
        self._agent_perf: Dict[str, Dict[str, Any]] = {}
        if weak_agent:
            self._agent_perf["query"] = {
                "ok": 1,
                "fail": 6,
                "verdicts": {"CONSISTENT": 1, "CONTRADICTS": 6},
                "orbit_drift": 0,
            }
        # Seed results tail.
        rho_tail = rho_tail or [0.9, 0.85, 0.8, 0.78, 0.76, 0.75, 0.74, 0.72]
        family_tail = family_tail or ["cosmos"] * len(rho_tail)
        self._results: List[MockResult] = [
            MockResult(rho=r, orbit_family=f)
            for r, f in zip(rho_tail, family_tail)
        ]

    def agent_performance(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for tt, perf in self._agent_perf.items():
            total = perf["ok"] + perf["fail"]
            out[tt] = {
                "total": total,
                "success_rate": round(perf["ok"] / total, 3) if total else 0.0,
                "verdicts": perf["verdicts"],
                "orbit_drift_count": perf["orbit_drift"],
                "needs_improvement": perf["fail"] > perf["ok"] or perf["orbit_drift"] > 2,
            }
        return out


def _make_improve_task(kernel: MockKernel, extra: Optional[Dict[str, Any]] = None) -> MockTask:
    extra = extra or {}
    return MockTask(
        task_type="improve",
        description="v2 test cycle",
        inputs={
            "introspect": {
                "kernel_orbit": (kernel._b, kernel._e),
                "kernel_family": "cosmos",
                "cycles": kernel._cycle_count,
                "agent_performance": kernel.agent_performance(),
                "weak_agents": [
                    tt for tt, p in kernel.agent_performance().items()
                    if p["needs_improvement"]
                ],
                "improvement_suggestions": [],
                "health": (
                    "needs_attention"
                    if any(
                        p["needs_improvement"]
                        for p in kernel.agent_performance().values()
                    )
                    else "good"
                ),
            },
            "orbit_context": {
                "satellite_streak": kernel._satellite_streak,
                "metamorphosis_threshold": kernel.metamorphosis_threshold,
                "kernel_family": "cosmos",
            },
            "spawn_queue": list(kernel._spawn_queue),
            "ob_context": "",
            "kernel_ref": kernel,
            **extra,
        },
    )


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

FAILURES: List[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        FAILURES.append(f"{label}: {detail}")
        print(f"  FAIL  {label}  {detail}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_synthetic_5_cycles() -> None:
    print("[T1] 5-cycle synthetic harness (HEALTHY kernel)")
    kernel = MockKernel()
    agent = SelfImprovementAgentV2()

    all_proposals: List[Dict[str, Any]] = []
    all_applied: List[Dict[str, Any]] = []
    lyaps: List[tuple] = []
    verdicts: List[str] = []
    fp_readouts: List[Dict[str, Any]] = []

    for cycle in range(5):
        task = _make_improve_task(kernel)
        out = agent.handle(task)
        all_proposals.extend(out["proposals"])
        all_applied.extend(out["applied"])
        lyaps.append((out["lyapunov"]["pre"], out["lyapunov"]["post"], out["lyapunov"]["tol"]))
        verdicts.append(out["verdict"])
        fp_readouts.append(out["fixed_point_candidates"])
        # Simulate modest kernel drift between cycles by appending another
        # healthy result.
        kernel._results.append(MockResult(rho=0.72 - 0.01 * cycle, orbit_family="cosmos"))  # noqa: ORBIT-2

    # Assertion A — every proposal has a level key.
    missing_level = [p for p in all_proposals if "level" not in p]
    check(
        "A. every proposal carries a 'level' key",
        not missing_level,
        f"{len(missing_level)} proposal(s) missing level",
    )

    # Assertion B — no L_2b or L_3 in applied.
    bad_applied = [a for a in all_applied if a.get("level") in ("L_2b", "L_3")]
    check(
        "B. no L_2b / L_3 in applied",
        not bad_applied,
        f"{len(bad_applied)} forbidden applied",
    )

    # Assertion C — CONSISTENT cycles have lyap_post <= lyap_pre + tol.
    bad_monotone = [
        (i, pre, post, tol)
        for i, ((pre, post, tol), v) in enumerate(zip(lyaps, verdicts))
        if v == "CONSISTENT" and post > pre + tol
    ]
    check(
        "C. CONSISTENT cycles: lyap_post <= lyap_pre + tol",
        not bad_monotone,
        f"violations: {bad_monotone}",
    )

    # Assertion D — all three FP candidate fields populated + numeric.
    bad_fp = []
    for i, fp in enumerate(fp_readouts):
        for key in ("A_trace_compression", "B_routing_barycenter", "C_pisano_periodicity"):
            v = fp.get(key)
            if not isinstance(v, (int, float)):
                bad_fp.append((i, key, type(v).__name__))
    check(
        "D. all three fixed-point candidates populated with numeric values",
        not bad_fp,
        f"bad: {bad_fp}",
    )


def test_weak_agent_L2a_gate() -> None:
    """A weak agent should trigger R3 WEAK_AGENT → L_2a proposal → probe gate.

    With a monotone-improving rho tail, the probe should commit the spawn
    spec append.
    """
    print("[T2] L_2a gate on weak agent (R3 SPAWN_IMPROVED)")
    kernel = MockKernel(weak_agent=True)
    agent = SelfImprovementAgentV2()
    task = _make_improve_task(kernel)

    out = agent.handle(task)
    l2a_proposals = [p for p in out["proposals"] if p.get("level") == "L_2a"]
    check(
        "T2a. at least one L_2a proposal generated",
        bool(l2a_proposals),
        f"proposals={[(p.get('rule'), p.get('level')) for p in out['proposals']]}",
    )
    # After commit, spawn queue should contain a pending spec for the weak agent.
    pending = [
        s for s in kernel._spawn_queue
        if s.get("required_capability") == "query"
    ]
    check(
        "T2b. L_2a committed → spawn queue has pending spec for query",
        bool(pending),
        f"queue={kernel._spawn_queue}",
    )
    # And the applied list contains at least one L_2a with committed=True.
    committed_l2a = [
        a for a in out["applied"] if a.get("level") == "L_2a" and a.get("committed")
    ]
    check(
        "T2c. applied list contains committed L_2a entry",
        bool(committed_l2a),
        f"applied={[(a.get('rule'), a.get('committed')) for a in out['applied']]}",
    )


def test_snapshot_restore_on_bad_lyap() -> None:
    """Force a rollback path by injecting a Lyapunov that jumps after apply.

    We monkey-patch ``_compute_lyapunov`` so the second call (post-apply,
    probe) returns a much larger value.  The probe gate must then roll
    back the spawn queue append.
    """
    print("[T3] snapshot-restore rolls back on worsened Lyapunov")
    kernel = MockKernel(weak_agent=True)
    agent = SelfImprovementAgentV2()

    pre_spawn_len = len(kernel._spawn_queue)

    call_count = {"n": 0}
    original_compute = agent._compute_lyapunov

    def fake_compute(kref: Any) -> float:
        call_count["n"] += 1
        # Call sequence inside one handle():
        #   1. lyap_pre
        #   2-4. all_lyapunov snapshot (rho_ewma / sat_fraction / weighted_sr)
        #   5. probe measurement inside _apply_with_probe
        #   6. lyap_post
        # We want the probe (call 5) to report the catastrophic jump so
        # the gate rolls back.
        if call_count["n"] < 5:
            return 0.1
        return 99.0

    agent._compute_lyapunov = fake_compute  # type: ignore[assignment]
    try:
        task = _make_improve_task(kernel)
        out = agent.handle(task)
    finally:
        agent._compute_lyapunov = original_compute  # type: ignore[assignment]

    # Spawn queue should be unchanged (rolled back).
    post_spawn_len = len(kernel._spawn_queue)
    check(
        "T3a. spawn queue length preserved on rollback",
        post_spawn_len == pre_spawn_len,
        f"pre={pre_spawn_len} post={post_spawn_len}",
    )

    # No L_2a should be committed in applied.
    committed_l2a = [
        a for a in out["applied"] if a.get("level") == "L_2a" and a.get("committed")
    ]
    check(
        "T3b. no L_2a committed when Lyapunov worsens",
        not committed_l2a,
        f"committed={committed_l2a}",
    )

    # Verdict should be CONTRADICTS because lyap_post > lyap_pre + tol.
    check(
        "T3c. verdict is CONTRADICTS on lyap worsening",
        out["verdict"] == "CONTRADICTS",
        f"verdict={out['verdict']}",
    )


def test_L2b_never_applied() -> None:
    """R4 ORBIT_DRIFT fires when an agent has orbit_drift > 2, and must be
    tagged L_2b and deferred, never applied.
    """
    print("[T4] L_2b (R4 ORBIT_DRIFT) always deferred")
    kernel = MockKernel()
    kernel._agent_perf["query"] = {
        "ok": 5,
        "fail": 1,
        "verdicts": {},
        "orbit_drift": 5,
    }
    agent = SelfImprovementAgentV2()
    task = _make_improve_task(kernel)
    out = agent.handle(task)

    l2b_in_applied = [a for a in out["applied"] if a.get("level") == "L_2b"]
    check(
        "T4a. no L_2b in applied",
        not l2b_in_applied,
        f"applied={[(a.get('rule'), a.get('level')) for a in out['applied']]}",
    )
    l2b_in_deferred = [d for d in out["deferred"] if d.get("level") == "L_2b"]
    check(
        "T4b. at least one L_2b deferred",
        bool(l2b_in_deferred),
        f"deferred={[(d.get('rule'), d.get('level')) for d in out['deferred']]}",
    )


def main() -> int:
    test_synthetic_5_cycles()
    test_weak_agent_L2a_gate()
    test_snapshot_restore_on_bad_lyap()
    test_L2b_never_applied()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} assertion(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
