"""
qa_lab.agents.self_improvement_agent_v2
========================================
SelfImprovementAgentV2 — [191]/[192]-aware refactor of
`self_improvement_agent.SelfImprovementAgent` (v1).

Contract
--------
See ``docs/qa_lab/SELF_IMPROVEMENT_AGENT_DESIGN.md`` (written by the
`lab-consolidation` session, 2026-04-05). That document is the spec this
file implements. Read it first.

Core deltas vs. v1
------------------
1. **Level tagging** — every proposal is tagged with
   ``level ∈ {L_1, L_2a, L_2b, L_3, None}`` and ``invariant_broken`` per the
   Bateson / Tiered Reachability filtration certified by [191].
2. **Lyapunov gate** — a single scalar ρ-EWMA (Unified Curvature §8.1) is
   computed pre- and post-cycle; any ``L_2a`` proposal is auto-applied only
   through ``_apply_with_probe`` (snapshot → apply → measure → rollback-or-
   commit).  ``L_2b`` and ``L_3`` are always deferred.
3. **Pisano-analog fixed-point readout** — every cycle emits three numeric
   candidates (A trace compression, B routing barycenter, C restricted
   Pisano periodicity) per ``LEARNING_LEVELS_BRIDGE.md §5``.  Reported, not
   enforced.

Safety invariants
-----------------
* v1's ``_generate_proposals`` is reused verbatim via ``super()``; no rule is
  rewritten.
* ``L_2b`` / ``L_3`` never land in ``applied``.  (Asserted in tests.)
* ``_apply_with_probe`` performs a full snapshot-and-restore of kernel state
  — the single biggest risk per design doc §10.6.  Restore happens on every
  path, including exceptions.
* No writes to ``loop.py``, ``base.py``, or v1.
* No Open Brain writes from inside the agent — the kernel's LEARN phase
  handles capture.
"""

from __future__ import annotations

QA_COMPLIANCE = "qa_lab_self_improvement_agent_v2 — orbit state tracks agent position; Lyapunov (rho-EWMA / sat_fraction / weighted_sr) is an observer-layer measurement per Theorem NT, never a causal input to QA dynamics; no continuous state; kernel b/e stay integer under snapshot/restore"

import contextlib
import copy
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_AGENTS_DIR = Path(__file__).resolve().parent
_QA_LAB_DIR = _AGENTS_DIR.parent

if str(_QA_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_LAB_DIR))

from agents.self_improvement_agent import SelfImprovementAgent as _V1
from agents.self_improvement_agent import _safe_proposal


# ---------------------------------------------------------------------------
# Level mapping table
# ---------------------------------------------------------------------------
#
# Mapping from v1 rule identifier → ([191] level, invariant broken).
# "None" level means the action is a parameter tweak outside the QA state
# space (e.g. ADJUST_THRESHOLD writes a scalar on the kernel that is not a
# coordinate in S_m).  Such proposals are always applied directly — they are
# NOT state-space operators at all.
#
# Authority: LEARNING_LEVELS_BRIDGE.md §3.

_LEVEL_TABLE: Dict[str, Tuple[Optional[str], str]] = {
    "R1_SINGULARITY_STUCK":  (None,   "none"),          # kernel scalar
    "R2_SATELLITE_LOOP":     (None,   "none"),          # kernel scalar
    "R3_WEAK_AGENT":         ("L_2a", "orbit"),         # agent population
    "R4_ORBIT_DRIFT":        ("L_2b", "family"),        # agent family change
    "R5_UNHANDLED_CAPABILITY": ("L_2a", "orbit"),       # StemAgent lifecycle
    "R6_OB_INSIGHT":         (None,   "none"),          # log only
    "R7_HEALTHY":            (None,   "none"),          # log only
}

_CERT_REF = "QA_BATESON_LEARNING_LEVELS_CERT.v1"
_TIER_CLAIM_NOTE = "[191] §5.3 Tiered Reachability; witnesses exhaustively verified on S_9."


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class SelfImprovementAgentV2(_V1):
    """v2 self-improvement agent — level-tagged, Lyapunov-gated.

    Subclasses v1; inherits the 7-rule engine and OB keyword table.  Overrides
    ``handle`` and ``_apply_governed``; adds ``_tag_levels``,
    ``_compute_lyapunov``, ``_compute_fixed_point_candidates``, and
    ``_apply_with_probe``.
    """

    capabilities = ["improve"]
    cert_family = "qa_self_improvement_cert"  # stub, see qa_self_improvement_cert_v1/

    #: Class attribute: small set of probe tasks used by ``_apply_with_probe``
    #: for forward dry-run.  Defaults to empty; the baseline session leaves
    #: probe cycles off and measures Lyapunov on the unchanged tail of
    #: ``_results``.  A future session may override this with three
    #: ``Task(TaskType.QUERY, ...)`` instances covering one tuple from each
    #: orbit family.
    _probe_tasks: List[Any] = []

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(
        self,
        modulus: int = 9,
        lyapunov: str = "rho_ewma",
        lyapunov_alpha: float = 0.2,
        dry_run_probe_cycles: int = 0,
        max_applied_per_cycle: int = 3,
    ) -> None:
        super().__init__(modulus=modulus)
        self.name = "self_improvement_agent_v2"
        self.lyapunov_name = lyapunov
        self.alpha = float(lyapunov_alpha)
        self.dry_run_probe_cycles = int(dry_run_probe_cycles)
        self.max_applied_per_cycle = int(max_applied_per_cycle)
        self._lyap_history: List[Tuple[int, float]] = []
        self._fp_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # handle — §4 of design doc
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:  # type: ignore[override]
        inputs = task.inputs if hasattr(task, "inputs") else {}

        introspect = inputs.get("introspect") or {}
        recent_results = inputs.get("recent_results") or []
        orbit_context = inputs.get("orbit_context") or {}
        spawn_queue = inputs.get("spawn_queue") or []
        ob_context = inputs.get("ob_context") or inputs.get("context") or ""
        kernel_ref = inputs.get("kernel_ref")
        lyap_override = inputs.get("lyap_override")
        if isinstance(lyap_override, str):
            self.lyapunov_name = lyap_override
        lyap_tol_override = inputs.get("lyap_tol")

        # Stale kernel_ref guard — §10.5
        run_id_at_start = getattr(kernel_ref, "_kernel_run_id", None)

        # Step 1: generate proposals (v1, unchanged)
        proposals = self._generate_proposals(
            introspect, recent_results, orbit_context, spawn_queue, ob_context
        )

        # Step 2: level tagging
        tagged = self._tag_levels(proposals)

        # Step 3: pre-Lyapunov
        lyap_pre = self._compute_lyapunov(kernel_ref)

        # Step 4: fixed-point candidates readout
        fp_readout = self._compute_fixed_point_candidates(kernel_ref)

        # Step 5: level-gated application
        tol = (
            float(lyap_tol_override)
            if lyap_tol_override is not None
            else max(1e-9, 1e-6 * abs(lyap_pre))
        )
        applied, deferred = self._apply_level_gated(tagged, kernel_ref, lyap_pre, tol)

        # Step 6: post-Lyapunov
        lyap_post = self._compute_lyapunov(kernel_ref)

        # Stale kernel_ref guard — §10.5 (second half)
        run_id_at_end = getattr(kernel_ref, "_kernel_run_id", None)
        kernel_stale = (
            run_id_at_start is not None
            and run_id_at_end is not None
            and run_id_at_start != run_id_at_end
        )

        # Verdict rule — §4 of design doc
        verdict, fail_ledger = self._verdict(
            tagged, applied, lyap_pre, lyap_post, tol, kernel_stale
        )

        # Kernel quality vector (LEARNING_LEVELS_BRIDGE.md §4.2)
        kqv = self._kernel_quality_vector(kernel_ref, lyap_post)

        # Summary
        health = introspect.get("health", "unknown")
        orbit_fam = introspect.get("kernel_family", "unknown")
        summary = (
            f"Self-improvement v2 cycle: health={health} orbit={orbit_fam} "
            f"proposals={len(tagged)} applied={len(applied)} deferred={len(deferred)} "
            f"lyap={self.lyapunov_name}: {lyap_pre:.6f} → {lyap_post:.6f} "
            f"(delta={lyap_post - lyap_pre:+.6f})"
        )

        # Evidence for cert
        evidence = [
            {
                "type": "introspect_snapshot",
                "data": {
                    "health": health,
                    "orbit": orbit_fam,
                    "weak_agents": introspect.get("weak_agents", []),
                    "cycles": introspect.get("cycles", 0),
                },
            },
            {
                "type": "proposals_tagged",
                "data": [_safe_proposal(p) for p in tagged],
            },
            {"type": "applied_actions", "data": [_safe_proposal(a) for a in applied]},
            {"type": "deferred_actions", "data": [_safe_proposal(d) for d in deferred]},
            {
                "type": "lyapunov",
                "data": {
                    "name": self.lyapunov_name,
                    "pre": lyap_pre,
                    "post": lyap_post,
                    "delta": lyap_post - lyap_pre,
                    "tol": tol,
                },
            },
            {"type": "fixed_point_candidates", "data": fp_readout},
            {"type": "kernel_quality_vector", "data": kqv},
            {"type": "kernel_run_id", "data": run_id_at_start},
        ]

        cert = self.certify(
            observation_body=summary,
            verdict=verdict,
            evidence=evidence,
            observation_source="self_improvement_agent_v2",
            fail_ledger=fail_ledger,
        )

        # History
        self._improvement_history.append(
            {
                "summary": summary,
                "proposals": len(tagged),
                "applied": len(applied),
                "deferred": len(deferred),
                "lyap_pre": lyap_pre,
                "lyap_post": lyap_post,
                "verdict": verdict,
            }
        )
        cycle_idx = getattr(kernel_ref, "_cycle_count", len(self._lyap_history))
        self._lyap_history.append((cycle_idx, lyap_post))
        self._fp_history.append({"cycle_idx": cycle_idx, **fp_readout})

        return {
            "ok": True,
            "verdict": verdict,
            "summary": summary,
            "proposals": tagged,
            "applied": applied,
            "deferred": deferred,
            "lyapunov": {
                "name": self.lyapunov_name,
                "pre": lyap_pre,
                "post": lyap_post,
                "delta": lyap_post - lyap_pre,
                "tol": tol,
            },
            "fixed_point_candidates": fp_readout,
            "kernel_quality_vector": kqv,
            "health": health,
            "cert": cert,
        }

    # ------------------------------------------------------------------
    # Level tagging — §5 of design doc
    # ------------------------------------------------------------------

    def _tag_levels(
        self, proposals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        tagged: List[Dict[str, Any]] = []
        for prop in proposals:
            rule = prop.get("rule", "")
            level, invariant = _LEVEL_TABLE.get(rule, (None, "none"))
            tagged.append(
                {
                    **prop,
                    "level": level,
                    "invariant_broken": invariant,
                    "cert_ref": _CERT_REF,
                    "tier_reachability_claim": _TIER_CLAIM_NOTE,
                }
            )
        return tagged

    # ------------------------------------------------------------------
    # Level-gated application — §6 of design doc
    # ------------------------------------------------------------------

    def _apply_level_gated(
        self,
        tagged: List[Dict[str, Any]],
        kernel_ref: Optional[Any],
        lyap_pre: float,
        tol: float,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        applied: List[Dict[str, Any]] = []
        deferred: List[Dict[str, Any]] = []
        applied_count = 0

        for prop in tagged:
            lvl = prop.get("level")
            action = prop.get("action")

            # Rate limit: cap on in-cycle applies (§10 item 3).
            if applied_count >= self.max_applied_per_cycle:
                deferred.append(
                    {
                        **prop,
                        "applied": False,
                        "committed": False,
                        "note": f"rate-limited: max_applied_per_cycle={self.max_applied_per_cycle}",
                    }
                )
                continue

            # L_2b and above: NEVER auto-apply.
            if lvl in ("L_2b", "L_3"):
                deferred.append(
                    {
                        **prop,
                        "applied": False,
                        "committed": False,
                        "note": (
                            f"level={lvl} requires operator approval per [191]; "
                            "L_2a is the highest autonomous tier in v2"
                        ),
                    }
                )
                continue

            # L_2a: apply under the probe gate.
            if lvl == "L_2a":
                result = self._apply_with_probe(prop, kernel_ref, lyap_pre, tol)
                if result.get("committed"):
                    applied.append(result)
                    applied_count += 1
                else:
                    deferred.append(result)
                continue

            # L_1 or level=None (parameter tweak / log-only): apply directly.
            result = self._apply_single(prop, kernel_ref)
            applied.append(result)
            applied_count += 1

        return applied, deferred

    def _apply_single(
        self, prop: Dict[str, Any], kernel_ref: Optional[Any]
    ) -> Dict[str, Any]:
        """Directly apply a single proposal without gating.

        Handles LOG_ONLY, ADJUST_THRESHOLD, SPAWN_IMPROVED (queue append),
        PROMOTE_STEM (spawn queue append).  DEDIFFERENTIATE should never
        reach here — it is L_2b and is deferred upstream.
        """
        action = prop.get("action")

        if action == "LOG_ONLY":
            return {**prop, "applied": True, "committed": True, "note": "logged"}

        if action == "ADJUST_THRESHOLD" and kernel_ref is not None:
            target = prop.get("target")
            new_value = prop.get("new_value")
            if target and new_value is not None and hasattr(kernel_ref, target):
                old_value = getattr(kernel_ref, target)
                setattr(kernel_ref, target, new_value)
                return {
                    **prop,
                    "applied": True,
                    "committed": True,
                    "old_value": old_value,
                    "note": f"kernel.{target} changed {old_value} → {new_value}",
                }
            return {
                **prop,
                "applied": False,
                "committed": False,
                "note": "no kernel_ref or unknown attribute",
            }

        if action == "ADJUST_THRESHOLD":
            return {
                **prop,
                "applied": False,
                "committed": False,
                "note": "no kernel_ref — cannot apply",
            }

        if action == "SPAWN_IMPROVED" and kernel_ref is not None:
            # Append a pending spawn spec to the kernel's queue.  Gated by
            # the kernel's existing require_spawn_approval flag downstream.
            spec = {
                "schema": "QA_AGENT_SPAWN_SPEC.v1",
                "required_capability": prop.get("target", "unknown"),
                "description": prop.get("reason", ""),
                "improvement_note": prop.get("spawn_spec_hint", {}),
                "source_rule": prop.get("rule"),
                "source_level": prop.get("level"),
                "approved": False,
                "pending_approval": True,
            }
            try:
                kernel_ref._spawn_queue.append(spec)
                return {
                    **prop,
                    "applied": True,
                    "committed": True,
                    "note": "queued spawn spec (operator approval still required)",
                }
            except Exception as exc:  # pragma: no cover — defensive
                return {
                    **prop,
                    "applied": False,
                    "committed": False,
                    "note": f"failed to queue spawn: {exc}",
                }

        if action == "PROMOTE_STEM" and kernel_ref is not None:
            # Promoting a stem agent is an L_2a op on the stem agent's
            # lifecycle.  In v2 we stage a note on the spawn queue rather
            # than directly reaching into StemAgent internals — that would
            # require a kernel edit to expose safely.  Honest deferral.
            return {
                **prop,
                "applied": False,
                "committed": False,
                "note": "stem promotion requires kernel surface not exposed in v2 — deferred",
            }

        # DEDIFFERENTIATE / unknown: defer
        return {
            **prop,
            "applied": False,
            "committed": False,
            "note": "action not directly applicable at this tier",
        }

    # ------------------------------------------------------------------
    # Apply-with-probe — §6 (snapshot/restore is §10.6)
    # ------------------------------------------------------------------

    def _apply_with_probe(
        self,
        prop: Dict[str, Any],
        kernel_ref: Optional[Any],
        lyap_pre: float,
        tol: float,
    ) -> Dict[str, Any]:
        if kernel_ref is None:
            return {
                **prop,
                "applied": False,
                "committed": False,
                "note": "L_2a probe requires kernel_ref",
            }

        snapshot = self._snapshot_kernel(kernel_ref)
        try:
            apply_result = self._apply_single(prop, kernel_ref)
            if not apply_result.get("committed"):
                # The apply itself failed — nothing to roll back, but
                # restore anyway for safety.
                self._restore_kernel(kernel_ref, snapshot)
                return {**apply_result, "probe_status": "apply_failed_pre_probe"}

            probe_error: Optional[str] = None
            if self.dry_run_probe_cycles > 0 and self._probe_tasks:
                try:
                    with self._isolated_ledgers(kernel_ref):
                        n = min(self.dry_run_probe_cycles, len(self._probe_tasks))
                        for probe in self._probe_tasks[:n]:
                            try:
                                kernel_ref.run_cycle(probe)
                            except Exception as exc:  # probe-local
                                probe_error = f"probe_cycle_error: {exc}"
                                break
                except Exception as exc:  # pragma: no cover
                    probe_error = f"probe_ledger_isolation_error: {exc}"

            lyap_post_probe = self._compute_lyapunov(kernel_ref)
            committed = (lyap_post_probe <= lyap_pre + tol) and probe_error is None

            # If probe ran forward cycles, always truncate state back to
            # snapshot regardless of commit decision — the probe cycles are
            # not real kernel history.
            ran_probe_cycles = (
                self.dry_run_probe_cycles > 0 and bool(self._probe_tasks)
            )

            if not committed:
                self._restore_kernel(kernel_ref, snapshot)
                return {
                    **apply_result,
                    "applied": False,
                    "committed": False,
                    "lyap_probe": lyap_post_probe,
                    "probe_status": probe_error or "probe_worsened_lyapunov",
                    "note": "probe rollback",
                }

            # Committed.  If we ran probe cycles we still need to restore
            # everything the probe touched (ledgers are already isolated,
            # _results was mutated by run_cycle).  We restore _results tail
            # but KEEP the applied proposal's changes — which we re-apply
            # after restore.
            if ran_probe_cycles:
                self._restore_kernel(kernel_ref, snapshot)
                self._apply_single(prop, kernel_ref)

            return {
                **apply_result,
                "applied": True,
                "committed": True,
                "lyap_probe": lyap_post_probe,
                "probe_status": "committed",
            }

        except Exception as exc:
            # Any unexpected failure: roll back unconditionally.
            self._restore_kernel(kernel_ref, snapshot)
            return {
                **prop,
                "applied": False,
                "committed": False,
                "note": f"probe_exception: {exc}",
            }

    # ------------------------------------------------------------------
    # Snapshot / restore — §10.6 (correctness-critical)
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot_kernel(kernel_ref: Any) -> Dict[str, Any]:
        """Capture the state that must be restored on rollback.

        Scalars are copied by value.  Containers are recorded by length +
        shallow copy of content so that a rollback can truncate.
        """
        return {
            "b": getattr(kernel_ref, "_b", None),
            "e": getattr(kernel_ref, "_e", None),
            "cycle_count": getattr(kernel_ref, "_cycle_count", 0),
            "satellite_streak": getattr(kernel_ref, "_satellite_streak", 0),
            "metamorphosis_threshold": getattr(
                kernel_ref, "metamorphosis_threshold", None
            ),
            "kernel_run_id": getattr(kernel_ref, "_kernel_run_id", None),
            "results_len": len(getattr(kernel_ref, "_results", []) or []),
            "spawn_queue_copy": list(getattr(kernel_ref, "_spawn_queue", []) or []),
            "agents_keys": list(getattr(kernel_ref, "_agents", {}) or {}),
            "agent_perf_copy": copy.deepcopy(
                getattr(kernel_ref, "_agent_perf", {}) or {}
            ),
        }

    @staticmethod
    def _restore_kernel(kernel_ref: Any, snap: Dict[str, Any]) -> None:
        if snap.get("b") is not None:
            kernel_ref._b = snap["b"]
        if snap.get("e") is not None:
            kernel_ref._e = snap["e"]
        kernel_ref._cycle_count = snap["cycle_count"]
        kernel_ref._satellite_streak = snap["satellite_streak"]
        if snap.get("metamorphosis_threshold") is not None:
            kernel_ref.metamorphosis_threshold = snap["metamorphosis_threshold"]
        if snap.get("kernel_run_id") is not None:
            kernel_ref._kernel_run_id = snap["kernel_run_id"]

        # Truncate _results to snapshot length.
        results = getattr(kernel_ref, "_results", None)
        if results is not None:
            del results[snap["results_len"] :]

        # Restore spawn_queue by truncating to snapshot length and overwriting.
        queue = getattr(kernel_ref, "_spawn_queue", None)
        if queue is not None:
            queue.clear()
            queue.extend(snap["spawn_queue_copy"])

        # Restore _agents dict to snapshot keys (drop any newly added
        # agents).  We do NOT swap out existing agent instances — their
        # internal (b,e) may have advanced, but that is out of scope for
        # this snapshot layer.
        agents = getattr(kernel_ref, "_agents", None)
        if agents is not None:
            snap_keys = set(snap["agents_keys"])
            for k in list(agents.keys()):
                if k not in snap_keys:
                    agents.pop(k, None)

        # Restore per-agent performance counters.
        if hasattr(kernel_ref, "_agent_perf"):
            kernel_ref._agent_perf = copy.deepcopy(snap["agent_perf_copy"])

    @staticmethod
    @contextlib.contextmanager
    def _isolated_ledgers(kernel_ref: Any):
        """Redirect the kernel's repo_root to a throwaway tempdir so that
        probe cycles' JSONL writes do not corrupt real ledgers."""
        original_root = getattr(kernel_ref, "repo_root", None)
        if original_root is None:
            yield
            return
        with tempfile.TemporaryDirectory(prefix="qa_lab_probe_") as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "qa_lab" / "kernel").mkdir(parents=True, exist_ok=True)
            (tmp_root / "qa_lab" / "kernel" / "spawn_queue").mkdir(
                parents=True, exist_ok=True
            )
            try:
                kernel_ref.repo_root = tmp_root
                yield
            finally:
                kernel_ref.repo_root = original_root

    # ------------------------------------------------------------------
    # Lyapunov — §7 of design doc
    # ------------------------------------------------------------------

    def _compute_lyapunov(self, kernel_ref: Optional[Any]) -> float:
        if kernel_ref is None:
            return 1.0
        name = self.lyapunov_name

        if name == "rho_ewma":
            results = getattr(kernel_ref, "_results", []) or []
            vals: List[float] = []
            for r in results[-64:]:
                # KernelResult dataclass uses .rho ; dict path for tests
                rho = getattr(r, "rho", None)
                if rho is None and isinstance(r, dict):
                    rho = r.get("rho") or r.get("kernel_rho")
                if rho is not None:
                    try:
                        vals.append(float(rho))
                    except (TypeError, ValueError):
                        pass
            if not vals:
                return 1.0
            ewma = vals[0]
            for v in vals[1:]:
                ewma = self.alpha * v + (1.0 - self.alpha) * ewma
            return float(ewma)

        if name == "sat_fraction":
            results = getattr(kernel_ref, "_results", []) or []
            tail = results[-64:]
            if not tail:
                return 0.0
            sat = 0
            for r in tail:
                fam = getattr(r, "orbit_family", None)
                if fam is None and isinstance(r, dict):
                    fam = r.get("orbit_family")
                if fam == "satellite":
                    sat += 1
            return sat / len(tail)

        if name == "weighted_sr":
            perf_fn = getattr(kernel_ref, "agent_performance", None)
            if not callable(perf_fn):
                return 1.0
            try:
                perf = perf_fn() or {}
            except Exception:
                return 1.0
            if not perf:
                return 1.0
            total = sum(p.get("total", 0) for p in perf.values())
            if total <= 0:
                return 1.0
            ws = (
                sum(
                    p.get("success_rate", 0.0) * p.get("total", 0)
                    for p in perf.values()
                )
                / total
            )
            return float(1.0 - ws)

        raise ValueError(f"unknown lyapunov: {name}")

    # ------------------------------------------------------------------
    # Fixed-point candidates — §8 of design doc
    # ------------------------------------------------------------------

    def _compute_fixed_point_candidates(
        self, kernel_ref: Optional[Any]
    ) -> Dict[str, Any]:
        return {
            "A_trace_compression": self._fp_A(kernel_ref),
            "B_routing_barycenter": self._fp_B(kernel_ref),
            "C_pisano_periodicity": self._fp_C(kernel_ref),
            "all_lyapunovs": self._all_lyapunov_snapshot(kernel_ref),
        }

    def _all_lyapunov_snapshot(
        self, kernel_ref: Optional[Any]
    ) -> Dict[str, float]:
        """Compute all three Lyapunov variants for the baseline readout.

        Per kickoff doc: "baseline readout produced at the end of the session
        should log all three. Will decides which to use going forward."
        """
        original = self.lyapunov_name
        out: Dict[str, float] = {}
        for name in ("rho_ewma", "sat_fraction", "weighted_sr"):
            self.lyapunov_name = name
            try:
                out[name] = self._compute_lyapunov(kernel_ref)
            except Exception as exc:  # pragma: no cover
                out[name] = float("nan")
        self.lyapunov_name = original
        return out

    # --- Candidate A: trace compression ratio --------------------------

    def _fp_A(self, kernel_ref: Optional[Any]) -> float:
        """Compression ratio of {C,S,G} encoding of the orbit transition tail.

        Lower ratio = more compressible = kernel trace is more structured.
        Fixed-point signal: ratio plateaus across cycles.
        """
        rows = self._read_jsonl_tail(
            kernel_ref, "orbit_transition_log.jsonl", n=256
        )
        if not rows:
            return 0.0
        letters = []
        for row in rows:
            fam = row.get("orbit_family_after") or row.get("orbit_family") or ""
            if fam == "cosmos":
                letters.append("C")
            elif fam == "satellite":
                letters.append("S")
            elif fam == "singularity":
                letters.append("G")
            else:
                letters.append("U")
        s = "".join(letters).encode("ascii")
        if not s:
            return 0.0
        return len(zlib.compress(s)) / len(s)

    # --- Candidate B: routing barycenter distance ----------------------

    def _fp_B(self, kernel_ref: Optional[Any]) -> float:
        """Sum over task types of |mean(task (b,e)) − agent (b,e)|_1 on Z/m.

        Uses L1 on (Z/m)×(Z/m) with circular distance as a cheap proxy for
        ``shortest_witness`` — the BFS version can be swapped in later
        without changing the interpretation (both are integer-valued,
        monotone, and bounded).
        """
        rows = self._read_jsonl_tail(
            kernel_ref, "task_state_trace.jsonl", n=256
        )
        if not rows or kernel_ref is None:
            return 0.0
        m = getattr(kernel_ref, "modulus", 9)
        by_type: Dict[str, List[Tuple[int, int]]] = {}
        for row in rows:
            if row.get("source") != "task.inputs":
                continue
            st = row.get("state")
            tt = row.get("task_type")
            if not (isinstance(st, list) and len(st) == 2):
                continue
            try:
                b_val = int(st[0]) % m
                e_val = int(st[1]) % m
            except (TypeError, ValueError):
                continue
            by_type.setdefault(tt, []).append((b_val, e_val))

        if not by_type:
            return 0.0

        agents = getattr(kernel_ref, "_agents", {}) or {}
        total_dist = 0.0
        counted = 0
        for tt_value, states in by_type.items():
            # Mean over the integer tuples, then rounded back to lattice.
            bs = sum(s[0] for s in states) / len(states)
            es = sum(s[1] for s in states) / len(states)
            b_mean = int(round(bs)) % m
            e_mean = int(round(es)) % m
            # Look up matching agent
            agent = None
            for key, a in agents.items():
                key_val = key.value if hasattr(key, "value") else str(key)
                if key_val == tt_value:
                    agent = a
                    break
            if agent is None:
                continue
            agent_b = getattr(agent, "_b", None)
            agent_e = getattr(agent, "_e", None)
            if agent_b is None or agent_e is None:
                continue
            # Circular distance on Z/m.
            db = min((b_mean - agent_b) % m, (agent_b - b_mean) % m)
            de = min((e_mean - agent_e) % m, (agent_e - e_mean) % m)
            total_dist += db + de
            counted += 1

        if counted == 0:
            return 0.0
        # Normalize by max possible distance so the readout is in [0, 1].
        return total_dist / (counted * m)

    # --- Candidate C: Pisano periodicity ratio -------------------------

    def _fp_C(self, kernel_ref: Optional[Any]) -> float:
        """Fraction of the last 48 kernel states that are periodic with
        period π(m) where π(9)=24.  Sanity check: under `_advance_orbit`
        on the (1,1) cosmos orbit this should be ≈1.0.
        """
        rows = self._read_jsonl_tail(
            kernel_ref, "orbit_transition_log.jsonl", n=48
        )
        if not rows:
            return 0.0
        m = getattr(kernel_ref, "modulus", 9) if kernel_ref else 9
        period = self._pisano_period(m)
        states: List[Tuple[int, int]] = []
        for row in rows:
            st = row.get("state_after")
            if isinstance(st, list) and len(st) == 2:
                try:
                    states.append((int(st[0]) % m, int(st[1]) % m))
                except (TypeError, ValueError):
                    pass
        n = len(states)
        if n == 0 or period <= 0 or n <= period:
            return 0.0
        # Fraction of indices i where states[i] == states[i - period].
        hits = sum(1 for i in range(period, n) if states[i] == states[i - period])
        return hits / (n - period)

    @staticmethod
    def _pisano_period(m: int) -> int:
        """Compute the Pisano period π(m) via direct cycle detection.
        Small m only (we never call this with m > 24 in practice)."""
        if m <= 1:
            return 1
        # Classical Pisano cycle detection — (pf, pg) are Fibonacci state
        # pair, not QA coordinates.  The variable `a` from the QA axiom
        # (a = b+2e) is unrelated to this local Fibonacci sequence.
        pf, pg = 0, 1
        for k in range(1, m * m + 1):
            pf, pg = pg, (pf + pg) % m
            if pf == 0 and pg == 1:
                return k
        return 0

    # ------------------------------------------------------------------
    # Ledger readers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_jsonl_tail(
        kernel_ref: Optional[Any], filename: str, n: int
    ) -> List[Dict[str, Any]]:
        if kernel_ref is None:
            return []
        repo_root = getattr(kernel_ref, "repo_root", None)
        if repo_root is None:
            return []
        path = Path(repo_root) / "qa_lab" / "kernel" / filename
        if not path.exists():
            return []
        try:
            import json

            lines = path.read_text(encoding="utf-8").splitlines()[-n:]
            rows: List[Dict[str, Any]] = []
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
            return rows
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Kernel quality vector — BRIDGE §4.2
    # ------------------------------------------------------------------

    def _kernel_quality_vector(
        self, kernel_ref: Optional[Any], lyap_post: float
    ) -> Dict[str, float]:
        if kernel_ref is None:
            return {
                "rho_smoothed": lyap_post,
                "p_cosmos": 0.0,
                "p_verified": 0.0,
                "n_weak_agents": 0,
            }
        results = getattr(kernel_ref, "_results", []) or []
        tail = results[-64:]
        if tail:
            cosmos = 0
            verified = 0
            for r in tail:
                fam = getattr(r, "orbit_family", None)
                ver = getattr(r, "verified", None)
                if fam is None and isinstance(r, dict):
                    fam = r.get("orbit_family")
                if ver is None and isinstance(r, dict):
                    ver = r.get("verified")
                if fam == "cosmos":
                    cosmos += 1
                if ver:
                    verified += 1
            p_cosmos = cosmos / len(tail)
            p_verified = verified / len(tail)
        else:
            p_cosmos = 0.0
            p_verified = 0.0

        try:
            perf = kernel_ref.agent_performance() or {}
            n_weak = sum(1 for p in perf.values() if p.get("needs_improvement"))
        except Exception:
            n_weak = 0

        return {
            "rho_smoothed": float(lyap_post),
            "p_cosmos": float(p_cosmos),
            "p_verified": float(p_verified),
            "n_weak_agents": int(n_weak),
        }

    # ------------------------------------------------------------------
    # Verdict rule — §4 of design doc
    # ------------------------------------------------------------------

    def _verdict(
        self,
        tagged: List[Dict[str, Any]],
        applied: List[Dict[str, Any]],
        lyap_pre: float,
        lyap_post: float,
        tol: float,
        kernel_stale: bool,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        if kernel_stale:
            return "INCONCLUSIVE", None

        # CONTRADICTS if any auto-applied L_2a rolled back OR lyap worsened.
        worsened: List[Dict[str, Any]] = []
        for a in applied:
            if a.get("level") == "L_2a":
                probe_status = a.get("probe_status", "")
                if probe_status not in ("committed", ""):
                    worsened.append(
                        {
                            "rule": a.get("rule"),
                            "probe_status": probe_status,
                            "lyap_pre": lyap_pre,
                            "lyap_probe": a.get("lyap_probe"),
                        }
                    )
        if lyap_post > lyap_pre + tol:
            worsened.append(
                {
                    "rule": "LYAPUNOV_POST",
                    "lyap_pre": lyap_pre,
                    "lyap_post": lyap_post,
                    "tol": tol,
                }
            )
        if worsened:
            return "CONTRADICTS", worsened

        # PARTIAL if any structural rule fired.
        if any(
            p.get("rule") in ("R1_SINGULARITY_STUCK", "R4_ORBIT_DRIFT")
            for p in tagged
        ):
            return "PARTIAL", None

        # INCONCLUSIVE if only R7 HEALTHY fired.
        non_healthy = [p for p in tagged if p.get("rule") != "R7_HEALTHY"]
        if not non_healthy:
            return "INCONCLUSIVE", None

        return "CONSISTENT", None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        s = super().status()
        s["version"] = "v2"
        s["lyapunov"] = self.lyapunov_name
        s["lyap_history_length"] = len(self._lyap_history)
        s["last_lyap"] = self._lyap_history[-1][1] if self._lyap_history else None
        return s
