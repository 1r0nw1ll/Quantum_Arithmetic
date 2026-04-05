"""
qa_lab.agents.query_agent
==========================
QueryAgent — deterministic QA-native query answering via qa_core.

Query types (set via inputs["query_type"] or auto-detected from inputs):

  orbit       — classify (b, e) mod m: family, length, norm, tuple
  reachable   — is (b1,e1) reachable from (b2,e2) mod m? + obstruction reason
  obstruction — structural obstruction for a target residue r mod m
  norm        — compute qa_norm(b, e) and norm mod m
  family_counts — census of cosmos/satellite/singularity for modulus m
  inert_primes  — inert primes for modulus m
  tuple       — full QA tuple (b, e, d, a) for a state
  step        — apply one Q-step: (b,e) → (e, b+e mod m)

All outputs are CONSISTENT verdicts with full evidence.
No stub=True. No PARTIAL unless inputs are malformed.

Spawned from task 7e295818 — first real self-improvement event.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path
from typing import Any, Dict, Optional

_AGENTS_DIR = str(Path(__file__).resolve().parent)
_QA_LAB_DIR = str(Path(__file__).resolve().parent.parent)
for _d in (_AGENTS_DIR, _QA_LAB_DIR):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

from base import QAAgent
from qa_core import (
    classify_state, orbit_length, qa_norm_mod, qa_tuple,
    qa_step, is_reachable, structural_obstruction,
    precompute_all_families, INERT_PRIMES,
)

# qa_norm lives in algebra module — import directly
from qa_core.algebra import qa_norm


class QueryAgent(QAAgent):
    """Deterministic QA-native query answering.

    Capabilities: query
    """

    capabilities = ["query"]
    cert_family = "query_agent_cert"

    # Query type keywords for auto-detection
    _TYPE_HINTS = {
        "orbit":         ["orbit", "classify", "family", "length"],
        "reachable":     ["reachable", "reach", "reachability"],
        "obstruction":   ["obstruct", "inert", "barrier", "fail"],
        "norm":          ["norm"],
        "family_counts": ["census", "count", "how many", "distribution"],
        "inert_primes":  ["inert prime", "inert_prime"],
        "tuple":         ["tuple", "(b,e,d,a)", "full state"],
        "step":          ["step", "next state", "q-step", "advance"],
    }

    def __init__(self, modulus: int = 9):
        super().__init__(name="query_agent", modulus=modulus)

    # ------------------------------------------------------------------
    # handle
    # ------------------------------------------------------------------

    def handle(self, task: Any) -> Dict[str, Any]:
        """Answer a QA-native query.

        inputs:
          query_type  — explicit type (orbit|reachable|obstruction|norm|
                        family_counts|inert_primes|tuple|step)
          query       — free-text query (used for auto-detection if no type)
          b, e        — state coordinates (int)
          m           — modulus (default: self.modulus)
          b2, e2      — second state for reachability
          r           — residue for obstruction query
        """
        inputs = task.inputs if hasattr(task, "inputs") else {}
        m = int(inputs.get("m", self.modulus))
        query_text = str(inputs.get("query", task.description if hasattr(task, "description") else ""))
        qt = inputs.get("query_type") or self._detect_type(query_text, inputs)

        handler = {
            "orbit":         self._query_orbit,
            "reachable":     self._query_reachable,
            "obstruction":   self._query_obstruction,
            "norm":          self._query_norm,
            "family_counts": self._query_family_counts,
            "inert_primes":  self._query_inert_primes,
            "tuple":         self._query_tuple,
            "step":          self._query_step,
        }.get(qt)

        if handler is None:
            return self._unknown_query(query_text, inputs)

        return handler(inputs, m, query_text)

    # ------------------------------------------------------------------
    # Query handlers
    # ------------------------------------------------------------------

    def _query_orbit(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        b, e, err = self._require_be(inputs)
        if err:
            return err

        family = classify_state(b, e, m)
        length = orbit_length(b, e, m)
        norm_val = qa_norm(b, e)
        norm_mod = qa_norm_mod(b, e, m)
        tup = qa_tuple(b, e, m)

        answer = (f"State ({b},{e}) mod {m}: family={family}, orbit_length={length}, "
                  f"norm={norm_val}, norm_mod={norm_mod}, tuple={tup}")

        cert = self.certify(
            observation_body=f"Orbit query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "orbit_query", "b": b, "e": e, "m": m,
                       "family": family, "orbit_length": length,
                       "norm": norm_val, "norm_mod": norm_mod, "tuple": tup}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "orbit",
                "answer": answer, "family": family, "orbit_length": length,
                "norm": norm_val, "norm_mod": norm_mod, "tuple": list(tup), "cert": cert}

    def _query_reachable(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        b1, e1, err = self._require_be(inputs, prefix="")
        if err:
            return err
        b2 = inputs.get("b2")
        e2 = inputs.get("e2")
        if b2 is None or e2 is None:
            return self._error("reachable query requires b2, e2 (target state)")
        b2, e2 = int(b2), int(e2)

        reachable = is_reachable(b1, e1, b2, e2, m)
        # Failure algebra: if not reachable, why?
        reason = None
        if not reachable:
            r = b2 * b2 + b2 * e2 - e2 * e2
            obstructed = structural_obstruction(r, m)
            reason = (f"structurally obstructed (inert prime divides norm {r} mod {m})"
                      if obstructed else "different orbit — no structural path")

        answer = (f"({b1},{e1}) → ({b2},{e2}) mod {m}: "
                  f"{'REACHABLE' if reachable else 'NOT REACHABLE'}"
                  + (f" — {reason}" if reason else ""))

        cert = self.certify(
            observation_body=f"Reachability query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "reachability", "start": [b1, e1], "target": [b2, e2],
                       "m": m, "reachable": reachable, "reason": reason}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "reachable",
                "answer": answer, "reachable": reachable, "reason": reason, "cert": cert}

    def _query_obstruction(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        r = inputs.get("r")
        if r is None:
            # Try extracting from b,e
            b, e, err = self._require_be(inputs)
            if err:
                return self._error("obstruction query requires r (residue) or b,e")
            r = b * b + b * e - e * e
        r = int(r)

        obstructed = structural_obstruction(r, m)
        inert = INERT_PRIMES.get(m, [])
        answer = (f"r={r} mod {m}: {'OBSTRUCTED' if obstructed else 'CLEAR'} — "
                  f"inert primes for mod-{m}: {inert}")

        cert = self.certify(
            observation_body=f"Obstruction query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "obstruction", "r": r, "m": m,
                       "obstructed": obstructed, "inert_primes": inert}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "obstruction",
                "answer": answer, "obstructed": obstructed,
                "inert_primes": inert, "cert": cert}

    def _query_norm(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        b, e, err = self._require_be(inputs)
        if err:
            return err

        norm_val = qa_norm(b, e)
        norm_mod = qa_norm_mod(b, e, m)
        answer = f"norm({b},{e}) = b²+be-e² = {norm_val}  ≡ {norm_mod} mod {m}"

        cert = self.certify(
            observation_body=f"Norm query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "norm", "b": b, "e": e, "m": m,
                       "norm": norm_val, "norm_mod": norm_mod}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "norm",
                "answer": answer, "norm": norm_val, "norm_mod": norm_mod, "cert": cert}

    def _query_family_counts(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        from collections import Counter
        families = precompute_all_families(m)
        counts = dict(Counter(families.values()))
        total = m * m
        answer = (f"mod-{m} state space ({total} states): "
                  + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

        cert = self.certify(
            observation_body=f"Family counts query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "family_counts", "m": m, "counts": counts, "total": total}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "family_counts",
                "answer": answer, "counts": counts, "m": m, "cert": cert}

    def _query_inert_primes(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        inert = INERT_PRIMES.get(m, [])
        answer = (f"Inert primes for mod-{m}: {inert} — "
                  f"these primes divide norms that create structural obstructions. "
                  f"A state with v_p(norm) = 1 for any inert p cannot be reached from "
                  f"outside its orbit family.")

        cert = self.certify(
            observation_body=f"Inert primes query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "inert_primes", "m": m, "inert_primes": inert}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "inert_primes",
                "answer": answer, "inert_primes": inert, "m": m, "cert": cert}

    def _query_tuple(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        b, e, err = self._require_be(inputs)
        if err:
            return err

        tup = qa_tuple(b, e, m)
        b_, e_, d, a = tup
        answer = f"QA tuple ({b},{e}) mod {m}: (b={b_}, e={e_}, d={d}, a={a})  where d=(b+e)%m, a=(b+2e)%m"

        cert = self.certify(
            observation_body=f"Tuple query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "tuple", "b": b, "e": e, "m": m, "tuple": list(tup)}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "tuple",
                "answer": answer, "tuple": list(tup), "cert": cert}

    def _query_step(self, inputs: Dict, m: int, query: str) -> Dict[str, Any]:
        b, e, err = self._require_be(inputs)
        if err:
            return err

        nb, ne = qa_step(b, e, m)
        family_before = classify_state(b, e, m)
        family_after = classify_state(nb, ne, m)
        answer = f"Q-step: ({b},{e}) → ({nb},{ne}) mod {m}  [{family_before} → {family_after}]"

        cert = self.certify(
            observation_body=f"Step query: {query}\n{answer}",
            verdict="CONSISTENT",
            evidence=[{"type": "step", "before": [b, e], "after": [nb, ne], "m": m,
                       "family_before": family_before, "family_after": family_after}],
            parent_cert_name="QA_CORE_SPEC.v1",
            observation_source="experiment_script",
        )
        return {"ok": True, "verdict": "CONSISTENT", "query_type": "step",
                "answer": answer, "before": [b, e], "after": [nb, ne], "cert": cert}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_type(self, query: str, inputs: Dict) -> Optional[str]:
        """Auto-detect query type from free text + inputs present."""
        q = query.lower()
        for qt, hints in self._TYPE_HINTS.items():
            if any(h in q for h in hints):
                return qt
        # Fallback from inputs
        if "b" in inputs and "e" in inputs:
            if "b2" in inputs or "e2" in inputs:
                return "reachable"
            return "orbit"
        if "r" in inputs:
            return "obstruction"
        if "m" in inputs and "b" not in inputs:
            return "family_counts"
        return None

    def _require_be(self, inputs: Dict, prefix: str = "") -> tuple:
        bk = f"{prefix}b" if prefix else "b"
        ek = f"{prefix}e" if prefix else "e"
        b = inputs.get(bk)
        e = inputs.get(ek)
        if b is None or e is None:
            return None, None, self._error(f"query requires {bk} and {ek}")
        return int(b), int(e), None

    def _error(self, msg: str) -> Dict[str, Any]:
        return {"ok": False, "verdict": "INCONCLUSIVE", "error": msg,
                "hint": "Supported query_type values: orbit, reachable, obstruction, "
                        "norm, family_counts, inert_primes, tuple, step"}

    def _unknown_query(self, query: str, inputs: Dict) -> Dict[str, Any]:
        return {"ok": False, "verdict": "INCONCLUSIVE",
                "error": f"Could not determine query type from: {query!r}",
                "hint": "Set inputs['query_type'] explicitly: orbit|reachable|obstruction|"
                        "norm|family_counts|inert_primes|tuple|step",
                "inputs_received": list(inputs.keys())}
