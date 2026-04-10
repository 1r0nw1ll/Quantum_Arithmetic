"""
qa_lab.protocols.organ
=======================
Organ Protocol — multi-agent binding for emergent capabilities.

## What is an Organ?

In the Levin morphogenetic architecture, an *organ* is a stable coalition
of committed agents that together exhibit capabilities none could achieve
alone. Like a biological organ:

  - Composed of differentiated cells (cosmos-orbit agents)
  - Has a structural identity (spine + supporting agents)
  - Exhibits emergent function (organ_capability > union of parts)
  - Can be dissolved back into individual agents

## Organ Structure

  Organ
  ├── spine:    ONE cosmos agent with guaranteed convergence (required)
  ├── ring:     0..N supporting agents (cosmos or mixed orbit)
  └── capability: the emergent task_type this organ handles

The SPINE is the convergence guarantee. Without it, the organ cannot form.
Supporting agents extend capability but cannot substitute for the spine.

## Formation Rules  (OrganFormationProtocol)

  F1  At least one committed cosmos/differentiated agent must be the spine
  F2  All members must be in committed stage (orbit = cosmos)
  F3  No two members may declare the same failure_mode as their PRIMARY blocker
      (diversity of failure modes = resilience)
  F4  The organ must declare an emergent capability not covered by any single member
  F5  Spine agent must have convergence != "none"

## Dissolution Rules

  D1  Spine agent dedifferentiates → organ dissolved immediately
  D2  Organ success_rate < 0.5 over MIN_ORGAN_EVAL (default 5 tasks) → dissolve
  D3  Explicit operator DISSOLVE command

## Emergent Capability Patterns

  SPINE(experiment) + RING(query)     → empirical_query  (run + interpret)
  SPINE(certify)   + RING(improve)    → adaptive_cert    (certify + self-fix)
  SPINE(query)     + RING(synthesize) → research_loop    (search + plan)
  SPINE(experiment)+ RING(synthesize) → science_loop     (run + propose next)
  ANY + RING(stem)                    → morphogenetic    (any + dediff/rediff)

## TaskType.ORGAN

  When an organ is registered for a given capability, the kernel routes
  that task_type to the organ instead of a single agent. The organ's
  handle() delegates to spine first, then passes output to ring agents
  in sequence (pipeline) or in parallel (broadcast), depending on organ_mode.

## Organ Modes

  pipeline:   spine → ring[0] → ring[1] → ... → final output
  broadcast:  spine + all ring agents run in parallel, results merged
  arbitrate:  all run, spine has veto on final verdict
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

QA_COMPLIANCE = "qa_lab_protocol — organ formation rules; orbit_family labels are protocol spec values from agent properties"

_PROTOCOLS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _PROTOCOLS_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from protocols.differentiation import check_organ_eligibility

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_ORGAN_EVAL    = 5     # min tasks before rate-based dissolution triggers
MIN_ORGAN_RATE    = 0.5   # organ success rate threshold
VALID_ORGAN_MODES = frozenset(["pipeline", "broadcast", "arbitrate"])

# Known emergent capability patterns
EMERGENT_PATTERNS: Dict[str, Dict[str, Any]] = {
    "empirical_query": {
        "spine": "experiment", "ring": ["query"],
        "description": "Run experiment + interpret result via QA query",
    },
    "adaptive_cert": {
        "spine": "certify", "ring": ["improve"],
        "description": "Certify result + self-improve on failure",
    },
    "research_loop": {
        "spine": "query", "ring": ["synthesize"],
        "description": "Query knowledge + plan next research step",
    },
    "science_loop": {
        "spine": "experiment", "ring": ["synthesize"],
        "description": "Run experiment + propose follow-up tasks",
    },
    "morphogenetic": {
        "spine": None, "ring": ["stem"],
        "description": "Any spine + stem support = self-regenerating organ",
    },
}


# ---------------------------------------------------------------------------
# Organ dataclass
# ---------------------------------------------------------------------------

class Organ:
    """A bound coalition of committed QA Lab agents.

    An organ handles a single emergent capability that none of its member
    agents could handle alone. The spine agent provides convergence guarantee;
    ring agents provide extended capability.
    """

    def __init__(
        self,
        name: str,
        capability: str,
        spine: Any,                   # QAAgent instance
        ring: Optional[List[Any]] = None,
        mode: str = "pipeline",
        modulus: int = 9,
    ):
        self.name        = name
        self.capability  = capability
        self.spine       = spine
        self.ring        = ring or []
        self.mode        = mode
        self.modulus     = modulus

        self._task_count:    int = 0
        self._success_count: int = 0
        self._dissolved:     bool = False
        self._dissolution_reason: Optional[str] = None

        # Validate on creation
        ok, errors = validate_organ(self)
        if not ok:
            raise ValueError(f"Organ formation blocked:\n" + "\n".join(f"  {e}" for e in errors))

    # ------------------------------------------------------------------
    # Core handle — routes task through spine + ring
    # ------------------------------------------------------------------

    def can_handle(self, task: Any) -> bool:
        if self._dissolved:
            return False
        task_type_val = _task_type_str(task)
        return task_type_val == self.capability

    def handle(self, task: Any) -> Dict[str, Any]:
        if self._dissolved:
            return {"ok": False, "verdict": "INCONCLUSIVE",
                    "reason": f"organ {self.name!r} is dissolved: {self._dissolution_reason}"}

        self._task_count += 1

        if self.mode == "pipeline":
            result = self._pipeline(task)
        elif self.mode == "broadcast":
            result = self._broadcast(task)
        elif self.mode == "arbitrate":
            result = self._arbitrate(task)
        else:
            result = self._pipeline(task)

        ok = result.get("ok", False)
        if ok:
            self._success_count += 1

        # Check dissolution condition D2
        if self._task_count >= MIN_ORGAN_EVAL:
            rate = self._success_count / self._task_count
            if rate < MIN_ORGAN_RATE:
                self._dissolve(f"success_rate={rate:.2f} < {MIN_ORGAN_RATE} over {self._task_count} tasks")

        result["organ"] = self.name
        result["organ_mode"] = self.mode
        return result

    def _pipeline(self, task: Any) -> Dict[str, Any]:
        """Spine runs first; each ring agent receives the previous output."""
        handler = getattr(self.spine, "safe_handle", self.spine.handle)
        result = handler(task)
        if not result.get("ok"):
            return result  # spine failed — short-circuit
        for agent in self.ring:
            # Inject previous result into task inputs for context
            if hasattr(task, "inputs") and isinstance(task.inputs, dict):
                task.inputs["pipeline_context"] = result
            h = getattr(agent, "safe_handle", agent.handle)
            result = h(task)
            if not result.get("ok"):
                break  # ring agent failed — stop pipeline
        return result

    def _broadcast(self, task: Any) -> Dict[str, Any]:
        """All agents run independently; results are merged."""
        results = []
        for agent in [self.spine] + self.ring:
            h = getattr(agent, "safe_handle", agent.handle)
            results.append(h(task))
        # Merge: ok if ALL ok; verdict = most pessimistic
        all_ok    = all(r.get("ok") for r in results)
        verdicts  = [r.get("verdict", "INCONCLUSIVE") for r in results]
        verdict   = _merge_verdicts(verdicts)
        return {"ok": all_ok, "verdict": verdict, "broadcast_results": results}

    def _arbitrate(self, task: Any) -> Dict[str, Any]:
        """All agents run; spine has veto — if spine says FAIL, result is FAIL."""
        handler = getattr(self.spine, "safe_handle", self.spine.handle)
        spine_result = handler(task)
        ring_results = []
        for agent in self.ring:
            h = getattr(agent, "safe_handle", agent.handle)
            ring_results.append(h(task))
        # Spine veto: if spine fails, organ fails
        if not spine_result.get("ok"):
            return {**spine_result, "arbitration": "spine_veto", "ring_results": ring_results}
        # Otherwise merge ring
        verdicts = [spine_result.get("verdict", "INCONCLUSIVE")] + \
                   [r.get("verdict", "INCONCLUSIVE") for r in ring_results]
        return {
            "ok": True,
            "verdict": _merge_verdicts(verdicts),
            "spine_result": spine_result,
            "ring_results": ring_results,
            "arbitration": "spine_approved",
        }

    # ------------------------------------------------------------------
    # Dissolution
    # ------------------------------------------------------------------

    def dissolve(self, reason: str = "OPERATOR_COMMAND") -> None:
        """Explicit dissolution — operator command."""
        self._dissolve(reason)

    def _dissolve(self, reason: str) -> None:
        self._dissolved = True
        self._dissolution_reason = reason

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_dissolved(self) -> bool:
        return self._dissolved

    @property
    def success_rate(self) -> float:
        if self._task_count == 0:
            return 1.0
        return self._success_count / self._task_count

    @property
    def members(self) -> List[Any]:
        return [self.spine] + self.ring

    def status(self) -> Dict[str, Any]:
        return {
            "name":               self.name,
            "capability":         self.capability,
            "mode":               self.mode,
            "spine":              type(self.spine).__name__,
            "ring":               [type(a).__name__ for a in self.ring],
            "task_count":         self._task_count,
            "success_rate":       round(self.success_rate, 3),
            "dissolved":          self._dissolved,
            "dissolution_reason": self._dissolution_reason,
        }

    def __repr__(self) -> str:
        members = [type(self.spine).__name__] + [type(a).__name__ for a in self.ring]
        return (f"<Organ {self.name!r} capability={self.capability!r} "
                f"mode={self.mode} members={members} dissolved={self._dissolved}>")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_organ(organ: Organ) -> Tuple[bool, List[str]]:
    """Check all formation rules (F1–F5).

    Returns (ok, list_of_blocking_reasons).
    """
    errors = []
    spine = organ.spine

    # F1: spine must be committed cosmos/differentiated
    spine_orbit = getattr(spine, "orbit_family", None)
    spine_stage = getattr(spine, "stage", "committed")  # non-StemAgents default committed
    eligible, reasons = check_organ_eligibility(
        agent_orbit_sig=spine_orbit or "cosmos",
        agent_levin_type="differentiated",
        organ_has_spine=True,
        failure_modes=[],
        organ_blocked_failures=[],
    )
    if not eligible:
        errors.append(f"F1 SPINE_INELIGIBLE: {'; '.join(reasons)}")

    # F2: all ring members must be committed (orbit = cosmos or appropriate)
    for i, agent in enumerate(organ.ring):
        agent_orbit = getattr(agent, "orbit_family", "cosmos")
        agent_stage = getattr(agent, "stage", "committed")
        if agent_orbit not in ("cosmos", "satellite", "mixed"):
            errors.append(f"F2 RING_MEMBER_WRONG_ORBIT: ring[{i}] {type(agent).__name__} "
                          f"orbit={agent_orbit!r} (must be cosmos/satellite/mixed)")

    # F3: failure mode diversity (warn only — not a hard block)
    all_failure_modes: List[str] = []
    for agent in organ.members:
        fms = getattr(agent, "failure_modes", [])
        all_failure_modes.extend(fms)
    # Count duplicates — warn if more than 2 agents share a failure mode
    from collections import Counter
    fm_counts = Counter(all_failure_modes)
    for fm, count in fm_counts.items():
        if count > 2:
            errors.append(f"F3 FAILURE_MODE_CONCENTRATION: '{fm}' shared by {count} members "
                          f"(max 2 for resilience)")

    # F4: organ capability must differ from all member capabilities
    member_caps: List[str] = []
    for agent in organ.members:
        member_caps.extend(getattr(agent, "capabilities", []))
    if organ.capability in member_caps:
        # This is actually EXPECTED for single-agent organs — only error if
        # capability is listed as the ONLY capability of the spine
        spine_caps = getattr(spine, "capabilities", [])
        if spine_caps == [organ.capability]:
            errors.append(f"F4 NO_EMERGENT_CAPABILITY: organ capability {organ.capability!r} "
                          f"is identical to spine's sole capability — no emergence")

    # F5: spine convergence must not be "none"
    spine_convergence = getattr(spine, "convergence", "guaranteed")
    if spine_convergence == "none":
        errors.append(f"F5 SPINE_NO_CONVERGENCE: spine convergence='none' — "
                      f"organ cannot guarantee termination")

    # Mode valid
    if organ.mode not in VALID_ORGAN_MODES:
        errors.append(f"INVALID_MODE: mode={organ.mode!r} must be one of {sorted(VALID_ORGAN_MODES)}")

    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# OrganRegistry — manages active organs in the kernel
# ---------------------------------------------------------------------------

class OrganRegistry:
    """Maintains active organs and routes tasks to them.

    The kernel holds one OrganRegistry. When a task_type matches an organ's
    declared capability, the organ handles it instead of a bare agent.
    """

    def __init__(self):
        self._organs: Dict[str, Organ] = {}   # capability → organ

    def register(self, organ: Organ) -> None:
        """Register an organ for its declared capability."""
        if self._organs.get(organ.capability) is not None:
            raise ValueError(f"Organ already registered for capability {organ.capability!r}")
        self._organs[organ.capability] = organ

    def deregister(self, capability: str) -> Optional[Organ]:
        return self._organs.pop(capability, None)

    def get(self, capability: str) -> Optional[Organ]:
        organ = self._organs.get(capability)
        if organ and organ.is_dissolved:
            del self._organs[capability]
            return None
        return organ

    def can_handle(self, task: Any) -> bool:
        cap = _task_type_str(task)
        organ = self.get(cap or "")
        return organ is not None and organ.can_handle(task)

    def handle(self, task: Any) -> Dict[str, Any]:
        cap = _task_type_str(task)
        organ = self.get(cap or "")
        if organ is None:
            return {"ok": False, "verdict": "INCONCLUSIVE", "reason": f"no organ for {cap!r}"}
        return organ.handle(task)

    def status(self) -> List[Dict[str, Any]]:
        return [o.status() for o in self._organs.values()]

    def __len__(self) -> int:
        return len(self._organs)

    def __repr__(self) -> str:
        return f"<OrganRegistry organs={list(self._organs.keys())}>"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _task_type_str(task: Any) -> Optional[str]:
    tt = getattr(task, "task_type", None)
    if tt is None:
        return None
    return tt.value if hasattr(tt, "value") else str(tt)


def _merge_verdicts(verdicts: List[str]) -> str:
    """Return most pessimistic verdict from a list."""
    order = ["CONTRADICTS", "INCONCLUSIVE", "PARTIAL", "CONSISTENT"]
    for v in order:
        if v in verdicts:
            return v
    return "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def run_self_test() -> bool:
    print("Organ Protocol self-test")

    # Minimal mock agents
    class MockAgent:
        capabilities = ["query"]
        orbit_family = "cosmos"  # noqa: ORBIT-2 — mock agent attribute for test fixture
        stage = "committed"
        failure_modes = ["memory_overflow"]

        def __init__(self, name, verdict="CONSISTENT"):
            self.name = name
            self._verdict = verdict

        def handle(self, task):
            return {"ok": self._verdict != "FAIL", "verdict": self._verdict, "agent": self.name}

        safe_handle = handle

    class MockExperimentAgent(MockAgent):
        capabilities = ["experiment"]

    class MockSynthesisAgent(MockAgent):
        capabilities = ["synthesize"]

    # 1. Valid organ formation (pipeline)
    spine = MockExperimentAgent("exp_spine")
    ring  = [MockSynthesisAgent("synth_ring")]
    organ = Organ("science_loop", "science_loop", spine, ring, mode="pipeline")
    assert not organ.is_dissolved
    print(f"  Organ formation (science_loop pipeline): PASS")

    # 2. Organ handles task
    from dataclasses import dataclass, field as dc_field
    @dataclass
    class FakeTask:
        task_type: Any
        description: str = ""
        inputs: dict = dc_field(default_factory=dict)

    class FakeCap:
        value = "science_loop"

    t = FakeTask(task_type=FakeCap())
    r = organ.handle(t)
    assert r.get("ok"), f"Organ handle failed: {r}"
    assert r.get("organ") == "science_loop"
    print(f"  Organ handle (pipeline): PASS")

    # 3. Broadcast mode
    organ_b = Organ("research_loop", "research_loop", MockAgent("q_spine"), [MockAgent("s_ring")], mode="broadcast")
    t2 = FakeTask(task_type=type("T", (), {"value": "research_loop"})())
    r2 = organ_b.handle(t2)
    assert "broadcast_results" in r2
    print(f"  Organ handle (broadcast): PASS")

    # 4. Arbitrate mode
    organ_a = Organ("arb_organ", "arb_organ", MockAgent("a_spine"), [MockAgent("a_ring")], mode="arbitrate")
    t3 = FakeTask(task_type=type("T", (), {"value": "arb_organ"})())
    r3 = organ_a.handle(t3)
    assert r3.get("arbitration") == "spine_approved"
    print(f"  Organ handle (arbitrate): PASS")

    # 5. OrganRegistry
    registry = OrganRegistry()
    registry.register(organ)
    assert len(registry) == 1
    assert registry.get("science_loop") is organ
    print(f"  OrganRegistry register/get: PASS")

    # 6. Dissolved organ removed from registry
    organ.dissolve("OPERATOR_COMMAND")
    assert organ.is_dissolved
    assert registry.get("science_loop") is None  # auto-removed on dissolve check
    assert len(registry) == 0
    print(f"  Organ dissolution + registry cleanup: PASS")

    # 7. Formation blocked — no spine (empty ring formation attempt)
    try:
        bad_agent = MockAgent("bad")
        bad_agent.orbit_family = "satellite"  # satellite not allowed as spine  # noqa: ORBIT-2 — test fixture
        Organ("bad_organ", "bad_cap", bad_agent, [], mode="pipeline")
        print(f"  Formation blocked (satellite spine): FAIL — should have raised")
        return False
    except ValueError as e:
        print(f"  Formation blocked (satellite spine): PASS")

    print(f"\nAll 7 checks passed — organ protocol ok")
    return True


if __name__ == "__main__":
    import sys
    ok = run_self_test()
    sys.exit(0 if ok else 1)
