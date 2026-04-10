"""
qa_lab.session_start — QA Lab session bootstrap script.

Run at the start of every Claude Code session:

    cd qa_lab && python session_start.py

What it does:
  1. Checks kernel health (orbit, cycle count, spawn queue)
  2. Fetches recent Open Brain context immediately, then loads injected_context.txt
  3. Runs a SYNTHESIZE cycle to produce prioritized task list
  4. Optionally runs a real experiment from the top of the task list
  5. Prints a session brief

Open Brain integration pattern
--------------------------------
The MCP tool (mcp__open-brain__*) is only available inside a Claude Code session.
The operator (Claude) reads recent thoughts and writes them to disk via:

    python console.py inject "<thought text>"

or directly in a Claude session:
    kernel.inject_context(text, source='open_brain')

Then session_start.py picks them up automatically. It now also performs a
fail-fast Open Brain bootstrap by default before the session proceeds.

This file is the glue layer between the Claude session's MCP access and the
Python kernel — the correct architecture for an operator-governed system.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_LAB_DIR.parent
sys.path.insert(0, str(_QA_LAB_DIR))

from kernel.loop import QALabKernel, Task, TaskType
from agents import CertAgent, ExperimentAgent, TheoremAgent, SynthesisAgent
from agents.query_agent import QueryAgent
from agents.stem_agent import StemAgent
from agents.self_improvement_agent import SelfImprovementAgent
from open_brain_bootstrap import OpenBrainBootstrapError, bootstrap_open_brain_context

_CONTEXT_FILE = _QA_LAB_DIR / "kernel" / "injected_context.txt"


def build_kernel(
    dry_run: bool = False,
    max_cycles: int = 50,
    verbose: bool = True,
) -> QALabKernel:
    """Build a fully-equipped kernel with all registered agents."""
    kernel = QALabKernel(
        repo_root=_REPO_ROOT,
        modulus=9,
        verbose=verbose,
        require_spawn_approval=True,
        max_cycles=max_cycles,
        max_agents=20,
    )
    kernel.register_agent(TaskType.CERTIFY,    CertAgent(modulus=9))
    kernel.register_agent(TaskType.EXPERIMENT,  ExperimentAgent(
        repo_root=_REPO_ROOT, modulus=9, dry_run=dry_run, timeout=120,
    ))
    kernel.register_agent(TaskType.THEOREM,     TheoremAgent(modulus=9))
    kernel.register_agent(TaskType.SYNTHESIZE,  SynthesisAgent(modulus=9))
    kernel.register_agent(TaskType.QUERY,       QueryAgent(modulus=9))
    kernel.register_agent(TaskType.IMPROVE,     SelfImprovementAgent(modulus=9))
    # StemAgent handles STEM + DEDIFFERENTIATE
    stem = StemAgent(modulus=9)
    kernel.register_agent(TaskType.STEM,            stem)
    kernel.register_agent(TaskType.DEDIFFERENTIATE, stem)
    return kernel


def load_open_brain_context(kernel: QALabKernel) -> int:
    """Load any Open Brain thoughts that were written to injected_context.txt.

    Returns number of chars injected (0 if nothing new).
    """
    if not _CONTEXT_FILE.exists():
        return 0
    text = _CONTEXT_FILE.read_text(encoding="utf-8").strip()
    if not text:
        return 0
    kernel.inject_context(text, source="open_brain")
    # Clear after loading so we don't re-inject next session
    _CONTEXT_FILE.write_text("", encoding="utf-8")
    return len(text)


def refresh_open_brain_context(
    *,
    require_open_brain: bool = True,
    limit: int = 10,
    since_days: int = 7,
) -> int:
    """Fetch fresh Open Brain context before a session starts.

    Returns the number of chars written into injected_context.txt.
    Raises when Open Brain is required but unavailable.
    """
    try:
        result = bootstrap_open_brain_context(
            limit=limit,
            since_days=since_days,
            write_context=True,
        )
        print(
            f"[session] Open Brain bootstrap OK: limit={limit}, since_days={since_days}, "
            f"chars={result.chars_written}"
        )
        return result.chars_written
    except OpenBrainBootstrapError as exc:
        if require_open_brain:
            raise
        print(f"[session] Open Brain bootstrap bypassed: {exc}")
        return 0


def session_brief(kernel: QALabKernel) -> None:
    """Print a structured session brief from kernel status."""
    st = kernel.status()
    print("\n" + "=" * 60)
    print("QA LAB SESSION BRIEF")
    print("=" * 60)
    print(f"Kernel orbit:    {st['orbit_state']}  family={st['orbit_family']}")
    print(f"Agents:          {', '.join(st['registered_agents'])}")
    print(f"Cycles logged:   {st['cycles_completed']}")
    spawn_p = st.get("spawn_pending", 0)
    if spawn_p:
        print(f"Spawn pending:   {spawn_p} (run: python console.py queue)")
    print("=" * 60)


def run_session(
    dry_run: bool = False,
    run_experiment: bool = True,
    verbose: bool = True,
    require_open_brain: bool = True,
) -> QALabKernel:
    """Full session startup sequence. Returns live kernel."""

    refresh_open_brain_context(require_open_brain=require_open_brain)
    kernel = build_kernel(dry_run=dry_run, verbose=verbose)

    # 1. Load Open Brain context
    ob_chars = load_open_brain_context(kernel)
    if ob_chars:
        print(f"[session] Open Brain context loaded: {ob_chars} chars → ready for SYNTHESIZE")
    else:
        print("[session] No new Open Brain context (use: python console.py inject '<thoughts>')")

    # 2. SYNTHESIZE: propose session priorities
    synth_result = kernel.run_cycle(Task(
        task_type=TaskType.SYNTHESIZE,
        description="Session startup: propose top priorities",
        inputs={"max_tasks": 5},
        priority=1.0,
    ))
    proposals = synth_result.output.get("proposed_tasks", [])
    if proposals:
        print("\n[session] Proposed session tasks (ranked):")
        for i, t in enumerate(proposals, 1):
            pri = t.get("priority", 0) if isinstance(t, dict) else getattr(t, "priority", 0)
            desc = t.get("description", "") if isinstance(t, dict) else getattr(t, "description", "")
            print(f"  [{i}] [{pri:.3f}] {desc[:72]}")

    # 3. Optionally run the highest-priority experiment task
    if run_experiment and proposals:
        top = proposals[0] if isinstance(proposals[0], dict) else proposals[0].__dict__
        if top.get("task_type") == "experiment" and top.get("inputs", {}).get("script_path"):
            print(f"\n[session] Auto-running top experiment: {top['inputs']['script_path']}")
            exp_result = kernel.run_cycle(Task(
                task_type=TaskType.EXPERIMENT,
                description=top.get("description", ""),
                inputs=top.get("inputs", {}),
                priority=top.get("priority", 0.9),
            ))
            verdict = exp_result.output.get("verdict")
            numbers = exp_result.output.get("numbers", {})
            print(f"[session] Experiment result: verdict={verdict}  numbers={numbers}")

    session_brief(kernel)
    return kernel


def run_real_experiment(
    script_path: str,
    description: str,
    success_pattern: str = r"orbit_follow_rate|VERDICT|PASS",
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """Run a single real experiment through the kernel and return the result.

    This is the primary interface for running research scripts with full
    cert generation, verdict classification, and results logging.

    Example:
        result = run_real_experiment(
            script_path="qa_audio_orbit_test.py",
            description="Audio orbit follow rate vs null hypothesis",
        )
    """
    kernel = build_kernel(dry_run=dry_run, verbose=verbose)
    result = kernel.run_cycle(Task(
        task_type=TaskType.EXPERIMENT,
        description=description,
        inputs={
            "script_path": script_path,
            "success_pattern": success_pattern,
            "capture_numbers": True,
        },
        priority=1.0,
    ))
    return {
        "ok": result.ok,
        "verdict": result.output.get("verdict"),
        "numbers": result.output.get("numbers", {}),
        "stdout_tail": result.output.get("stdout", "")[-800:],
        "cert": result.output.get("cert"),
        "orbit_family": result.orbit_family,
    }


def run_improve_cycle(
    dry_run: bool = False,
    verbose: bool = True,
    ob_context: str = "",
) -> dict:
    """Run a self-improvement cycle and return the proposals + applied actions.

    The kernel auto-enriches the IMPROVE task with introspect() data.
    Pass ob_context to include Open Brain findings in the analysis.

    Example:
        result = run_improve_cycle(ob_context="Sornette singularity exit is a priority")
        for p in result['proposals']:
            print(p['action'], p['reason'])
    """
    kernel = build_kernel(dry_run=dry_run, verbose=verbose)
    if ob_context:
        kernel.inject_context(ob_context, source="session_start")
    result = kernel.run_cycle(Task(
        task_type=TaskType.IMPROVE,
        description="Self-improvement cycle",
        inputs={"ob_context": ob_context},
        priority=1.0,
    ))
    return {
        "ok": result.ok,
        "verdict": result.output.get("verdict"),
        "health": result.output.get("health", "unknown"),
        "proposals": result.output.get("proposals", []),
        "applied": result.output.get("applied", []),
        "deferred": result.output.get("deferred", []),
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="QA Lab session startup")
    p.add_argument("--dry-run", action="store_true", help="Don't execute scripts")
    p.add_argument("--no-experiment", action="store_true", help="Skip auto-run of top experiment")
    p.add_argument("--quiet", action="store_true", help="Reduce verbosity")
    p.add_argument(
        "--allow-missing-open-brain",
        action="store_true",
        help="Emergency bypass: continue even if Open Brain bootstrap fails",
    )
    args = p.parse_args()

    run_session(
        dry_run=args.dry_run,
        run_experiment=not args.no_experiment,
        verbose=not args.quiet,
        require_open_brain=not args.allow_missing_open_brain,
    )
