"""
qa_lab.agents.synthesis_agent
==============================
SynthesisAgent-lite — reads Open Brain + cert ecosystem, proposes next tasks.

This agent automates what Claude currently does manually:
  1. Read recent Open Brain thoughts (last N days)
  2. Scan cert family results and knowledge graph
  3. Cluster related findings
  4. Rank proposed next tasks by priority score
  5. Return a task list for the kernel queue

Priority scoring
----------------
Each proposed task gets a score based on:
  - cert_impact    — does it advance a paper or cert family?
  - orbit_score    — what orbit family does the action put the kernel in? (cosmos=1.0)
  - urgency        — is it time-sensitive (paper deadline, broken validator)?
  - novelty        — is it genuinely new vs re-running something we know?

The scoring is orbit-aware: tasks that move the research toward cosmos orbit
(maximum reachability, full exploration) rank higher than tasks that push
into satellite (looping) or singularity (stuck).

Open Brain integration
----------------------
SynthesisAgent reads Open Brain via the MCP tool if available.
Fallback: reads qa_lab/kernel/results_log.jsonl for recent kernel traces.

This is SynthesisAgent-LITE. The full version will:
  - Parse the knowledge graph (qa_knowledge_graph.graphml)
  - Do semantic clustering of Open Brain entries
  - Generate structured task specs conforming to QA_TASK_SPEC.v1
  - Support multi-hop reasoning ("A depends on B which needs C")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_QA_LAB_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _QA_LAB_DIR.parent

import sys as _sys
if str(_QA_LAB_DIR) not in _sys.path:
    _sys.path.insert(0, str(_QA_LAB_DIR))
from protocols.schemas import make_task, VALID_TASK_TYPES

from .base import QAAgent


class SynthesisAgent(QAAgent):
    """Reads recent results and proposes prioritized next tasks.

    Capabilities: synthesize
    """

    capabilities = ["synthesize"]
    cert_family = "qa_synthesis_cert"

    # Static task suggestions keyed by keywords found in recent results
    # Format: (keyword_pattern, task_spec_template, base_priority)
    SYNTHESIS_RULES: List[Tuple[str, Dict[str, Any], float]] = [
        # Audio baseline still open
        (r"orbit_follow_rate|audio.*orbit|autocorrelation.*open",
         {"task_type": "experiment",
          "description": "Run audio autocorrelation baseline (qa_audio_ac_baseline.py) — is orbit_follow_rate QA-specific or just lag-1 AC?",
          "inputs": {"script_path": "qa_audio_ac_baseline.py", "success_pattern": "VERDICT:"},
          "success_criteria": ["VERDICT line printed", "no errors"]},
         0.9),

        # Finance structural argument
        (r"orbit degeneracy|singularity.*momentum|finance.*structural|WHY.*singularity",
         {"task_type": "theorem",
          "description": "Prove: QA singularity condition ≡ dual-momentum extreme threshold (structural argument for finance paper)",
          "inputs": {"claim": "orbit degeneracy (singularity) = simultaneous top-decile momentum", "claim_type": "orbit"},
          "success_criteria": ["formal mapping between singularity condition and momentum threshold"]},
         0.85),

        # EEG full dataset
        (r"CHB-MIT|EEG.*21|full.*patient|HI.*2\.0",
         {"task_type": "experiment",
          "description": "Scale EEG experiment to full CHB-MIT 21-patient suite with HI 2.0",
          "inputs": {"script_path": "eeg_hi2_0_experiment.py", "success_pattern": "accuracy|F1"},
          "success_criteria": ["21-patient results", "balanced accuracy > 0.65"]},
         0.75),

        # Meta-validator green check
        (r"cert|validator|family|meta.?validator",
         {"task_type": "certify",
          "description": "Verify meta-validator stays 128/128 PASS after recent changes",
          "inputs": {"run_meta": True},
          "success_criteria": ["128/128 PASS"]},
         0.95),

        # Batch certify Open Brain results
        (r"open brain|batch.?cert|[122].*cert|observation cert",
         {"task_type": "certify",
          "description": "Batch-certify 10-15 Open Brain empirical results as [122] certs",
          "inputs": {
              "validator_path": "qa_alphageometry_ptolemy/qa_empirical_observation_cert/qa_empirical_observation_cert_validate.py",
          },
          "success_criteria": ["new [122] cert fixtures created"]},
         0.8),

        # Pythagorean families paper shipping
        (r"arxiv|submit|pythagorean|ship.*paper",
         {"task_type": "experiment",
          "description": "Run verify_classification.py to confirm pythagorean-families paper is submission-ready",
          "inputs": {
              "script_path": "qa_alphageometry_ptolemy/qa_congruence_primitive_idempotent_cert_v1/verify_classification.py",
              "success_pattern": r"\d+/\d+",
          },
          "success_criteria": ["10/10 PASS"]},
         0.7),
    ]

    def __init__(
        self,
        repo_root: Optional[str | Path] = None,
        modulus: int = 9,
        max_proposals: int = 5,
        lookback_days: int = 3,
    ):
        super().__init__(name="synthesis_agent", modulus=modulus)
        self.repo_root = Path(repo_root) if repo_root else _REPO_ROOT
        self.max_proposals = max_proposals
        self.lookback_days = lookback_days

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        """Execute a SYNTHESIZE task.

        Optional inputs:
          context       — string of recent observations to synthesize from
          max_tasks     — max number of tasks to propose (default: self.max_proposals)
          focus_area    — filter to a specific domain (audio, finance, eeg, theorem, cert)
        """
        inputs = task.inputs if hasattr(task, "inputs") else {}
        max_tasks = inputs.get("max_tasks", self.max_proposals)
        focus_area = inputs.get("focus_area")

        # 1. Gather recent context
        context = self._gather_context(inputs.get("context"))

        # 2. Read recent kernel traces
        kernel_traces = self._read_kernel_traces()

        # 3. Score and rank candidate tasks
        proposals = self._propose_tasks(context, kernel_traces, focus_area)

        # 4. Trim to max_tasks
        proposals = proposals[:max_tasks]

        # 5. Convert to proper QA_TASK_SPEC.v1 objects
        task_specs = [
            make_task(
                task_type=p["task_type"],
                description=p["description"],
                inputs=p.get("inputs", {}),
                success_criteria=p.get("success_criteria", []),
                priority=p["priority"],
            )
            for p in proposals
        ]

        # 6. Produce a synthesis cert
        cert = self.certify(
            observation_body=f"Synthesized {len(task_specs)} next tasks from recent context",
            verdict="CONSISTENT",
            evidence=[{
                "type": "synthesis",
                "context_length": len(context),
                "kernel_traces_read": len(kernel_traces),
                "proposals": [{"description": p["description"], "priority": p["priority"]}
                               for p in proposals],
            }],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )

        return {
            "ok": True,
            "proposed_tasks": task_specs,
            "proposal_count": len(task_specs),
            "context_summary": context[:300] if context else "",
            "cert": cert,
        }

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------

    def _gather_context(self, provided: Optional[str] = None) -> str:
        """Gather context from provided string + kernel results log."""
        parts = []
        if provided:
            parts.append(provided)

        # Read recent VISION.md priorities
        vision = self.repo_root / "docs" / "specs" / "VISION.md"
        if vision.exists():
            text = vision.read_text(encoding="utf-8")
            # Extract Immediate Actions section
            m = re.search(r"## 6\. Immediate Actions(.*?)(?=^##|\Z)", text, re.DOTALL | re.MULTILINE)
            if m:
                parts.append("VISION.md priorities:\n" + m.group(1)[:500])

        # Read kernel results log
        log = self.repo_root / "qa_lab" / "kernel" / "results_log.jsonl"
        if log.exists():
            try:
                lines = log.read_text(encoding="utf-8").strip().split("\n")[-20:]
                parts.append("Recent kernel results:\n" + "\n".join(lines[-5:]))
            except Exception:
                pass

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Kernel trace reading
    # ------------------------------------------------------------------

    def _read_kernel_traces(self) -> List[Dict[str, Any]]:
        log = self.repo_root / "qa_lab" / "kernel" / "results_log.jsonl"
        if not log.exists():
            return []
        traces = []
        try:
            for line in log.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        traces.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        return traces[-50:]  # last 50 traces

    # ------------------------------------------------------------------
    # Task proposal and ranking
    # ------------------------------------------------------------------

    def _propose_tasks(
        self,
        context: str,
        kernel_traces: List[Dict[str, Any]],
        focus_area: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Match synthesis rules against context, score, deduplicate, rank."""
        scored: List[Tuple[float, Dict[str, Any]]] = []

        context_lower = context.lower() if context else ""

        # Check which tasks have already been completed recently
        recent_descriptions = {
            t.get("description", "").lower()
            for t in kernel_traces
            if t.get("ok") and t.get("verified")
        }

        for pattern, template, base_priority in self.SYNTHESIS_RULES:
            # Focus area filter
            if focus_area and focus_area.lower() not in template["description"].lower():
                continue

            # Score by pattern match in context
            match_score = 1.0 if re.search(pattern, context_lower) else 0.3

            # Boost for recently failed tasks (need retry)
            for trace in kernel_traces[-10:]:
                if not trace.get("ok") and template["description"][:30].lower() in trace.get("description", "").lower():
                    match_score += 0.2

            # Penalise if recently completed successfully
            if any(template["description"][:30].lower() in d for d in recent_descriptions):
                match_score *= 0.3

            priority = round(base_priority * match_score, 3)

            # Always include high-priority items (orbit_score weighted)
            import sys
            sys.path.insert(0, str(_QA_LAB_DIR))
            from qa_core import orbit_family_score
            orbit_boost = orbit_family_score(self.orbit_family)  # cosmos=1.0
            priority = round(priority * (0.7 + 0.3 * orbit_boost), 3)

            scored.append((priority, {**template, "priority": priority}))

        # Always add a meta-validator health check if not recently run
        meta_recently_run = any(
            t.get("task_type") == "certify" and "meta" in t.get("description", "").lower()
            for t in kernel_traces[-20:]
        )
        if not meta_recently_run:
            scored.append((0.95, {
                "task_type": "certify",
                "description": "Meta-validator health check — confirm 128/128 PASS",
                "inputs": {"run_meta": True},
                "success_criteria": ["128/128 PASS"],
                "priority": 0.95,
            }))

        # Sort by priority descending, deduplicate by description prefix
        scored.sort(key=lambda x: x[0], reverse=True)
        seen: set = set()
        result = []
        for _, proposal in scored:
            key = proposal["description"][:40].lower()
            if key not in seen:
                seen.add(key)
                result.append(proposal)

        return result
