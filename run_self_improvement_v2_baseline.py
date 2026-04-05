#!/usr/bin/env python3
"""
Run one real IMPROVE cycle against a live QALabKernel with
SelfImprovementAgentV2 registered, and dump the baseline fixed-point
readout to ``qa_lab/kernel/self_improvement_v2_baseline.json``.

This is the `lab-self-improvement` session's "one real cycle" deliverable
(kickoff doc §Deliverables item 4).  The kernel is instantiated fresh
(``_results`` starts empty), but the three ledger JSONL files exist from
prior sessions — candidates A (trace compression) and C (Pisano
periodicity) read directly from ``orbit_transition_log.jsonl`` and
therefore see the full 823-row tail.  Candidate B (routing barycenter)
reads ``task_state_trace.jsonl`` (2463 rows).  The ``rho_ewma`` Lyapunov
reads the in-memory ``_results`` list and will collapse to the default
``1.0`` on a fresh kernel — this is honest, not a bug: the smoothed rho
requires prior cycles in the same kernel instance to become informative.

Usage::

    cd qa_lab
    python run_self_improvement_v2_baseline.py
"""
from __future__ import annotations

QA_COMPLIANCE = "qa_lab_self_improvement_baseline_runner — instantiates QALabKernel and runs one IMPROVE cycle; Lyapunov reading and fixed-point candidates are observer-layer measurements per Theorem NT; no continuous state enters QA logic"

import json
import sys
import datetime
from pathlib import Path

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_LAB_DIR.parent
if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from kernel.loop import QALabKernel, Task, TaskType
from agents.self_improvement_agent_v2 import SelfImprovementAgentV2


def _json_default(o):
    """Make KernelResult / agent objects / datetime JSON-serializable."""
    if hasattr(o, "__dataclass_fields__"):
        return {k: getattr(o, k) for k in o.__dataclass_fields__}
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    if isinstance(o, TaskType):
        return o.value
    if hasattr(o, "status"):
        try:
            return {"_agent": type(o).__name__, **o.status()}
        except Exception:
            return {"_agent": type(o).__name__}
    return str(o)


def _strip_nonserializable(d):
    """Remove kernel_ref from cert evidence (circular + huge) for JSON dump."""
    if isinstance(d, dict):
        return {k: _strip_nonserializable(v) for k, v in d.items() if k != "kernel_ref"}
    if isinstance(d, list):
        return [_strip_nonserializable(x) for x in d]
    return d


def main() -> int:
    kernel = QALabKernel(
        repo_root=_REPO_ROOT,
        modulus=9,
        verbose=False,
        dry_run=False,
        require_spawn_approval=True,
    )
    agent = SelfImprovementAgentV2(
        modulus=9,
        lyapunov="rho_ewma",
        lyapunov_alpha=0.2,
        dry_run_probe_cycles=0,  # baseline: probe cycles off; see OB capture
    )
    kernel.register_agent(TaskType.IMPROVE, agent)

    task = Task(
        task_type=TaskType.IMPROVE,
        description="baseline self-improvement v2 cycle (lab-self-improvement)",
    )

    print(f"[baseline] running one IMPROVE cycle against live kernel "
          f"run_id={kernel._kernel_run_id}")

    result = kernel.run_cycle(task)

    out = result.output
    readout = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session": "lab-self-improvement",
        "kernel_run_id": kernel._kernel_run_id,
        "kernel_orbit": list(kernel.orbit_state),
        "kernel_family": kernel.orbit_family,
        "kernel_modulus": kernel.modulus,
        "agent": {
            "name": agent.name,
            "version": "v2",
            "cert_family": agent.cert_family,
            "lyapunov_name": agent.lyapunov_name,
            "lyapunov_alpha": agent.alpha,
            "dry_run_probe_cycles": agent.dry_run_probe_cycles,
            "max_applied_per_cycle": agent.max_applied_per_cycle,
            "orbit_state": list(agent.orbit_state),
            "orbit_family": agent.orbit_family,
        },
        "cycle": {
            "verdict": out.get("verdict"),
            "summary": out.get("summary"),
            "proposals": _strip_nonserializable(out.get("proposals", [])),
            "applied": _strip_nonserializable(out.get("applied", [])),
            "deferred": _strip_nonserializable(out.get("deferred", [])),
            "lyapunov": out.get("lyapunov"),
            "fixed_point_candidates": out.get("fixed_point_candidates"),
            "kernel_quality_vector": out.get("kernel_quality_vector"),
            "cert_hash": (out.get("cert") or {}).get("cert_hash"),
        },
        "notes": {
            "rho_ewma_is_1_on_fresh_kernel": (
                "The kernel was instantiated fresh; _results starts empty, so "
                "the ρ-EWMA reduces to its default (1.0). Candidates A and C "
                "read directly from the persistent JSONL ledgers and reflect "
                "real history. The smoothed ρ becomes informative only after "
                "≥1 real non-IMPROVE cycles have run in the same process."
            ),
            "probe_cycles_disabled": (
                "dry_run_probe_cycles=0 for this baseline: snapshot-and-restore "
                "is exercised through the unit harness, not on live kernel "
                "trajectories. The next session may flip this to 3 once the "
                "isolated-ledgers path has been audited on real tasks."
            ),
            "meta_validator_untouched": (
                "Cert stub at qa_alphageometry_ptolemy/qa_self_improvement_cert_v1/ "
                "is NOT registered in qa_meta_validator.py per guardrail §"
                "Deliverables item 7."
            ),
        },
    }

    out_path = _QA_LAB_DIR / "kernel" / "self_improvement_v2_baseline.json"
    out_path.write_text(
        json.dumps(readout, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )
    print(f"[baseline] wrote readout: {out_path.relative_to(_REPO_ROOT)}")
    print(f"[baseline] verdict={out['verdict']} "
          f"lyap={out['lyapunov']['name']}: "
          f"{out['lyapunov']['pre']:.6f} → {out['lyapunov']['post']:.6f}")
    fp = out["fixed_point_candidates"]
    print(f"[baseline] fixed-point candidates:")
    print(f"    A trace_compression  = {fp['A_trace_compression']:.6f}")
    print(f"    B routing_barycenter = {fp['B_routing_barycenter']:.6f}")
    print(f"    C pisano_periodicity = {fp['C_pisano_periodicity']:.6f}")
    print(f"    all_lyapunovs        = {fp['all_lyapunovs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
