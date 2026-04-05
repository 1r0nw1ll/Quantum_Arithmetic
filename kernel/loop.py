"""
qa_lab.kernel.loop
==================
The QA Lab Von Neumann Kernel — the self-replicating core loop.

Architecture
------------
Six operations execute in sequence for every task cycle:

  SENSE    → Read environment state (task queue, knowledge graph, recent results)
  REASON   → Classify task in QA orbit space; check reachability; select agent
  ACT      → Execute via selected agent; produce certified output
  VERIFY   → Validate output through cert ecosystem (meta-validator or cert check)
  LEARN    → Capture result to Open Brain; update knowledge state
  REPLICATE → If task required a missing capability, produce new agent spec

Von Neumann property: if no agent can handle a task, the kernel spawns a
spec for a new agent rather than failing silently. New agents are defined as
cert families and onboarded through the standard Gate 0-5 protocol.

Usage
-----
    from qa_lab.kernel import QALabKernel, Task, TaskType

    kernel = QALabKernel(
        repo_root="/path/to/signal_experiments",
        modulus=9,
        verbose=True,
    )
    task = Task(task_type=TaskType.CERTIFY, description="validate audio orbit cert",
                inputs={"cert_path": "qa_alphageometry_ptolemy/qa_empirical_observation_cert/..."})
    result = kernel.run_cycle(task)
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import uuid

QA_COMPLIANCE = "qa_lab_kernel — orbit state tracks kernel position; orbit_family is a class property, not a canonical orbit call"
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# qa_core is in the parent directory of kernel
_KERNEL_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _KERNEL_DIR.parent
_REPO_ROOT = _QA_LAB_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from qa_core import (
    classify_state, orbit_family_score, is_reachable,
    orbit_contraction_factor, kappa, precompute_all_families,
    canonical_json, domain_sha256,
)


# ---------------------------------------------------------------------------
# Task and Result types
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    CERTIFY         = "certify"         # validate a cert artifact
    EXPERIMENT      = "experiment"      # run an experiment script
    THEOREM         = "theorem"         # prove/check a theorem claim
    SPAWN           = "spawn"           # design a new micro-agent (cert family)
    QUERY           = "query"           # query the knowledge graph / Open Brain
    SYNTHESIZE      = "synthesize"      # read results, propose next tasks
    IMPROVE         = "improve"         # self-improvement: analyse weakness, propose/apply fix
    STEM            = "stem"            # stem cell status query
    DEDIFFERENTIATE = "dedifferentiate" # Levin: reset agent(s) to singularity (totipotent)
    ORGAN           = "organ"           # multi-agent organ task (routed via OrganRegistry)


@dataclass
class Task:
    """A unit of work for the QA Lab kernel."""
    task_type: TaskType
    description: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    priority: float = 1.0  # higher = more urgent


@dataclass
class KernelResult:
    """Output of one kernel cycle."""
    task_id: str
    task_type: TaskType
    ok: bool
    output: Dict[str, Any]
    orbit_family: str          # agent's orbit family during this cycle
    rho: float                 # orbit contraction factor (convergence rate)
    verified: bool             # passed VERIFY step
    learned: bool              # successfully captured to knowledge base
    spawn_required: bool       # did REPLICATE trigger a new agent spec?
    spawn_spec: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# The Kernel
# ---------------------------------------------------------------------------

class QALabKernel:
    """
    QA Lab Von Neumann Kernel.

    State: the kernel itself has a QA orbit position (b, e) that advances
    one Q-step per cycle. This means the kernel's own cognitive state is
    orbit-tracked — it can detect if it's stuck (satellite), productive
    (cosmos), or converged (singularity).
    """

    def __init__(
        self,
        repo_root: Optional[str | Path] = None,
        modulus: int = 9,
        lr: float = 0.1,
        verbose: bool = True,
        # Operator controls
        dry_run: bool = False,
        require_spawn_approval: bool = True,
        max_cycles: Optional[int] = None,
        max_agents: int = 20,
        # Levin metamorphosis
        metamorphosis_threshold: int = 5,
    ):
        self.repo_root = Path(repo_root) if repo_root else _REPO_ROOT
        self.modulus = modulus
        self.lr = lr
        self.verbose = verbose

        # Operator safety controls
        self.dry_run = dry_run
        self.require_spawn_approval = require_spawn_approval
        self.max_cycles = max_cycles
        self.max_agents = max_agents
        self._cycle_count = 0
        self._kernel_run_id = (
            datetime.datetime.now(datetime.timezone.utc).strftime("kernel-%Y%m%dT%H%M%SZ")
            + "-"
            + str(uuid.uuid4())[:8]
        )

        # Kernel's own QA orbit state — starts at (1, 1) in cosmos
        self._b: int = 1
        self._e: int = 1
        self._families = precompute_all_families(modulus)

        # Knowledge base: in-process list of KernelResult records
        self._results: List[KernelResult] = []

        # Registered agents: {task_type: agent_instance}
        self._agents: Dict[TaskType, Any] = {}

        # Spawn queue: agent specs awaiting implementation
        self._spawn_queue: List[Dict[str, Any]] = []

        # Organ registry: multi-agent composite handlers
        from protocols.organ import OrganRegistry
        self.organs = OrganRegistry()

        # Self-improvement: per-agent performance counters
        # {task_type.value: {"ok": int, "fail": int, "verdicts": Counter}}
        self._agent_perf: Dict[str, Any] = {}

        # Levin metamorphosis: track consecutive satellite cycles
        self._satellite_streak: int = 0
        self.metamorphosis_threshold: int = metamorphosis_threshold

        if verbose:
            family = self._families[(self._b % modulus, self._e % modulus)]
            flags = []
            if dry_run: flags.append("DRY_RUN")
            if require_spawn_approval: flags.append("SPAWN_APPROVAL_ON")
            if max_cycles: flags.append(f"MAX_CYCLES={max_cycles}")
            flag_str = "  ".join(flags)
            print(f"[QALabKernel] init  modulus={modulus}  orbit=({self._b},{self._e})  family={family}  {flag_str}")

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(self, task_type: TaskType, agent: Any) -> None:
        """Register an agent to handle a given task type."""
        self._agents[task_type] = agent
        if self.verbose:
            print(f"[QALabKernel] registered agent for {task_type.value}: {type(agent).__name__}")

    def register_organ(self, organ: Any) -> None:
        """Register a multi-agent organ for its declared emergent capability."""
        self.organs.register(organ)
        if self.verbose:
            members = [type(organ.spine).__name__] + [type(a).__name__ for a in organ.ring]
            print(f"[QALabKernel] registered organ {organ.name!r} capability={organ.capability!r} "
                  f"mode={organ.mode} members={members}")

    # ------------------------------------------------------------------
    # SENSE
    # ------------------------------------------------------------------

    def _sense(self, task: Task) -> Dict[str, Any]:
        """Read environment: task, current orbit state, available agents."""
        family = self._families[(self._b, self._e)]
        score = orbit_family_score(family)
        rho = orbit_contraction_factor(self._b, self._e, self.modulus, self.lr)
        k = kappa(self._b, self._e, self.modulus, self.lr)

        env = {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "kernel_orbit": (self._b, self._e),
            "kernel_family": family,
            "kernel_orbit_score": score,
            "kernel_rho": rho,
            "kernel_kappa": k,
            "agent_available": (task.task_type in self._agents
                                or self.organs.can_handle(task)),
            "organ_available": self.organs.can_handle(task),
            "known_results_count": len(self._results),
        }
        if self.verbose:
            print(f"  [SENSE]  task={task.task_type.value}  family={family}  agent={'yes' if env['agent_available'] else 'NO'}")
        return env

    # ------------------------------------------------------------------
    # REASON
    # ------------------------------------------------------------------

    def _reason(self, task: Task, env: Dict[str, Any]) -> Dict[str, Any]:
        """Classify task; determine if reachable; select agent or flag spawn."""
        family = env["kernel_family"]

        # Singularity check: kernel stuck → warn
        if family == "singularity":
            print(f"  [REASON] WARNING: kernel in singularity orbit — may be stuck")

        # Satellite check: kernel looping → mild warning
        if family == "satellite":
            print(f"  [REASON] WARNING: kernel in satellite orbit — limited reachability")

        # Prefer organ over bare agent if both available
        use_organ = env.get("organ_available", False)
        plan = {
            "can_handle": env["agent_available"],
            "selected_agent": self._agents.get(task.task_type),
            "use_organ": use_organ,
            "spawn_needed": not env["agent_available"],
            "orbit_family": family,
            "rho": env["kernel_rho"],
        }

        if self.verbose:
            status = "delegating" if plan["can_handle"] else "SPAWN NEEDED"
            print(f"  [REASON] {status}  orbit_family={family}  rho={plan['rho']:.4f}")

        return plan

    # ------------------------------------------------------------------
    # ACT
    # ------------------------------------------------------------------

    def _act(self, task: Task, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task via selected agent; produce certified output."""
        if not plan["can_handle"]:
            # No agent — produce a minimal spawn spec as output
            spawn_spec = self._make_spawn_spec(task)
            if self.verbose:
                print(f"  [ACT]    no agent — produced spawn spec for {task.task_type.value}")
            return {"ok": False, "spawn_spec": spawn_spec, "reason": "no_agent"}

        # Organ takes priority over bare agent
        if plan.get("use_organ"):
            try:
                output = self.organs.handle(task)
                if self.verbose:
                    print(f"  [ACT]    organ={output.get('organ','?')}  ok={output.get('ok',False)}")
                return output
            except Exception as exc:
                if self.verbose:
                    print(f"  [ACT]    ORGAN ERROR: {exc} — falling back to bare agent")

        agent = plan["selected_agent"]
        try:
            # Inject Open Brain / operator context + introspection into SYNTHESIZE tasks
            if task.task_type == TaskType.SYNTHESIZE:
                injected = self._get_injected_context()
                # Always append kernel self-improvement report
                intro = self._format_introspect_for_context()
                combined = "\n\n".join(filter(None, [injected, intro]))
                if combined and not task.inputs.get("context"):
                    task.inputs["context"] = combined
                elif combined:
                    task.inputs["context"] = combined + "\n\n" + task.inputs["context"]

            # Auto-enrich IMPROVE tasks with kernel introspect + orbit + spawn state
            if task.task_type == TaskType.IMPROVE:
                if not task.inputs.get("introspect"):
                    task.inputs["introspect"] = self.introspect()
                if not task.inputs.get("orbit_context"):
                    task.inputs["orbit_context"] = {
                        "satellite_streak": self._satellite_streak,
                        "metamorphosis_threshold": self.metamorphosis_threshold,
                        "kernel_family": self.orbit_family,
                    }
                if not task.inputs.get("spawn_queue"):
                    task.inputs["spawn_queue"] = list(self._spawn_queue)
                if not task.inputs.get("ob_context"):
                    task.inputs["ob_context"] = self._get_injected_context()
                if "kernel_ref" not in task.inputs:
                    task.inputs["kernel_ref"] = self

            # Use safe_handle for orbit tracking; fall back to handle
            handler = getattr(agent, "safe_handle", agent.handle)
            output = handler(task)
            if self.verbose:
                ok = output.get("ok", False)
                print(f"  [ACT]    agent={type(agent).__name__}  ok={ok}")
            return output
        except Exception as exc:
            if self.verbose:
                print(f"  [ACT]    ERROR: {exc}")
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # VERIFY
    # ------------------------------------------------------------------

    def _verify(self, task: Task, output: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify output against cert ecosystem where applicable.

        For CERTIFY tasks: run the cert's own validator via --self-test.
        For other tasks: check output["ok"] flag.
        Returns (verified: bool, gate_reached: str).
        """
        if not output.get("ok", False):
            return False, "ACT_FAILED"

        if task.task_type == TaskType.CERTIFY:
            validator_path = output.get("validator_path")
            if validator_path:
                result = self._run_validator(validator_path)
                if self.verbose:
                    print(f"  [VERIFY] validator={'PASS' if result else 'FAIL'}  path={validator_path}")
                return result, "GATE_5" if result else "GATE_0"

        verified = output.get("ok", False)
        if self.verbose:
            print(f"  [VERIFY] ok={verified}")
        return verified, "PASS" if verified else "FAIL"

    def _run_validator(self, validator_path: str | Path) -> bool:
        """Run a cert validator with --self-test; return True iff exit 0."""
        vp = Path(validator_path)
        if not vp.is_absolute():
            vp = self.repo_root / vp
        if not vp.exists():
            return False
        try:
            proc = subprocess.run(
                [sys.executable, str(vp), "--self-test"],
                capture_output=True, text=True, timeout=30,
                cwd=str(self.repo_root),
            )
            return proc.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # LEARN
    # ------------------------------------------------------------------

    def _learn(self, task: Task, output: Dict[str, Any], verified: bool) -> bool:
        """Capture result to the in-kernel knowledge store.

        In production, this will also call mcp__open-brain__capture_thought.
        For MVP: appends to self._results and writes a JSON log entry.
        """
        _orbit = (self._b, self._e)
        record = {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "description": task.description,
            "ok": output.get("ok", False),
            "verified": verified,
            "orbit_family": self._families.get(_orbit, "unknown"),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "kernel_orbit": list(_orbit),
        }

        # Self-improvement: update per-agent performance counters
        tt = task.task_type.value
        if tt not in self._agent_perf:
            self._agent_perf[tt] = {"ok": 0, "fail": 0, "verdicts": {}, "orbit_drift": 0}
        perf = self._agent_perf[tt]
        if output.get("ok"):
            perf["ok"] += 1
        else:
            perf["fail"] += 1
        verdict = output.get("verdict", "UNKNOWN")
        perf["verdicts"][verdict] = perf["verdicts"].get(verdict, 0) + 1
        # Detect satellite drift (looping) — self-correction signal
        current_family = self._families.get((self._b, self._e), "unknown")
        if current_family == "satellite":
            perf["orbit_drift"] += 1
        record["agent_perf_snapshot"] = {k: v for k, v in perf.items() if k != "verdicts"}

        # Append to results log
        log_path = self.repo_root / "qa_lab" / "kernel" / "results_log.jsonl"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(canonical_json(record) + "\n")
            if self.verbose:
                print(f"  [LEARN]  logged to {log_path.name}")
            return True
        except Exception as exc:
            if self.verbose:
                print(f"  [LEARN]  WARNING: could not write log: {exc}")
            return False

    def _extract_task_state_refs(self, task: Task, output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract explicit task-semantic (b,e) states from task inputs and outputs.

        This intentionally stays narrow: only well-typed QA state fields are logged.
        No floats, no heuristic reduction, no inferred coordinates from prose.
        """

        def _state_from_be_keys(mapping: Any, b_key: str = "b", e_key: str = "e") -> Optional[Tuple[int, int]]:
            if not isinstance(mapping, dict):
                return None
            b_val = mapping.get(b_key)
            e_val = mapping.get(e_key)
            if isinstance(b_val, int) and isinstance(e_val, int):
                return (b_val, e_val)
            return None

        def _state_from_pair(value: Any) -> Optional[Tuple[int, int]]:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                first, second = value
                if isinstance(first, int) and isinstance(second, int):
                    return (first, second)
            return None

        refs: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, int, int]] = set()

        def _add(source: str, path: str, state: Optional[Tuple[int, int]]) -> None:
            if state is None:
                return
            b_val, e_val = state
            key = (source, path, b_val, e_val)
            if key in seen:
                return
            seen.add(key)
            refs.append({
                "source": source,
                "path": path,
                "state": [b_val, e_val],
            })

        inputs = task.inputs if hasattr(task, "inputs") and isinstance(task.inputs, dict) else {}
        _add("task.inputs", "b,e", _state_from_be_keys(inputs))
        _add("task.inputs", "b2,e2", _state_from_be_keys(inputs, "b2", "e2"))

        orbit_query = inputs.get("orbit_query")
        if isinstance(orbit_query, dict):
            _add("task.inputs", "orbit_query.state", _state_from_be_keys(orbit_query))

        bfs_query = inputs.get("bfs_query")
        if isinstance(bfs_query, dict):
            _add("task.inputs", "bfs_query.start", _state_from_pair(bfs_query.get("start")))
            _add("task.inputs", "bfs_query.target", _state_from_pair(bfs_query.get("target")))

        objective = inputs.get("objective")
        if isinstance(objective, dict):
            _add("task.inputs", "objective.target_state", _state_from_be_keys(objective.get("target_state")))

        run_block = inputs.get("run")
        if isinstance(run_block, dict):
            _add("task.inputs", "run.start_state", _state_from_be_keys(run_block.get("start_state")))

        _add("output", "state", _state_from_pair(output.get("state")))
        _add("output", "start", _state_from_pair(output.get("start")))
        _add("output", "target", _state_from_pair(output.get("target")))
        _add("output", "before", _state_from_pair(output.get("before")))
        _add("output", "after", _state_from_pair(output.get("after")))
        _add("output", "tuple_seed", _state_from_pair(output.get("tuple")))
        _add("output", "cycle_state", _state_from_be_keys(output.get("cycle_state")))
        _add("output", "witness.state", _state_from_pair(output.get("witness", {}).get("state") if isinstance(output.get("witness"), dict) else None))

        witness = output.get("witness")
        if isinstance(witness, dict):
            _add("output", "witness.start", _state_from_pair(witness.get("start")))
            _add("output", "witness.target", _state_from_pair(witness.get("target")))
            _add("output", "witness.state", _state_from_pair(witness.get("state")))

        return refs

    def _log_transition_traces(
        self,
        task: Task,
        output: Dict[str, Any],
        verified: bool,
        kernel_state_before: Tuple[int, int],
        kernel_state_after: Tuple[int, int],
    ) -> None:
        """Write per-cycle kernel transition rows and task-semantic state rows."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cycle_idx = self._cycle_count
        base = {
            "run_id": self._kernel_run_id,
            "cycle_idx": cycle_idx,
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "description": task.description,
            "timestamp": timestamp,
            "ok": output.get("ok", False),
            "verified": verified,
        }

        kernel_row = {
            **base,
            "move": "qa_step",
            "state_before": list(kernel_state_before),
            "state_after": list(kernel_state_after),
            "orbit_family_before": self._families.get(kernel_state_before, "unknown"),
            "orbit_family_after": self._families.get(kernel_state_after, "unknown"),
        }

        kernel_trace_path = self.repo_root / "qa_lab" / "kernel" / "orbit_transition_log.jsonl"
        try:
            with open(kernel_trace_path, "a", encoding="utf-8") as handle:
                handle.write(canonical_json(kernel_row) + "\n")
        except Exception as exc:
            if self.verbose:
                print(f"  [TRACE]  WARNING: could not write kernel transition log: {exc}")

        state_refs = self._extract_task_state_refs(task, output)
        if not state_refs:
            return

        task_trace_path = self.repo_root / "qa_lab" / "kernel" / "task_state_trace.jsonl"
        try:
            with open(task_trace_path, "a", encoding="utf-8") as handle:
                for ref_idx, ref in enumerate(state_refs):
                    row = {
                        **base,
                        "ref_idx": ref_idx,
                        "source": ref["source"],
                        "path": ref["path"],
                        "state": ref["state"],
                    }
                    handle.write(canonical_json(row) + "\n")
        except Exception as exc:
            if self.verbose:
                print(f"  [TRACE]  WARNING: could not write task state trace log: {exc}")

    # ------------------------------------------------------------------
    # REPLICATE
    # ------------------------------------------------------------------

    def _replicate(self, task: Task, plan: Dict[str, Any], output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """If a new capability is needed, produce an agent spawn spec.

        The spawn spec is a structured JSON that Codex can use to implement
        a new cert family + validator, turning it into a working micro-agent.
        """
        if not plan.get("spawn_needed"):
            return None

        # Operator approval gate
        if self.require_spawn_approval:
            if self.verbose:
                print(f"  [REPLICATE] spawn requires operator approval (require_spawn_approval=True)")
                print(f"              Set kernel.require_spawn_approval=False to auto-approve.")
            # Still produce the spec but mark it unapproved
            spawn_spec = output.get("spawn_spec") or self._make_spawn_spec(task)
            spawn_spec["approved"] = False
            spawn_spec["pending_approval"] = True
        else:
            spawn_spec = output.get("spawn_spec") or self._make_spawn_spec(task)
            spawn_spec["approved"] = True
        self._spawn_queue.append(spawn_spec)

        # Write spec to file so it persists across sessions
        spawn_dir = self.repo_root / "qa_lab" / "kernel" / "spawn_queue"
        spawn_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spawn_dir / f"spawn_{task.task_id}.json"
        try:
            spec_path.write_text(canonical_json(spawn_spec), encoding="utf-8")
            if self.verbose:
                print(f"  [REPLICATE] spawn spec written: {spec_path.name}")
        except Exception as exc:
            if self.verbose:
                print(f"  [REPLICATE] WARNING: could not write spawn spec: {exc}")

        return spawn_spec

    def _make_spawn_spec(self, task: Task) -> Dict[str, Any]:
        """Produce a minimal agent spawn spec from a task that had no handler."""
        return {
            "schema": "QA_AGENT_SPAWN_SPEC.v1",
            "task_id": task.task_id,
            "required_capability": task.task_type.value,
            "description": task.description,
            "inputs_example": task.inputs,
            "cert_family_name": f"qa_{task.task_type.value}_agent",
            "validator_checks": [
                "V1: input schema valid",
                "V2: output is certifiable artifact",
                "V3: --self-test exits 0",
            ],
            "gate_compliance": [0, 1, 2, 3, 4, 5],
            "spawn_timestamp": datetime.datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Kernel orbit advancement
    # ------------------------------------------------------------------

    def _advance_orbit(self) -> None:
        """Advance kernel's own QA state by one Q-step."""
        from qa_core import qa_step
        self._b, self._e = qa_step(self._b, self._e, self.modulus)

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------

    def run_cycle(self, task: Task) -> KernelResult:
        """Execute one full SENSE→REASON→ACT→VERIFY→LEARN→REPLICATE cycle."""
        # Operator limit check
        if self.max_cycles is not None and self._cycle_count >= self.max_cycles:
            raise RuntimeError(f"[QALabKernel] max_cycles={self.max_cycles} reached. Operator must reset.")
        self._cycle_count += 1

        # Dry-run: propagate to agents if they support it
        if self.dry_run:
            for agent in self._agents.values():
                if hasattr(agent, "dry_run"):
                    agent.dry_run = True

        if self.verbose:
            print(f"\n[QALabKernel] cycle  task_id={task.task_id}  type={task.task_type.value}")
            print(f"  desc: {task.description[:80]}")

        kernel_state_before = self.orbit_state
        family = self._families[(self._b, self._e)]
        rho = orbit_contraction_factor(self._b, self._e, self.modulus, self.lr)

        # Six steps
        env    = self._sense(task)
        plan   = self._reason(task, env)
        output = self._act(task, plan)
        verified, gate = self._verify(task, output)
        learned = self._learn(task, output, verified)
        spawn_spec = self._replicate(task, plan, output)

        # Advance kernel's own orbit
        self._advance_orbit()
        kernel_state_after = self.orbit_state
        self._log_transition_traces(task, output, verified, kernel_state_before, kernel_state_after)

        # Levin metamorphosis detection
        self._check_metamorphosis(family)

        result = KernelResult(
            task_id=task.task_id,
            task_type=task.task_type,
            ok=output.get("ok", False),
            output=output,
            orbit_family=family,
            rho=rho,
            verified=verified,
            learned=learned,
            spawn_required=plan.get("spawn_needed", False),
            spawn_spec=spawn_spec,
            error=output.get("error"),
        )
        self._results.append(result)

        if self.verbose:
            print(f"  [RESULT] ok={result.ok}  verified={result.verified}  orbit={family}  spawn={result.spawn_required}")

        return result

    def run_batch(self, tasks: List[Task]) -> List[KernelResult]:
        """Run multiple tasks sequentially, returning all results."""
        return [self.run_cycle(t) for t in tasks]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def orbit_state(self) -> Tuple[int, int]:
        return (self._b, self._e)

    @property
    def orbit_family(self) -> str:
        return self._families[self.orbit_state]

    @property
    def spawn_queue(self) -> List[Dict[str, Any]]:
        return list(self._spawn_queue)

    def status(self) -> Dict[str, Any]:
        return {
            "modulus": self.modulus,
            "orbit_state": self.orbit_state,
            "orbit_family": self.orbit_family,
            "cycles_completed": len(self._results),
            "registered_agents": [k.value for k in self._agents],
            "spawn_queue_depth": len(self._spawn_queue),
            "spawn_pending": sum(1 for s in self._spawn_queue if not s.get("approved", True)),
        }

    def agent_performance(self) -> Dict[str, Any]:
        """Return per-agent performance metrics for self-improvement analysis."""
        out = {}
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

    def introspect(self) -> Dict[str, Any]:
        """Self-improvement introspection: analyse performance + propose improvements.

        Returns a structured report that SynthesisAgent can use to generate
        self-improvement tasks for the next cycle.
        """
        perf = self.agent_performance()
        weak_agents = [tt for tt, p in perf.items() if p["needs_improvement"]]
        orbit = self.orbit_family

        suggestions = []
        for tt in weak_agents:
            p = perf[tt]
            # K-001 fix (2026-04-04): read success_rate from the formatted
            # view instead of p["fail"] / p["ok"], which don't exist in the
            # output of agent_performance() — those keys live only in the
            # raw self._agent_perf counter dict.  success_rate < 0.5 is
            # equivalent to fail > ok since success_rate = ok / (ok+fail).
            suggestions.append({
                "agent": tt,
                "issue": "high failure rate" if p["success_rate"] < 0.5 else "satellite drift",
                "action": f"review {tt} agent handler — consider spawning improved version",
                "priority": 0.9,
            })
        if orbit == "satellite":
            suggestions.append({
                "agent": "kernel",
                "issue": "kernel orbit in satellite (looping detected)",
                "action": "inject high-novelty task to break looping orbit",
                "priority": 1.0,
            })
        if orbit == "singularity":
            suggestions.append({
                "agent": "kernel",
                "issue": "kernel orbit in singularity (stuck)",
                "action": "URGENT: reset kernel orbit or inject cosmos task",
                "priority": 1.0,
            })

        return {
            "kernel_orbit": self.orbit_state,
            "kernel_family": orbit,
            "cycles": self._cycle_count,
            "agent_performance": perf,
            "weak_agents": weak_agents,
            "improvement_suggestions": suggestions,
            "health": "good" if not weak_agents and orbit == "cosmos" else "needs_attention",
        }

    # ------------------------------------------------------------------
    # Levin metamorphosis protocol
    # ------------------------------------------------------------------

    def _check_metamorphosis(self, cycle_family: str) -> Optional[Dict[str, Any]]:
        """Track satellite streak. If threshold exceeded → trigger metamorphosis.

        Metamorphosis = Levin dedifferentiation:
          1. All satellite agents dedifferentiate → singularity
          2. SynthesisAgent generates new QA_AGENT_SPAWN_SPEC.v1
          3. New spec added to spawn_queue for operator approval
        """
        if cycle_family == "satellite":
            self._satellite_streak += 1
        else:
            self._satellite_streak = 0

        if self._satellite_streak >= self.metamorphosis_threshold:
            return self._trigger_metamorphosis()
        return None

    def _trigger_metamorphosis(self) -> Dict[str, Any]:
        """Execute metamorphosis: dedifferentiate satellite agents, request respecification."""
        self._satellite_streak = 0  # reset streak

        if self.verbose:
            print(f"\n[QALabKernel] *** METAMORPHOSIS TRIGGERED *** "
                  f"({self.metamorphosis_threshold} consecutive satellite cycles)")

        dediff_results = []
        for task_type, agent in list(self._agents.items()):
            # Only dedifferentiate agents in satellite or progenitor stage
            agent_orbit = getattr(agent, "orbit_family", None)
            if agent_orbit in ("satellite",) or getattr(agent, "is_progenitor", False):
                dediff_task = Task(
                    task_type=TaskType.DEDIFFERENTIATE,
                    description=f"Metamorphosis: dedifferentiate {type(agent).__name__}",
                )
                if hasattr(agent, "safe_handle"):
                    result = agent.safe_handle(dediff_task)
                    dediff_results.append({"agent": type(agent).__name__, "result": result})
                    if self.verbose:
                        print(f"  [METAMORPHOSIS] dedifferentiated {type(agent).__name__}")

        # Generate respecification request for SynthesisAgent
        meta_spec = {
            "schema": "QA_METAMORPHOSIS_SPEC.v1",
            "trigger": f"{self.metamorphosis_threshold}_satellite_cycles",
            "dedifferentiated_agents": [r["agent"] for r in dediff_results],
            "action_required": "SynthesisAgent should generate new QA_AGENT_SPAWN_SPEC.v1 for each dedifferentiated agent",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._spawn_queue.append(meta_spec)

        # Reset kernel orbit to cosmos seed to break satellite loop
        self._b, self._e = 1, 1

        if self.verbose:
            print(f"  [METAMORPHOSIS] kernel orbit reset to (1,1) cosmos")
            print(f"  [METAMORPHOSIS] respecification request added to spawn_queue")

        return {"metamorphosis": True, "dediff_results": dediff_results, "spec": meta_spec}

    def last_cycles(self, n: int = 5) -> List[Dict[str, Any]]:
        """Return summary of last N kernel cycles."""
        return [
            {
                "cycle": i + 1,
                "task_id": r.task_id,
                "task_type": r.task_type.value,
                "ok": r.ok,
                "verdict": r.output.get("verdict"),
                "orbit_family": r.orbit_family,
                "verified": r.verified,
                "spawn_required": r.spawn_required,
            }
            for i, r in enumerate(self._results[-n:], start=max(0, len(self._results) - n))
        ]

    # ------------------------------------------------------------------
    # Context injection (Open Brain / operator feed)
    # ------------------------------------------------------------------

    def inject_context(self, context: str, source: str = "operator") -> None:
        """Inject external context (e.g. Open Brain thoughts) into next SYNTHESIZE task.

        The injected context is stored and automatically prepended to any
        SYNTHESIZE task's context input if the task doesn't supply its own.
        Call this from the operator console or Claude Code session after
        reading recent Open Brain thoughts.
        """
        self._injected_context = getattr(self, "_injected_context", [])
        self._injected_context.append({"source": source, "text": context})
        if self.verbose:
            print(f"[QALabKernel] context injected ({source}): {len(context)} chars")

    def _get_injected_context(self) -> str:
        """Return and clear injected context for the next SYNTHESIZE cycle."""
        chunks = getattr(self, "_injected_context", [])
        if not chunks:
            return ""
        text = "\n\n".join(f"[{c['source']}] {c['text']}" for c in chunks)
        self._injected_context = []
        return text

    def _format_introspect_for_context(self) -> str:
        """Format kernel introspect() output as a context string for SynthesisAgent."""
        if self._cycle_count < 2:
            return ""  # Not enough history yet
        report = self.introspect()
        parts = [f"[kernel_introspect] health={report['health']}  orbit={report['kernel_family']}  cycles={report['cycles']}"]
        for agent, perf in report["agent_performance"].items():
            parts.append(f"  agent={agent} success_rate={perf['success_rate']} total={perf['total']}"
                         + (" NEEDS_IMPROVEMENT" if perf["needs_improvement"] else ""))
        for s in report["improvement_suggestions"]:
            parts.append(f"  suggest: {s['agent']} — {s['action']}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Bootstrap closure: approve → stub → register → rerun
    # ------------------------------------------------------------------

    def approve_spawn(self, spawn_id: str) -> bool:
        """Operator approval of a pending spawn spec by task_id.

        Returns True if found and approved, False otherwise.
        """
        for spec in self._spawn_queue:
            if spec.get("task_id") == spawn_id:
                spec["approved"] = True
                spec["pending_approval"] = False
                spec["approved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                # Update persisted file
                spawn_dir = self.repo_root / "qa_lab" / "kernel" / "spawn_queue"
                spec_path = spawn_dir / f"spawn_{spawn_id}.json"
                if spec_path.exists():
                    spec_path.write_text(canonical_json(spec), encoding="utf-8")
                if self.verbose:
                    print(f"[QALabKernel] spawn approved: {spawn_id}")
                return True
        if self.verbose:
            print(f"[QALabKernel] spawn not found: {spawn_id}")
        return False

    def create_agent_stub(self, spawn_spec: Dict[str, Any]) -> Path:
        """Generate a minimal agent stub .py from an approved spawn spec.

        Writes to qa_lab/agents/<agent_name>.py.
        Returns the path written.
        """
        import re as _re
        capability = spawn_spec.get("required_capability", "query")
        agent_name = spawn_spec.get("agent_name") or f"{capability}_agent"
        # Sanitise to valid Python identifier
        agent_name = _re.sub(r"[^a-z0-9_]", "_", agent_name.lower())
        class_name = "".join(w.capitalize() for w in agent_name.split("_"))

        agents_dir = str(Path(__file__).resolve().parent.parent / "agents")
        stub = f'''"""
{agent_name} — auto-generated stub from QA_AGENT_SPAWN_SPEC.v1
Generated:    {datetime.datetime.now(datetime.timezone.utc).isoformat()}
Spawn reason: {spawn_spec.get("description", "unhandled task")}
Task ID:      {spawn_spec.get("task_id", "?")}

TODO: implement handle() with real logic.
"""
from __future__ import annotations
import sys as _sys
_AGENTS_DIR = {agents_dir!r}
if _AGENTS_DIR not in _sys.path:
    _sys.path.insert(0, _AGENTS_DIR)
from typing import Any, Dict
from base import QAAgent


class {class_name}(QAAgent):
    """Auto-generated stub for capability: {capability}.

    Capabilities: {capability}
    """

    capabilities = [{capability!r}]
    cert_family = "{agent_name}_cert"

    def __init__(self, modulus: int = 9):
        super().__init__(name="{agent_name}", modulus=modulus)

    def handle(self, task: Any) -> Dict[str, Any]:
        inputs = task.inputs if hasattr(task, "inputs") else {{}}
        # --- STUB: replace with real implementation ---
        result = f"[STUB] {class_name} received: {{inputs}}"
        cert = self.certify(
            observation_body=f"Stub response for: {{getattr(task, \'description\', \'\')}}",
            verdict="PARTIAL",
            evidence=[{{"type": "stub", "inputs": inputs}}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {{
            "ok": True,
            "verdict": "PARTIAL",
            "result": result,
            "stub": True,
            "cert": cert,
        }}
'''
        out_path = Path(__file__).resolve().parent.parent / "agents" / f"{agent_name}.py"
        out_path.write_text(stub, encoding="utf-8")
        if self.verbose:
            print(f"[QALabKernel] agent stub written: {out_path.name}")
        return out_path

    def register_from_stub(self, stub_path: Path, task_type: "TaskType") -> Any:
        """Dynamically load a stub agent and register it with the kernel.

        This closes the bootstrap loop: spawn → stub → register → rerun.
        Returns the instantiated agent.
        """
        import importlib.util
        import re as _re

        spec = importlib.util.spec_from_file_location(stub_path.stem, stub_path)
        mod = importlib.util.module_from_spec(spec)
        # Ensure agents package context for relative imports
        import sys as _sys
        _agents_dir = str(stub_path.parent)
        if _agents_dir not in _sys.path:
            _sys.path.insert(0, _agents_dir)
        spec.loader.exec_module(mod)

        # Find the QAAgent subclass in the module
        from .agents.base import QAAgent as _QAAgent  # noqa: F401 (for isinstance check)
        agent_class = None
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if (isinstance(obj, type) and issubclass(obj, QAAgent)  # type: ignore[name-defined]
                    and obj.__name__ != "QAAgent"):
                agent_class = obj
                break

        if agent_class is None:
            raise ImportError(f"No QAAgent subclass found in {stub_path}")

        agent = agent_class(modulus=self.modulus)
        self.register_agent(task_type, agent)
        if self.verbose:
            print(f"[QALabKernel] bootstrap closure: {agent_class.__name__} registered for {task_type.value}")
        return agent
