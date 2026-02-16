#!/usr/bin/env python3
"""
qa_ebm_cert_lane.py

Emit QA EBM navigation/verifier-bridge certificates from QA Lab scoring pipelines.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
QA_LAB_ROOT = Path(__file__).resolve().parent
NAV_VALIDATOR = REPO_ROOT / "qa_ebm_navigation_cert" / "validator.py"
BRIDGE_VALIDATOR = REPO_ROOT / "qa_ebm_verifier_bridge_cert" / "validator.py"
MAPPING_PROTOCOL_PATH = REPO_ROOT / "Documents" / "QA_MAPPING_PROTOCOL__EBM_REASONING_KONA_PODCAST.v1.json"


def _canonical_json_compact(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_cert_digest(cert_obj: Dict[str, Any]) -> str:
    cert_copy = json.loads(_canonical_json_compact(cert_obj))
    cert_copy.setdefault("digests", {})
    cert_copy["digests"]["canonical_sha256"] = "0" * 64
    return _sha256_text(_canonical_json_compact(cert_copy))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ref_digest(ref_name: str, sha256_value: str) -> Dict[str, str]:
    return {"ref_name": ref_name, "sha256": sha256_value}


def _energy_from_score(score: float) -> int:
    clamped = min(1.0, max(0.0, float(score)))
    return int(round((1.0 - clamped) * 1_000_000.0))


def _winner_index(candidates: List[Dict[str, Any]]) -> int:
    ranked = []
    for idx, candidate in enumerate(candidates):
        energy = int(candidate["energy_after"]["value"])
        ranked.append((energy, candidate["generator"], candidate["state_after"], idx))
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    return int(ranked[0][3])


def _validate_json(cert_path: Path, validator_path: Path) -> Tuple[bool, str]:
    if not validator_path.exists():
        return False, f"validator_missing:{validator_path}"
    proc = subprocess.run(
        [sys.executable, str(validator_path), str(cert_path), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        return False, (proc.stdout or proc.stderr or "").strip()
    return True, (proc.stdout or "").strip()


def emit_fastpath_case_certs(
    *,
    run_id: str,
    case_name: str,
    selected_indices: List[int],
    selected_scores: List[float],
    accepted_by_verifier: bool = False,
    validate: bool = True,
) -> Dict[str, Any]:
    cert_root = QA_LAB_ROOT / "artifacts" / "certs" / run_id
    cert_root.mkdir(parents=True, exist_ok=True)

    selected = [
        {"idx": int(idx), "score": float(score)}
        for idx, score in zip(selected_indices, selected_scores)
    ]
    if not selected:
        return {
            "ok": False,
            "error": "no_selected_candidates",
            "run_id": run_id,
            "case_name": case_name,
        }

    mapping_ref = None
    if MAPPING_PROTOCOL_PATH.exists():
        mapping_ref = _ref_digest(
            str(MAPPING_PROTOCOL_PATH.relative_to(REPO_ROOT)),
            _sha256_file(MAPPING_PROTOCOL_PATH),
        )

    candidates = []
    for row in selected:
        state_after = f"candidate:{row['idx']}"
        energy_int = _energy_from_score(row["score"])
        candidates.append(
            {
                "generator": "fastpath_rerank",
                "legal": True,
                "state_after": state_after,
                "energy_after": {"type": "int", "value": str(energy_int)},
                "violations_after": {"violations_total": energy_int},
            }
        )
    chosen_idx = _winner_index(candidates)
    chosen = candidates[chosen_idx]
    energy_before = max(int(c["energy_after"]["value"]) for c in candidates) + 1
    energy_after = int(chosen["energy_after"]["value"])

    problem_ref = _ref_digest(
        f"qa_fast_eval_case:{case_name}",
        _sha256_text(_canonical_json_compact({"case": case_name, "selected": selected})),
    )
    constraints_ref = _ref_digest(
        "qa_lab/qa_fastpath.py",
        _sha256_file(QA_LAB_ROOT / "qa_fastpath.py"),
    )
    target_ref = _ref_digest(
        f"qa_fast_eval_target:{case_name}",
        _sha256_text(f"qa_fast_eval_target::{case_name}"),
    )

    bridge_payload: Optional[Dict[str, Any]] = None
    bridge_path: Optional[Path] = None
    bridge_ref: Optional[Dict[str, str]] = None

    nav_payload: Dict[str, Any] = {
        "cert_type": "QA_EBM_NAVIGATION_CERT.v1",
        "schema_version": 1,
        "cert_id": f"ebm_nav_{run_id}_{case_name}",
        "issued_utc": _now_utc(),
        "inputs": {
            "problem_ref": problem_ref,
            "constraints_ref": constraints_ref,
        },
        "navigation": {
            "state_space": {"state_type": "Fastpath candidate index state"},
            "generators": [
                {
                    "name": "fastpath_rerank",
                    "kind": "ebm_meta_policy",
                    "transition_rule": "Select min-energy legal candidate from scored shortlist",
                    "invariant_effect": "Preserves deterministic tie-break and typed failure-complete contract",
                }
            ],
            "energy": {
                "scalar_type": "int",
                "definition": (
                    "Lab-local deterministic ranking penalty: "
                    "E=round((1-score)*1e6), monotone transform of score (not physical energy)"
                ),
                "minimize": True,
                "components": [
                    {
                        "name": "ranking_penalty",
                        "weight": {"type": "int", "value": "1"},
                        "unit": "penalty",
                    }
                ],
            },
            "policy": {
                "selection": "min_energy_legal",
                "tie_break": "lex_generator_then_state_after",
                "declared_deterministic": True,
            },
            "budgets": {"max_steps": 1, "max_millis": 5000},
        },
        "trace": {
            "steps": [
                {
                    "t": 0,
                    "state_before": f"pool:{len(candidates)}",
                    "energy_before": {"type": "int", "value": str(energy_before)},
                    "violations_before": {"violations_total": energy_before},
                    "candidates": candidates,
                    "chosen_idx": chosen_idx,
                    "result": "OK",
                    "state_after": chosen["state_after"],
                    "energy_after": {"type": "int", "value": str(energy_after)},
                    "violations_after": {"violations_total": energy_after},
                    "invariant_diff": {
                        "delta_energy": {"type": "int", "value": str(energy_after - energy_before)},
                        "delta_violations": {"violations_total": energy_after - energy_before},
                        "witness": "Deterministic min-energy legal successor under lex(generator,state_after) tie-break.",
                    },
                }
            ],
            "outcome": {
                "status": "REACHED_TARGET",
                "target_ref": target_ref,
            },
        },
        "determinism_contract": {
            "invariant_diff_defined": True,
            "failure_complete": True,
            "tie_break_total": True,
            "exact_energy_required": True,
        },
        "digests": {"canonical_sha256": "0" * 64},
    }
    if mapping_ref:
        nav_payload["inputs"]["mapping_protocol_ref"] = mapping_ref

    if accepted_by_verifier:
        bridge_payload = {
            "cert_type": "QA_EBM_VERIFIER_BRIDGE_CERT.v1",
            "schema_version": 1,
            "cert_id": f"ebm_bridge_{run_id}_{case_name}",
            "issued_utc": _now_utc(),
            "verifier": {
                "verifier_id": "qa_fast_eval_constraint_gate",
                "verifier_version": "v1",
                "mode": "constraint_check",
                "deterministic": True,
            },
            "subject": {
                "state_after": chosen["state_after"],
                "state_sha256": _sha256_text(chosen["state_after"]),
                "target_ref": target_ref,
                "note": (
                    "Verifier bridge uses a deterministic QA Lab constraint gate "
                    "(not an external proof assistant)."
                ),
            },
            "verdict": {
                "passed": True,
                "fail_type": "OK",
                "witness": (
                    "Lab-internal deterministic constraint gate accepted the top-ranked candidate; "
                    "this is not a Lean/Coq proof verdict."
                ),
            },
            "invariant_diff": {
                "witness": "state_after digest bound and verdict coherent.",
                "state_sha256": _sha256_text(chosen["state_after"]),
                "verdict_fail_type": "OK",
            },
            "digests": {"canonical_sha256": "0" * 64},
        }
        if mapping_ref:
            bridge_payload["inputs"] = {"mapping_protocol_ref": mapping_ref}
        bridge_payload["digests"]["canonical_sha256"] = _compute_cert_digest(bridge_payload)
        bridge_path = cert_root / f"ebm_bridge_{run_id}_{case_name}.json"
        _write_json(bridge_path, bridge_payload)
        bridge_ref = _ref_digest(
            str(bridge_path.relative_to(REPO_ROOT).as_posix()),
            bridge_payload["digests"]["canonical_sha256"],
        )

        nav_payload["trace"]["outcome"]["accepted_by_verifier"] = True
        nav_payload["trace"]["outcome"]["verifier_bridge_ref"] = bridge_ref
        nav_payload.setdefault("digests", {})
        nav_payload["digests"]["refs"] = [bridge_ref]

    nav_payload["digests"]["canonical_sha256"] = _compute_cert_digest(nav_payload)
    nav_path = cert_root / f"ebm_nav_{run_id}_{case_name}.json"
    _write_json(nav_path, nav_payload)

    status: Dict[str, Any] = {
        "ok": True,
        "run_id": run_id,
        "case_name": case_name,
        "navigation_cert": str(nav_path.relative_to(QA_LAB_ROOT)),
        "navigation_sha256": nav_payload["digests"]["canonical_sha256"],
        "bridge_cert": str(bridge_path.relative_to(QA_LAB_ROOT)) if bridge_path else None,
        "accepted_by_verifier": bool(nav_payload["trace"]["outcome"].get("accepted_by_verifier", False)),
        "bridge_emitted": bool(bridge_path),
        "bridge_navigation_digest_match": None,
    }

    if validate:
        if bridge_path:
            bridge_ok, bridge_msg = _validate_json(bridge_path, BRIDGE_VALIDATOR)
            status["bridge_valid"] = bridge_ok
            if not bridge_ok:
                status["ok"] = False
                status["bridge_error"] = bridge_msg

        nav_ok, nav_msg = _validate_json(nav_path, NAV_VALIDATOR)
        status["navigation_valid"] = nav_ok
        if not nav_ok:
            status["ok"] = False
            status["navigation_error"] = nav_msg

    manifest_path = cert_root / "manifest.json"
    existing = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    manifest_cases = existing.get("cases", {})
    manifest_cases[case_name] = {
        "navigation_cert": status["navigation_cert"],
        "bridge_cert": status["bridge_cert"],
        "accepted_by_verifier": status["accepted_by_verifier"],
        "bridge_emitted": status["bridge_emitted"],
    }
    manifest_payload = {
        "run_id": run_id,
        "generated_utc": _now_utc(),
        "cases": manifest_cases,
    }
    _write_json(manifest_path, manifest_payload)
    status["manifest"] = str(manifest_path.relative_to(QA_LAB_ROOT))
    return status
