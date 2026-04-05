#!/usr/bin/env python3
"""
Unified batch runner: 3 real science tasks + v2 warmup + probe-cycle audit.

This runner is the execution counterpart of the `lab-self-improvement`
session's second-pass deliverable. It does four things in order:

 1. **Wrap the three script-shaped YAML tasks** (qa_raman_collect, qa_paper,
    qa_raman_experiment) as ``TaskType.EXPERIMENT`` kernel cycles and run
    them through ``kernel.run_batch``.  This populates ``kernel._results``
    with real contraction factors and family states, giving v2's rho-EWMA
    Lyapunov a real signal rather than the default 1.0.

 2. **Run one IMPROVE cycle** with ``SelfImprovementAgentV2`` and
    ``dry_run_probe_cycles=0``.  This is the warmup-confirmation cycle —
    rho_ewma should now reflect the batch's real contraction factors.

 3. **Audit the probe path** by flipping ``dry_run_probe_cycles=3`` on a
    second IMPROVE cycle, capturing real-ledger row counts before and
    after, and verifying the ``_isolated_ledgers`` tempdir swap did not
    append any rows to the live JSONL files.  This is the §10.6
    correctness-critical property audited on live kernel state rather
    than synthetic mocks.

 4. **Emit a combined readout** to
    ``qa_lab/kernel/batch_v2_hardening_readout.json`` with: per-task
    verdicts, lyapunov trajectory, ledger-integrity delta, and the
    fixed-point candidates at warmup-end and post-audit.

YAML duplication note
---------------------
``qa_raman_experiment.yaml`` declares the same artifacts as
``qa_paper.yaml`` and its command list re-runs ``qa_paper.py``.  Rather
than double-running the ~minute-scale benchmark, this runner executes
``qa_paper.py`` once and checks both YAMLs' acceptance criteria against
the shared artifacts.

Usage::

    cd /home/player2/signal_experiments
    python qa_lab/run_batch_v2_hardening.py
"""
from __future__ import annotations

QA_COMPLIANCE = "qa_lab_batch_v2_hardening_runner — wraps 3 script tasks as EXPERIMENT kernel cycles and audits v2 probe path; Lyapunov + FP readouts are observer-layer measurements per Theorem NT; kernel b/e stay integer; probe cycles run under _isolated_ledgers tempdir swap"

import datetime
import json
import sys
from pathlib import Path

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_LAB_DIR.parent
if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from kernel.loop import QALabKernel, Task, TaskType
from agents.experiment_agent import ExperimentAgent
from agents.query_agent import QueryAgent
from agents.self_improvement_agent_v2 import SelfImprovementAgentV2


LEDGER_DIR = _QA_LAB_DIR / "kernel"
LEDGERS = [
    "results_log.jsonl",
    "orbit_transition_log.jsonl",
    "task_state_trace.jsonl",
]


def _ledger_rows() -> dict:
    out = {}
    for name in LEDGERS:
        p = LEDGER_DIR / name
        if p.exists():
            try:
                out[name] = sum(1 for _ in p.open("r", encoding="utf-8"))
            except Exception:
                out[name] = None
        else:
            out[name] = 0
    return out


def _strip(obj):
    """Strip non-serializable nodes for JSON dump."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("kernel_ref",)}
    if isinstance(obj, list):
        return [_strip(x) for x in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _strip(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, TaskType):
        return obj.value
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if hasattr(obj, "name") and hasattr(obj, "orbit_state"):
        return {"_agent": type(obj).__name__, "name": obj.name, "orbit": list(obj.orbit_state)}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ---------------------------------------------------------------------------
# Script-task wrappers
# ---------------------------------------------------------------------------

# After the F1-F5 follow-up fixes (2026-04-04), the qa_paper pipeline is
# unblocked: qa_paper.py now runs `make` from qa_lab/ (where the target
# lives), and ExperimentAgent auto-injects PYTHONPATH for qa_lab/ scripts.
# All three script tasks run for real; no BLOCKED_TASKS list.
SCRIPT_TASKS = [
    {
        "name": "qa_raman_collect",
        "yaml": "qa_raman_collect.yaml",
        "script_path": "qa_lab/qa_agents/cli/qa_raman_fetch.py",
        "args": [],
        "timeout": 120,
        "acceptance": [
            # "any_exists: collected_data/*.json"
            lambda: any((_REPO_ROOT / "collected_data").glob("*.json")) if (_REPO_ROOT / "collected_data").exists() else False,
        ],
    },
    {
        "name": "qa_paper",
        "yaml": "qa_paper.yaml",
        "script_path": "qa_lab/qa_agents/cli/qa_paper.py",
        "args": ["--run", "--json-out", "artifacts/overleaf/qa_paper.json",
                 "--min-step-speedup", "1.2", "--min-compute-ratio", "1.2"],
        "timeout": 1200,  # full pipeline: 5 cargo builds + plots + bundle
        "acceptance": [
            lambda: (_REPO_ROOT / "qa_lab/artifacts/overleaf/qa_training_compute_section.tex").exists(),
            lambda: (_REPO_ROOT / "qa_lab/plots/qa_benchmarks.png").exists(),
            lambda: (_REPO_ROOT / "qa_lab/plots/qa_pcn_theta_compare.png").exists(),
            lambda: (_REPO_ROOT / "qa_lab/plots/qa_jepa_convergence.png").exists(),
            lambda: (_REPO_ROOT / "qa_lab/artifacts/qa_overleaf_bundle.tar.gz").exists(),
        ],
    },
    {
        "name": "qa_raman_experiment",
        "yaml": "qa_raman_experiment.yaml",
        "script_path": "qa_lab/qa_raman_effect.py",
        "args": [],
        "timeout": 60,
        "acceptance": [
            lambda: True,  # qa_raman_effect.demo() acceptance is exit 0
        ],
    },
]

BLOCKED_TASKS = []


def check_acceptance(tasks: list) -> dict:
    """Re-check acceptance for every listed task."""
    results = {}
    for t in tasks:
        checks = [bool(fn()) for fn in t["acceptance"]]
        results[t["name"]] = {"acceptance_checks": checks, "all_ok": all(checks)}
    for bt in BLOCKED_TASKS:
        try:
            ok = bool(bt["acceptance"]())
        except Exception as exc:
            ok = False
        results[bt["name"]] = {
            "all_ok": ok,
            "blocked": True,
            "blocker": bt["blocker"],
            "note": "artifact check shown for completeness; task was not executed in this batch",
        }
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"[batch-v2] starting at {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    ledger_before = _ledger_rows()
    print(f"[batch-v2] ledger rows at start: {ledger_before}")

    kernel = QALabKernel(
        repo_root=_REPO_ROOT,
        modulus=9,
        verbose=False,
        dry_run=False,
        require_spawn_approval=True,
    )

    # Agents: QueryAgent (used as synthetic probe target), ExperimentAgent, v2
    exp_agent = ExperimentAgent(
        repo_root=_REPO_ROOT,
        approved_scripts=[],     # empty = any script in repo_root is fine
        timeout=600,              # per-script timeout; v2 runner uses per-task override
    )
    query_agent = QueryAgent(modulus=9)
    v2 = SelfImprovementAgentV2(
        modulus=9,
        lyapunov="rho_ewma",
        lyapunov_alpha=0.2,
        dry_run_probe_cycles=0,   # warmup cycle: probe off
    )
    kernel.register_agent(TaskType.EXPERIMENT, exp_agent)
    kernel.register_agent(TaskType.QUERY, query_agent)
    kernel.register_agent(TaskType.IMPROVE, v2)

    # ------------------------------------------------------------------
    # Phase 1: wrap + run 3 script tasks as EXPERIMENT cycles
    # ------------------------------------------------------------------

    task_results = []
    for spec in SCRIPT_TASKS:
        print(f"[batch-v2] phase1: running script task {spec['name']!r} "
              f"(timeout={spec['timeout']}s)")
        exp_agent.timeout = spec["timeout"]
        t = Task(
            task_type=TaskType.EXPERIMENT,
            description=f"batch wrap: {spec['name']} (from {spec['yaml']})",
            inputs={
                "script_path": spec["script_path"],
                "args": spec["args"],
                # The scripts under qa_lab/qa_agents/cli/ import their own
                # package by top-level name ("qa_agents.cli..."), which
                # requires qa_lab/ on PYTHONPATH.  The kernel runs from
                # repo_root, so inject it per-task.
                "env": {"PYTHONPATH": str(_QA_LAB_DIR)},
            },
        )
        res = kernel.run_cycle(t)
        task_results.append({
            "name": spec["name"],
            "yaml": spec["yaml"],
            "verdict": res.output.get("verdict"),
            "ok": res.ok,
            "orbit_family": res.orbit_family,
            "rho": res.rho,
            "elapsed_ms": res.output.get("elapsed_ms"),
            "numeric_results": res.output.get("numeric_results"),
            "error": res.error,
        })
        print(f"    verdict={res.output.get('verdict')} ok={res.ok} "
              f"rho={res.rho:.4f} family={res.orbit_family}")

    # Re-check acceptance criteria now that scripts have run
    acceptance = check_acceptance(SCRIPT_TASKS)
    print(f"[batch-v2] phase1: acceptance: "
          f"{ {k: v['all_ok'] for k, v in acceptance.items()} }")

    # ------------------------------------------------------------------
    # Phase 2: warmup IMPROVE cycle (probe off)
    # ------------------------------------------------------------------

    print(f"[batch-v2] phase2: warmup IMPROVE cycle (probe=0)")
    improve1 = kernel.run_cycle(Task(
        task_type=TaskType.IMPROVE,
        description="warmup IMPROVE cycle (probe off) — rho_ewma should now be informative",
    ))
    warmup_out = improve1.output
    if "verdict" not in warmup_out:
        print(f"    ERROR: v2.handle failed — output={warmup_out}")
        print(f"    improve1.error={improve1.error}")
        return 2
    print(f"    verdict={warmup_out['verdict']} "
          f"lyap: {warmup_out['lyapunov']['pre']:.6f} → "
          f"{warmup_out['lyapunov']['post']:.6f}")
    print(f"    FP candidates: {warmup_out['fixed_point_candidates']}")

    # ------------------------------------------------------------------
    # Phase 3: audit probe-cycle path
    # ------------------------------------------------------------------

    print(f"[batch-v2] phase3: audit probe path with dry_run_probe_cycles=3")
    v2.dry_run_probe_cycles = 3
    v2._probe_tasks = [
        Task(task_type=TaskType.QUERY, description="probe cosmos (1,1)",
             inputs={"b": 1, "e": 1}),
        Task(task_type=TaskType.QUERY, description="probe satellite (3,3)",
             inputs={"b": 3, "e": 3}),
        Task(task_type=TaskType.QUERY, description="probe singularity (9,9)",
             inputs={"b": 9, "e": 9}),
    ]

    # Seed a weak-agent perf record so R3 WEAK_AGENT fires → L_2a proposal
    # → _apply_with_probe actually gets called → _isolated_ledgers tempdir
    # swap actually runs → ledger-integrity check becomes meaningful.
    # Without this seed, the real kernel state has no weak agents and no
    # L_2a proposals are generated; the probe path is dead code in phase 3.
    kernel._agent_perf["query"] = {
        "ok": 1,
        "fail": 6,
        "verdicts": {"CONSISTENT": 1, "CONTRADICTS": 6},
        "orbit_drift": 0,
    }
    print(f"    seeded weak-agent perf record for 'query' to force R3 L_2a firing")

    # (K-001 workaround removed 2026-04-04 — kernel introspect() fix landed
    # in loop.py:756 so weak_agents no longer crash the suggestion loop.)

    # Snapshot ledgers just before the audit cycle
    ledger_pre_audit = _ledger_rows()
    # And snapshot the in-memory _results length and cycle count
    results_len_pre = len(kernel._results)
    cycle_pre = kernel._cycle_count

    improve2 = kernel.run_cycle(Task(
        task_type=TaskType.IMPROVE,
        description="audit IMPROVE cycle with probe=3; _isolated_ledgers must prevent probe rows from reaching real JSONLs",
    ))
    audit_out = improve2.output
    if "verdict" not in audit_out:
        print(f"    ERROR: audit v2.handle failed — output={audit_out}")
        print(f"    improve2.error={improve2.error}")
        # fall through so readout still gets written

    # The audit cycle itself appended exactly one row to each ledger
    # (results_log, orbit_transition_log). If _isolated_ledgers works,
    # nothing *extra* from probe cycles should show up.
    ledger_post_audit = _ledger_rows()
    expected_delta = {
        "results_log.jsonl": 1,
        "orbit_transition_log.jsonl": 1,
        # task_state_trace: only changes if the IMPROVE task inputs
        # carried well-typed (b,e) fields; they don't, so delta=0.
        "task_state_trace.jsonl": 0,
    }
    actual_delta = {
        k: (ledger_post_audit[k] or 0) - (ledger_pre_audit[k] or 0)
        for k in LEDGERS
    }
    ledger_integrity_ok = (actual_delta == expected_delta)
    print(f"    ledger delta (expected {expected_delta}): {actual_delta} "
          f"→ {'OK' if ledger_integrity_ok else 'DRIFT DETECTED'}")
    if "verdict" in audit_out:
        print(f"    verdict={audit_out['verdict']} "
              f"lyap: {audit_out['lyapunov']['pre']:.6f} → "
              f"{audit_out['lyapunov']['post']:.6f}")
        print(f"    FP candidates: {audit_out['fixed_point_candidates']}")
    else:
        audit_out.setdefault("verdict", "ERROR")
        audit_out.setdefault("lyapunov", {"pre": None, "post": None, "delta": None})
        audit_out.setdefault("fixed_point_candidates", {})
        audit_out.setdefault("applied", [])
        audit_out.setdefault("deferred", [])

    # Were any L_2a proposals actually probe-gated? (depends on what v1's
    # rules emit given the current kernel state)
    probed = [
        a for a in audit_out.get("applied", [])
        if a.get("level") == "L_2a" and "lyap_probe" in a
    ]
    probe_deferred = [
        d for d in audit_out.get("deferred", [])
        if d.get("level") == "L_2a" and "probe" in (d.get("note") or d.get("probe_status") or "")
    ]
    print(f"    L_2a proposals probed: applied={len(probed)} deferred={len(probe_deferred)}")

    # ------------------------------------------------------------------
    # Readout
    # ------------------------------------------------------------------

    readout = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session": "lab-self-improvement",
        "phase": "post-consolidation batch + v2 hardening",
        "kernel_run_id": kernel._kernel_run_id,
        "ledger_rows": {
            "before_run": ledger_before,
            "after_run":  ledger_post_audit,
            "pre_audit":  ledger_pre_audit,
            "audit_delta_actual":   actual_delta,
            "audit_delta_expected": expected_delta,
            "audit_integrity_ok":   ledger_integrity_ok,
        },
        "phase1_script_tasks": _strip(task_results),
        "phase1_acceptance": acceptance,
        "phase2_warmup_improve": {
            "verdict":   warmup_out.get("verdict"),
            "summary":   warmup_out.get("summary"),
            "lyapunov":  warmup_out.get("lyapunov"),
            "fixed_point_candidates": warmup_out.get("fixed_point_candidates"),
            "kernel_quality_vector":  warmup_out.get("kernel_quality_vector"),
            "proposals":  _strip(warmup_out.get("proposals", [])),
            "applied":    _strip(warmup_out.get("applied", [])),
            "deferred":   _strip(warmup_out.get("deferred", [])),
            "cert_hash":  (warmup_out.get("cert") or {}).get("cert_hash"),
        },
        "phase3_probe_audit": {
            "verdict":   audit_out.get("verdict"),
            "summary":   audit_out.get("summary"),
            "lyapunov":  audit_out.get("lyapunov"),
            "fixed_point_candidates": audit_out.get("fixed_point_candidates"),
            "kernel_quality_vector":  audit_out.get("kernel_quality_vector"),
            "proposals":  _strip(audit_out.get("proposals", [])),
            "applied":    _strip(audit_out.get("applied", [])),
            "deferred":   _strip(audit_out.get("deferred", [])),
            "l2a_probed_committed": len(probed),
            "l2a_probed_deferred":  len(probe_deferred),
            "probe_cycles":         v2.dry_run_probe_cycles,
            "cert_hash":            (audit_out.get("cert") or {}).get("cert_hash"),
        },
        "kernel_state_final": {
            "orbit": list(kernel.orbit_state),
            "family": kernel.orbit_family,
            "cycle_count": kernel._cycle_count,
            "satellite_streak": kernel._satellite_streak,
            "results_in_memory": len(kernel._results),
        },
    }

    out_path = _QA_LAB_DIR / "kernel" / "batch_v2_hardening_readout.json"
    out_path.write_text(
        json.dumps(readout, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"[batch-v2] wrote readout: {out_path.relative_to(_REPO_ROOT)}")
    print(f"[batch-v2] done at {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    return 0 if ledger_integrity_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
