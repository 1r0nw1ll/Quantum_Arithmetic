#!/usr/bin/env python3
"""
run_lab_status.py

Comprehensive QA Lab status run. Exercises every registered agent type in
one heterogeneous kernel batch, runs a terminal IMPROVE cycle over the
full runtime history, and dumps a dashboard JSON + readable summary.

Covers:
  1. QueryAgent        — orbit query on (3,6) mod 9
  2. TheoremAgent      — orbit claim verification
  3. ExperimentAgent   — qa_raman_effect demo (exit 0, QA tuple analysis)
  4. CertAgent         — validates one of the [122] batch certs
  5. SynthesisAgent    — reads recent traces, proposes next tasks
  6. SelfImprovementAgentV2 — terminal IMPROVE over full 5-cycle history

StemAgent is intentionally NOT exercised here: its initial (0,0) state
predates the 2026-04-05 A1 refactor and isn't compatible with the
A1-compliant {1..m} _families dict without a separate base-class fix
(filed as a future follow-up).

Writes:
  qa_lab/kernel/lab_status_readout.json

Run:
    cd /home/player2/signal_experiments
    python qa_lab/run_lab_status.py
"""
from __future__ import annotations

QA_COMPLIANCE = "qa_lab_status_runner — exercises every agent type in one heterogeneous batch; all measurements (rho, ρ-EWMA, FP candidates, verdict distributions) are observer-layer per Theorem NT; kernel b/e stay integer under A1 post-K-002"

import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO = _QA_LAB_DIR.parent
if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from kernel.loop import QALabKernel, Task, TaskType
from agents.cert_agent import CertAgent
from agents.experiment_agent import ExperimentAgent
from agents.query_agent import QueryAgent
from agents.theorem_agent import TheoremAgent
from agents.synthesis_agent import SynthesisAgent
from agents.self_improvement_agent_v2 import SelfImprovementAgentV2

LEDGERS = [
    "results_log.jsonl",
    "orbit_transition_log.jsonl",
    "task_state_trace.jsonl",
]


def _ledger_rows() -> Dict[str, int]:
    out = {}
    for name in LEDGERS:
        p = _QA_LAB_DIR / "kernel" / name
        out[name] = sum(1 for _ in p.open("r", encoding="utf-8")) if p.exists() else 0
    return out


def _git_state() -> Dict[str, Any]:
    try:
        last = subprocess.check_output(
            ["git", "-C", str(_REPO), "log", "-1", "--format=%H %ai %s"],
            text=True,
        ).strip()
        short = subprocess.check_output(
            ["git", "-C", str(_REPO), "status", "--short"], text=True,
        ).strip().splitlines()
        untracked = [l for l in short if l.startswith("?? ")]
        modified = [l for l in short if l.startswith(" M ") or l.startswith("M ")]
        return {
            "last_commit": last,
            "untracked_count": len(untracked),
            "modified_count": len(modified),
            "total_dirty": len(short),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _cert_batch_state() -> Dict[str, Any]:
    results = _REPO / "qa_alphageometry_ptolemy/qa_empirical_observation_cert/results"
    if not results.exists():
        return {"error": "results dir missing"}
    files = sorted(p.name for p in results.glob("*.json"))
    # Classify by verdict by reading each
    verdicts: Dict[str, int] = {}
    for p in results.glob("*.json"):
        try:
            c = json.loads(p.read_text())
            v = c.get("verdict", "?")
            verdicts[v] = verdicts.get(v, 0) + 1
        except Exception:
            verdicts["PARSE_ERROR"] = verdicts.get("PARSE_ERROR", 0) + 1
    return {"n_results": len(files), "verdict_distribution": verdicts, "files": files}


def main() -> int:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"[lab-status] start {ts}")
    ledger_before = _ledger_rows()

    kernel = QALabKernel(
        repo_root=_REPO, modulus=9, verbose=False,
        dry_run=False, require_spawn_approval=True,
    )
    query_a = QueryAgent(modulus=9)
    theorem_a = TheoremAgent(modulus=9)
    exp_a = ExperimentAgent(repo_root=_REPO, timeout=60)
    cert_a = CertAgent(repo_root=_REPO)
    syn_a = SynthesisAgent(repo_root=_REPO)
    v2 = SelfImprovementAgentV2(
        modulus=9,
        lyapunov="rho_ewma",
        lyapunov_alpha=0.2,
        dry_run_probe_cycles=0,
    )

    kernel.register_agent(TaskType.QUERY, query_a)
    kernel.register_agent(TaskType.THEOREM, theorem_a)
    kernel.register_agent(TaskType.EXPERIMENT, exp_a)
    kernel.register_agent(TaskType.CERTIFY, cert_a)
    kernel.register_agent(TaskType.SYNTHESIZE, syn_a)
    kernel.register_agent(TaskType.IMPROVE, v2)

    # Pick one of the batch certs to validate
    cert_to_run = _REPO / "qa_alphageometry_ptolemy/qa_empirical_observation_cert/results/eoc_pass_audio_residual_control_consistent.json"
    validator_rel = "qa_alphageometry_ptolemy/qa_empirical_observation_cert/qa_empirical_observation_cert_validate.py"

    cycles_plan: List[Dict[str, Any]] = [
        {
            "label": "01 QUERY orbit (3,6) mod 9",
            "task": Task(
                task_type=TaskType.QUERY,
                description="orbit classification of (3,6) mod 9",
                inputs={"query_type": "orbit", "b": 3, "e": 6, "m": 9},
            ),
        },
        {
            "label": "02 THEOREM orbit claim (1,2) → cosmos",
            "task": Task(
                task_type=TaskType.THEOREM,
                description="claim: (1,2) mod 9 is in the cosmos orbit family",
                inputs={
                    "claim_type": "orbit",
                    "orbit_query": {"type": "classify", "b": 1, "e": 2, "m": 9,
                                    "expected": "cosmos"},
                },
            ),
        },
        {
            "label": "03 EXPERIMENT qa_raman_effect demo",
            "task": Task(
                task_type=TaskType.EXPERIMENT,
                description="raman Stokes/Anti-Stokes QA tuple analysis (demo)",
                inputs={
                    "script_path": "qa_lab/qa_raman_effect.py",
                    "args": [],
                    # F5 auto-PYTHONPATH handles the qa_lab package import
                },
            ),
        },
        {
            "label": "04 CERTIFY [122] audio_residual_control",
            "task": Task(
                task_type=TaskType.CERTIFY,
                description="validate audio residual control cert artifact",
                inputs={
                    "validator_path": validator_rel,
                    "cert_path": str(cert_to_run),
                    "family_name": "qa_empirical_observation_cert",
                },
            ),
        },
        {
            "label": "05 SYNTHESIZE next-task proposals",
            "task": Task(
                task_type=TaskType.SYNTHESIZE,
                description="propose next tasks from recent ledger context",
                inputs={"max_tasks": 3},
            ),
        },
    ]

    per_cycle: List[Dict[str, Any]] = []
    for plan in cycles_plan:
        label = plan["label"]
        t = plan["task"]
        print(f"[lab-status] {label}")
        r = kernel.run_cycle(t)
        out = r.output or {}
        verdict = out.get("verdict") or ("OK" if r.ok else "FAIL")
        per_cycle.append({
            "label": label,
            "task_type": t.task_type.value,
            "verdict": verdict,
            "ok": r.ok,
            "verified": r.verified,
            "rho": r.rho,
            "orbit_family": r.orbit_family,
            "error": r.error,
            "short_out": {k: v for k, v in out.items() if k in (
                "verdict", "ok", "summary", "answer", "family", "orbit_length",
                "proposal_count", "claim", "exit_code"
            )},
        })
        print(f"    verdict={verdict} ok={r.ok} family={r.orbit_family} rho={r.rho:.4f}")

    # Terminal IMPROVE cycle
    print(f"[lab-status] 06 IMPROVE terminal — v2 over full runtime history")
    improve = kernel.run_cycle(Task(
        task_type=TaskType.IMPROVE,
        description="lab status terminal IMPROVE cycle over 5-cycle heterogeneous history",
    ))
    io = improve.output
    if "verdict" in io:
        lyap = io["lyapunov"]
        fp = io["fixed_point_candidates"]
        print(f"    verdict={io['verdict']}")
        print(f"    lyap={lyap['name']}: {lyap['pre']:.6f} → {lyap['post']:.6f}")
        print(f"    FP A={fp['A_trace_compression']:.4f} B={fp['B_routing_barycenter']:.4f} C={fp['C_pisano_periodicity']:.4f}")
        print(f"    all_lyap={fp['all_lyapunovs']}")
    else:
        print(f"    ERROR: {io}")

    # Dashboard
    ledger_after = _ledger_rows()
    perf = kernel.agent_performance()
    dashboard = {
        "timestamp": ts,
        "session": "cert-batch-empirical (lab status pass)",
        "kernel_run_id": kernel._kernel_run_id,
        "kernel_state_final": {
            "orbit": list(kernel.orbit_state),
            "family": kernel.orbit_family,
            "cycles_this_run": kernel._cycle_count,
            "satellite_streak": kernel._satellite_streak,
            "results_in_memory": len(kernel._results),
        },
        "heterogeneous_cycles": per_cycle,
        "terminal_improve": {
            "verdict": io.get("verdict"),
            "summary": io.get("summary"),
            "lyapunov": io.get("lyapunov"),
            "fixed_point_candidates": io.get("fixed_point_candidates"),
            "kernel_quality_vector": io.get("kernel_quality_vector"),
            "cert_hash": (io.get("cert") or {}).get("cert_hash"),
            "proposals_count": len(io.get("proposals", [])),
            "applied_count": len(io.get("applied", [])),
            "deferred_count": len(io.get("deferred", [])),
        },
        "agent_performance_this_run": perf,
        "ledger_rows": {
            "before": ledger_before,
            "after": ledger_after,
            "delta": {k: ledger_after[k] - ledger_before[k] for k in LEDGERS},
        },
        "cert_batch_state": _cert_batch_state(),
        "git_state": _git_state(),
    }

    out_path = _QA_LAB_DIR / "kernel" / "lab_status_readout.json"
    out_path.write_text(json.dumps(dashboard, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print()
    print(f"[lab-status] wrote {out_path.relative_to(_REPO)}")
    print(f"[lab-status] done {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
