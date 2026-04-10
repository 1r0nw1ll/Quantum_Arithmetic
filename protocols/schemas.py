"""
qa_lab.protocols.schemas
========================
Frozen protocol definitions for QA Lab internal communication.

These schemas are the "genetics" of the lab — they define what every
task, agent declaration, spawn request, and kernel trace must look like.
Everything that flows through the kernel must conform to one of these.

Schemas
-------
QA_TASK_SPEC.v1          — unit of work dispatched to an agent
QA_AGENT_SPEC.v1         — declaration of an agent's identity and capabilities
QA_AGENT_SPAWN_SPEC.v1   — request to create a new micro-agent
QA_KERNEL_TRACE_CERT.v1  — record of one full kernel cycle (certifiable artifact)

Validation
----------
Each schema has a validate(obj) function that returns (ok: bool, errors: list).
Validators are intentionally simple — no external deps (stdlib only).
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = {"certify", "experiment", "theorem", "spawn", "query", "synthesize"}
VALID_VERDICTS = {"CONSISTENT", "CONTRADICTS", "PARTIAL", "INCONCLUSIVE"}
VALID_ORBIT_FAMILIES = {"cosmos", "satellite", "singularity"}
VALID_RESULTS = {"PASS", "FAIL", "PENDING", "SKIPPED"}

SCHEMA_VERSIONS = {
    "task":         "QA_TASK_SPEC.v1",
    "agent":        "QA_AGENT_SPEC.v1",
    "spawn":        "QA_AGENT_SPAWN_SPEC.v1",
    "kernel_trace": "QA_KERNEL_TRACE_CERT.v1",
}


# ---------------------------------------------------------------------------
# QA_TASK_SPEC.v1
# ---------------------------------------------------------------------------

def make_task(
    task_type: str,
    description: str,
    inputs: Optional[Dict[str, Any]] = None,
    success_criteria: Optional[List[str]] = None,
    task_id: Optional[str] = None,
    priority: float = 1.0,
    requires_approval: bool = False,
    parent_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a conformant QA_TASK_SPEC.v1 dict."""
    import uuid
    return {
        "schema_version": SCHEMA_VERSIONS["task"],
        "task_id": task_id or str(uuid.uuid4())[:8],
        "task_type": task_type,
        "description": description,
        "inputs": inputs or {},
        "success_criteria": success_criteria or [],
        "priority": priority,
        "requires_approval": requires_approval,
        "parent_task_id": parent_task_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def validate_task(obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a QA_TASK_SPEC.v1 object. Returns (ok, errors)."""
    errors: List[str] = []
    if obj.get("schema_version") != SCHEMA_VERSIONS["task"]:
        errors.append(f"schema_version must be '{SCHEMA_VERSIONS['task']}'")
    if not obj.get("task_id"):
        errors.append("task_id is required")
    if obj.get("task_type") not in VALID_TASK_TYPES:
        errors.append(f"task_type must be one of {VALID_TASK_TYPES}")
    if not obj.get("description"):
        errors.append("description is required and must be non-empty")
    if not isinstance(obj.get("inputs", {}), dict):
        errors.append("inputs must be a dict")
    if not isinstance(obj.get("priority", 1.0), (int, float)):
        errors.append("priority must be numeric")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# QA_AGENT_SPEC.v1
# ---------------------------------------------------------------------------

def make_agent_spec(
    name: str,
    capabilities: List[str],
    cert_family: Optional[str],
    description: str,
    modulus: int = 9,
    initial_orbit: Optional[List[int]] = None,
    parent_certs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Construct a conformant QA_AGENT_SPEC.v1 dict."""
    return {
        "schema_version": SCHEMA_VERSIONS["agent"],
        "name": name,
        "capabilities": capabilities,
        "cert_family": cert_family,
        "description": description,
        "modulus": modulus,
        "initial_orbit": initial_orbit or [1, 1],
        "parent_certs": parent_certs or [],
        "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def validate_agent_spec(obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a QA_AGENT_SPEC.v1 object. Returns (ok, errors)."""
    errors: List[str] = []
    if obj.get("schema_version") != SCHEMA_VERSIONS["agent"]:
        errors.append(f"schema_version must be '{SCHEMA_VERSIONS['agent']}'")
    if not obj.get("name"):
        errors.append("name is required")
    caps = obj.get("capabilities", [])
    if not isinstance(caps, list) or len(caps) == 0:
        errors.append("capabilities must be a non-empty list")
    for cap in caps:
        if cap not in VALID_TASK_TYPES:
            errors.append(f"capability '{cap}' not in {VALID_TASK_TYPES}")
    if not obj.get("description"):
        errors.append("description is required")
    orbit = obj.get("initial_orbit", [1, 1])
    if not (isinstance(orbit, list) and len(orbit) == 2):
        errors.append("initial_orbit must be [b, e] (list of 2 ints)")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# QA_AGENT_SPAWN_SPEC.v1
# ---------------------------------------------------------------------------

def make_spawn_spec(
    required_capability: str,
    description: str,
    task_id: str,
    inputs_example: Optional[Dict[str, Any]] = None,
    validator_checks: Optional[List[str]] = None,
    requester_orbit: Optional[List[int]] = None,
    approved: bool = False,
) -> Dict[str, Any]:
    """Construct a conformant QA_AGENT_SPAWN_SPEC.v1 dict."""
    import uuid
    if required_capability not in VALID_TASK_TYPES:
        raise ValueError(f"required_capability must be one of {VALID_TASK_TYPES}")
    return {
        "schema_version": SCHEMA_VERSIONS["spawn"],
        "spawn_id": str(uuid.uuid4())[:8],
        "required_capability": required_capability,
        "description": description,
        "triggering_task_id": task_id,
        "cert_family_name": f"qa_{required_capability}_agent",
        "inputs_example": inputs_example or {},
        "validator_checks": validator_checks or [
            "V1: input schema valid",
            "V2: output is certifiable artifact",
            "V3: --self-test exits 0 returning {\"ok\": true}",
            "V4: fixtures include ≥1 PASS and ≥1 FAIL case",
        ],
        "gate_compliance": [0, 1, 2, 3, 4, 5],
        "requester_orbit": requester_orbit or [1, 1],
        "approved": approved,
        "implementation_target": "Codex",
        "spawned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def validate_spawn_spec(obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a QA_AGENT_SPAWN_SPEC.v1 object. Returns (ok, errors)."""
    errors: List[str] = []
    if obj.get("schema_version") != SCHEMA_VERSIONS["spawn"]:
        errors.append(f"schema_version must be '{SCHEMA_VERSIONS['spawn']}'")
    if obj.get("required_capability") not in VALID_TASK_TYPES:
        errors.append(f"required_capability must be one of {VALID_TASK_TYPES}")
    if not obj.get("description"):
        errors.append("description is required")
    if not obj.get("cert_family_name"):
        errors.append("cert_family_name is required")
    checks = obj.get("validator_checks", [])
    if not isinstance(checks, list) or len(checks) == 0:
        errors.append("validator_checks must be a non-empty list")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# QA_KERNEL_TRACE_CERT.v1
# ---------------------------------------------------------------------------

def make_kernel_trace(
    task_id: str,
    task_type: str,
    kernel_orbit: List[int],
    kernel_family: str,
    agent_name: Optional[str],
    ok: bool,
    verified: bool,
    learned: bool,
    spawn_required: bool,
    rho: float,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None,
    spawn_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a conformant QA_KERNEL_TRACE_CERT.v1 dict."""
    return {
        "schema_version": SCHEMA_VERSIONS["kernel_trace"],
        "task_id": task_id,
        "task_type": task_type,
        "kernel_orbit": kernel_orbit,
        "kernel_family": kernel_family,
        "agent_name": agent_name,
        "result": {
            "ok": ok,
            "verified": verified,
            "learned": learned,
            "spawn_required": spawn_required,
            "error": error,
        },
        "convergence": {
            "rho": rho,
            "orbit_family_score": {"cosmos": 1.0, "satellite": 0.5, "singularity": 0.0}.get(kernel_family, 0.0),
        },
        "spawn_id": spawn_id,
        "duration_ms": duration_ms,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def validate_kernel_trace(obj: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a QA_KERNEL_TRACE_CERT.v1 object. Returns (ok, errors)."""
    errors: List[str] = []
    if obj.get("schema_version") != SCHEMA_VERSIONS["kernel_trace"]:
        errors.append(f"schema_version must be '{SCHEMA_VERSIONS['kernel_trace']}'")
    if not obj.get("task_id"):
        errors.append("task_id is required")
    if obj.get("task_type") not in VALID_TASK_TYPES:
        errors.append(f"task_type must be one of {VALID_TASK_TYPES}")
    orbit = obj.get("kernel_orbit", [])
    if not (isinstance(orbit, list) and len(orbit) == 2):
        errors.append("kernel_orbit must be [b, e]")
    if obj.get("kernel_family") not in VALID_ORBIT_FAMILIES:
        errors.append(f"kernel_family must be one of {VALID_ORBIT_FAMILIES}")
    result = obj.get("result", {})
    if not isinstance(result.get("ok"), bool):
        errors.append("result.ok must be bool")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    """Run all schema validators against minimal valid examples."""
    errors_found: List[str] = []

    # Task
    task = make_task("certify", "test task", inputs={"validator_path": "foo.py"})
    ok, errs = validate_task(task)
    if not ok:
        errors_found.extend([f"task: {e}" for e in errs])

    # Invalid task
    ok_bad, _ = validate_task({"schema_version": "wrong", "task_type": "certify", "description": "x"})
    if ok_bad:
        errors_found.append("task: invalid task should have failed")

    # Agent spec
    agent = make_agent_spec("test_agent", ["certify"], None, "A test agent")
    ok, errs = validate_agent_spec(agent)
    if not ok:
        errors_found.extend([f"agent: {e}" for e in errs])

    # Spawn spec
    spawn = make_spawn_spec("theorem", "Prove claim X", "task123")
    ok, errs = validate_spawn_spec(spawn)
    if not ok:
        errors_found.extend([f"spawn: {e}" for e in errs])

    # Kernel trace
    trace = make_kernel_trace(
        task_id="t001", task_type="certify",
        kernel_orbit=[1, 1], kernel_family="cosmos",
        agent_name="cert_agent", ok=True, verified=True,
        learned=True, spawn_required=False, rho=0.0067,
    )
    ok, errs = validate_kernel_trace(trace)
    if not ok:
        errors_found.extend([f"trace: {e}" for e in errs])

    if errors_found:
        for e in errors_found:
            print(f"  FAIL: {e}")
        return False

    print('{"ok": true, "schemas": ["QA_TASK_SPEC.v1", "QA_AGENT_SPEC.v1", "QA_AGENT_SPAWN_SPEC.v1", "QA_KERNEL_TRACE_CERT.v1"]}')
    return True


if __name__ == "__main__":
    import sys
    import argparse
    parser = argparse.ArgumentParser(description="QA Lab protocol schema validator")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)
