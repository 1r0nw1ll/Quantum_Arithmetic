"""
qa_lab.agents.self_improvement_agent
=====================================
SelfImprovementAgent — handles TaskType.IMPROVE.

## Role in the Levin Architecture

SelfImprovementAgent is the lab's *immune system + growth regulator*:
  - Reads kernel introspection report + recent failures + Open Brain context
  - Generates ranked improvement proposals (deterministic rule engine)
  - Applies GOVERNED actions directly (no arbitrary code rewriting)
  - Returns proposals for human/operator review for higher-risk actions

## Governed Action Types (v1)

  ADJUST_THRESHOLD   — modify a kernel numeric parameter (safe, reversible)
  DEDIFFERENTIATE    — signal a specific agent to reset to stem state
  SPAWN_IMPROVED     — add an improved spawn spec to kernel spawn_queue
  PROMOTE_STEM       — assign a specific task_type to an undifferentiated StemAgent
  LOG_ONLY           — record observation, no structural change

## Decision Rules (deterministic priority order)

  Rule 1 — SINGULARITY STUCK: kernel orbit = singularity for ≥2 cycles
            → ADJUST metamorphosis_threshold=1 (force immediate reset)

  Rule 2 — SATELLITE LOOP: satellite_streak > 0.5 * metamorphosis_threshold
            → ADJUST metamorphosis_threshold -= 1 (accelerate recovery)

  Rule 3 — WEAK AGENT: agent success_rate < 0.4 AND total > 3
            → SPAWN_IMPROVED for that agent type

  Rule 4 — ORBIT DRIFT: agent orbit_drift_count > 2
            → DEDIFFERENTIATE that agent (too much looping → stem reset)

  Rule 5 — UNHANDLED CAPABILITY: spawn_queue has pending entry
            → PROMOTE_STEM if a StemAgent is undifferentiated

  Rule 6 — OB INSIGHT: ob_context contains a specific keyword trigger
            → LOG_ONLY (surface for operator) or SPAWN_IMPROVED based on topic

  Rule 7 — HEALTHY: no issues detected
            → LOG_ONLY "lab health is good"

## Orbit Signature

SelfImprovementAgent runs in COSMOS orbit — it is a convergent, differentiated
agent. Its goal is to move other agents toward cosmos. It must not itself drift
to satellite (rule engine is deterministic, O(N) in n_agents, always terminates).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_AGENTS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _AGENTS_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from agents.base import QAAgent


# Keywords in OB context that trigger specific improvement proposals
_OB_KEYWORDS = {
    "singularity_exit":   "finance_singularity_exit",
    "vasicek":            "finance_mean_reversion",
    "sornette":           "finance_sornette_crash",
    "eeg":                "eeg_scale_up",
    "metamorphosis":      "levin_metamorphosis",
    "satellite loop":     "satellite_damping",
    "stem cell":          "stem_promotion",
    "competency spec":    "cert_family_123",
    "organ":              "organ_protocol",
    "self-improvement":   "self_improvement_loop",
}


class SelfImprovementAgent(QAAgent):
    """Deterministic rule engine for kernel self-improvement.

    Reads introspect + failures + OB context → generates ranked proposals.
    Applies governed actions directly; returns rest for operator review.
    """

    capabilities = ["improve"]
    cert_family  = None  # no cert family yet — will become [123] or similar

    def __init__(self, modulus: int = 9):
        super().__init__(
            name="self_improvement_agent",
            modulus=modulus,
            initial_b=1,
            initial_e=1,  # start in cosmos
        )
        self._improvement_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        inputs = task.inputs if hasattr(task, "inputs") else {}
        description = getattr(task, "description", "") or ""

        # Gather inputs
        introspect     = inputs.get("introspect") or {}
        recent_results = inputs.get("recent_results") or []
        orbit_context  = inputs.get("orbit_context") or {}
        spawn_queue    = inputs.get("spawn_queue") or []
        ob_context     = inputs.get("ob_context") or inputs.get("context") or ""
        kernel_ref     = inputs.get("kernel_ref")  # live kernel handle (optional)

        # Generate proposals
        proposals = self._generate_proposals(
            introspect, recent_results, orbit_context, spawn_queue, ob_context
        )

        # Apply governed actions
        applied, deferred = self._apply_governed(proposals, kernel_ref)

        # Build summary
        n_applied  = len(applied)
        n_deferred = len(deferred)
        health     = introspect.get("health", "unknown")
        orbit_fam  = introspect.get("kernel_family", "unknown")

        summary = (
            f"Self-improvement cycle: health={health} orbit={orbit_fam} "
            f"proposals={len(proposals)} applied={n_applied} deferred={n_deferred}"
        )

        # Certify
        evidence = [
            {"type": "introspect_snapshot", "data": {
                "health": health,
                "orbit": orbit_fam,
                "weak_agents": introspect.get("weak_agents", []),
                "cycles": introspect.get("cycles", 0),
            }},
            {"type": "proposals", "data": [_safe_proposal(p) for p in proposals]},
            {"type": "applied_actions", "data": applied},
            {"type": "ob_context_length", "data": len(ob_context)},
        ]

        verdict = "CONSISTENT" if proposals else "INCONCLUSIVE"
        if any(p.get("action") in ("SINGULARITY_STUCK", "ORBIT_DRIFT") for p in proposals):
            verdict = "PARTIAL"  # structural issues detected — flag clearly

        cert = self.certify(
            observation_body=summary,
            verdict=verdict,
            evidence=evidence,
            observation_source="self_improvement_agent",
        )

        # Record history
        record = {"summary": summary, "proposals": len(proposals), "applied": n_applied}
        self._improvement_history.append(record)

        return {
            "ok": True,
            "verdict": verdict,
            "summary": summary,
            "proposals": proposals,
            "applied": applied,
            "deferred": deferred,
            "health": health,
            "cert": cert,
        }

    # ------------------------------------------------------------------
    # Rule engine
    # ------------------------------------------------------------------

    def _generate_proposals(
        self,
        introspect: Dict[str, Any],
        recent_results: List[Dict[str, Any]],
        orbit_context: Dict[str, Any],
        spawn_queue: List[Dict[str, Any]],
        ob_context: str,
    ) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []

        kernel_family   = introspect.get("kernel_family", "unknown")
        cycles          = introspect.get("cycles", 0)
        agent_perf      = introspect.get("agent_performance", {})
        weak_agents     = introspect.get("weak_agents", [])
        suggestions     = introspect.get("improvement_suggestions", [])
        sat_streak      = orbit_context.get("satellite_streak", 0)
        meta_threshold  = orbit_context.get("metamorphosis_threshold", 5)

        # Rule 1: SINGULARITY STUCK
        if kernel_family == "singularity" and cycles >= 2:
            proposals.append({
                "action": "ADJUST_THRESHOLD",
                "target": "metamorphosis_threshold",
                "new_value": 1,
                "old_value": meta_threshold,
                "reason": "kernel stuck in singularity — force immediate metamorphosis reset",
                "priority": 1.0,
                "rule": "R1_SINGULARITY_STUCK",
            })

        # Rule 2: SATELLITE STREAK — approaching threshold
        if sat_streak > 0 and meta_threshold > 0:
            sat_fraction = sat_streak / meta_threshold
            if sat_fraction > 0.5:
                new_threshold = max(1, meta_threshold - 1)
                proposals.append({
                    "action": "ADJUST_THRESHOLD",
                    "target": "metamorphosis_threshold",
                    "new_value": new_threshold,
                    "old_value": meta_threshold,
                    "reason": f"satellite streak {sat_streak}/{meta_threshold} > 50% — accelerate metamorphosis",
                    "priority": 0.8,
                    "rule": "R2_SATELLITE_LOOP",
                })

        # Rule 3: WEAK AGENT — failure rate too high
        for agent_name in weak_agents:
            perf = agent_perf.get(agent_name, {})
            total = perf.get("total", 0)
            sr    = perf.get("success_rate", 0.0)
            if total > 3 and sr < 0.4:
                proposals.append({
                    "action": "SPAWN_IMPROVED",
                    "target": agent_name,
                    "current_success_rate": sr,
                    "required_min_rate": 0.6,
                    "reason": f"agent {agent_name} success_rate={sr:.2f} < 0.4 over {total} tasks",
                    "spawn_spec_hint": {
                        "required_capability": agent_name,
                        "minimum_success_rate": 0.6,
                        "improvement_note": f"Current agent fails {total - int(sr*total)}/{total} tasks",
                    },
                    "priority": 0.9,
                    "rule": "R3_WEAK_AGENT",
                })

        # Rule 4: ORBIT DRIFT — agent cycling excessively
        for agent_name, perf in agent_perf.items():
            drift = perf.get("orbit_drift_count", 0)
            if drift > 2:
                proposals.append({
                    "action": "DEDIFFERENTIATE",
                    "target": agent_name,
                    "drift_count": drift,
                    "reason": f"agent {agent_name} orbit_drift={drift} — dedifferentiate and respecify",
                    "priority": 0.85,
                    "rule": "R4_ORBIT_DRIFT",
                })

        # Rule 5: UNHANDLED CAPABILITY — stem agent available
        pending_spawns = [s for s in spawn_queue if not s.get("approved", True)]
        if pending_spawns:
            for spec in pending_spawns[:2]:  # limit to 2 at a time
                capability = spec.get("required_capability", "unknown")
                proposals.append({
                    "action": "PROMOTE_STEM",
                    "target": "stem_agent",
                    "capability": capability,
                    "spawn_spec": spec,
                    "reason": f"unhandled capability '{capability}' — promote stem agent to trial",
                    "priority": 0.7,
                    "rule": "R5_UNHANDLED_CAPABILITY",
                })

        # Rule 6: OB INSIGHT — keywords in context
        if ob_context:
            ob_lower = ob_context.lower()
            for keyword, topic in _OB_KEYWORDS.items():
                if keyword in ob_lower:
                    proposals.append({
                        "action": "LOG_ONLY",
                        "target": topic,
                        "reason": f"Open Brain context contains insight about: {topic}",
                        "ob_keyword": keyword,
                        "priority": 0.5,
                        "rule": "R6_OB_INSIGHT",
                        "operator_note": (
                            f"OB context references '{keyword}' → topic={topic}. "
                            f"Consider spawning {topic} agent or running related experiment."
                        ),
                    })

        # Rule 7: HEALTHY — no issues
        if not proposals:
            proposals.append({
                "action": "LOG_ONLY",
                "target": "kernel",
                "reason": "no structural issues detected",
                "priority": 0.1,
                "rule": "R7_HEALTHY",
                "operator_note": "Lab health is good. Suggest: advance science experiments or ship papers.",
            })

        # Sort by priority descending
        proposals.sort(key=lambda p: p.get("priority", 0.0), reverse=True)
        return proposals

    # ------------------------------------------------------------------
    # Governed action application
    # ------------------------------------------------------------------

    def _apply_governed(
        self,
        proposals: List[Dict[str, Any]],
        kernel_ref: Optional[Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Apply safe, reversible governed actions. Defer rest for operator.

        Governed (applied directly):
          ADJUST_THRESHOLD — modify kernel numeric parameter (safe)
          LOG_ONLY         — no change, just record

        Deferred (operator decision required):
          SPAWN_IMPROVED   — requires operator approval
          DEDIFFERENTIATE  — requires operator approval (agent state change)
          PROMOTE_STEM     — requires operator confirmation
        """
        applied  = []
        deferred = []

        for prop in proposals:
            action = prop.get("action")

            if action == "LOG_ONLY":
                applied.append({**prop, "applied": True, "note": "logged"})

            elif action == "ADJUST_THRESHOLD" and kernel_ref is not None:
                target    = prop.get("target")
                new_value = prop.get("new_value")
                if target and new_value is not None and hasattr(kernel_ref, target):
                    old_value = getattr(kernel_ref, target)
                    setattr(kernel_ref, target, new_value)
                    applied.append({
                        **prop,
                        "applied": True,
                        "old_value": old_value,
                        "note": f"kernel.{target} changed {old_value} → {new_value}",
                    })
                else:
                    deferred.append({**prop, "applied": False, "note": "no kernel_ref or unknown attribute"})

            elif action == "ADJUST_THRESHOLD" and kernel_ref is None:
                deferred.append({**prop, "applied": False, "note": "no kernel_ref — cannot apply"})

            else:
                # SPAWN_IMPROVED, DEDIFFERENTIATE, PROMOTE_STEM → operator decision
                deferred.append({**prop, "applied": False, "note": "requires operator approval"})

        return applied, deferred

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        s = super().status()
        s["improvement_cycles"] = len(self._improvement_history)
        s["last_improvement"] = self._improvement_history[-1] if self._improvement_history else None
        return s


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_proposal(p: Dict[str, Any]) -> Dict[str, Any]:
    """Strip non-serializable fields for cert evidence."""
    skip = {"spawn_spec", "spawn_spec_hint"}
    return {k: v for k, v in p.items() if k not in skip}
