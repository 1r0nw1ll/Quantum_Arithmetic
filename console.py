"""
qa_lab.operator — CLI operator console for the QA Lab kernel.

Usage:
    python -m qa_lab.operator status
    python -m qa_lab.operator cycles [N]
    python -m qa_lab.operator queue
    python -m qa_lab.operator approve <task_id>
    python -m qa_lab.operator reject <task_id>
    python -m qa_lab.operator stub <task_id>       # generate agent stub from spawn spec
    python -m qa_lab.operator close <task_id>      # full bootstrap closure: approve+stub+register+rerun
    python -m qa_lab.operator inject "<text>"      # inject context for next SYNTHESIZE cycle

This console reads the persisted spawn_queue from disk and the results_log.jsonl.
It does not require a running kernel instance — it operates on the persisted state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_QA_LAB_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_LAB_DIR.parent
_SPAWN_DIR = _QA_LAB_DIR / "kernel" / "spawn_queue"
_RESULTS_LOG = _QA_LAB_DIR / "kernel" / "results_log.jsonl"
_CONTEXT_FILE = _QA_LAB_DIR / "kernel" / "injected_context.txt"


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------

def _load_spawn_specs() -> list:
    if not _SPAWN_DIR.exists():
        return []
    specs = []
    for f in sorted(_SPAWN_DIR.glob("spawn_*.json")):
        try:
            specs.append(json.loads(f.read_text()))
        except Exception:
            pass
    return specs


def _load_results(n: int = 10) -> list:
    if not _RESULTS_LOG.exists():
        return []
    lines = _RESULTS_LOG.read_text(encoding="utf-8").strip().split("\n")
    results = []
    for line in lines:
        if line.strip():
            try:
                results.append(json.loads(line))
            except Exception:
                pass
    return results[-n:]


def _find_spec(task_id: str) -> tuple[dict | None, Path | None]:
    if not _SPAWN_DIR.exists():
        return None, None
    p = _SPAWN_DIR / f"spawn_{task_id}.json"
    if not p.exists():
        # search all
        for f in _SPAWN_DIR.glob("spawn_*.json"):
            try:
                spec = json.loads(f.read_text())
                if spec.get("task_id") == task_id:
                    return spec, f
            except Exception:
                pass
        return None, None
    return json.loads(p.read_text()), p


def _save_spec(spec: dict, path: Path) -> None:
    path.write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")), encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status(_args: list) -> None:
    specs = _load_spawn_specs()
    results = _load_results(50)
    pending = [s for s in specs if not s.get("approved", True)]
    approved = [s for s in specs if s.get("approved", True)]
    print("=== QA Lab Operator Console ===")
    print(f"Spawn specs total:   {len(specs)}")
    print(f"  pending approval:  {len(pending)}")
    print(f"  approved:          {len(approved)}")
    print(f"Cycles logged:       {len(results)}")
    if results:
        last = results[-1]
        print(f"Last cycle:          type={last.get('task_type','?')}  ok={last.get('ok')}  orbit={last.get('orbit_family','?')}")


def cmd_cycles(args: list) -> None:
    n = int(args[0]) if args else 10
    results = _load_results(n)
    print(f"=== Last {len(results)} cycles ===")
    for i, r in enumerate(results, 1):
        verdict = r.get("output", {}).get("verdict", "-")
        print(f"  [{i:2d}] {r.get('task_type','?'):12s}  ok={str(r.get('ok',False)):5s}  "
              f"verdict={verdict:15s}  orbit={r.get('orbit_family','?'):12s}  "
              f"task_id={r.get('task_id','?')[:8]}")


def cmd_queue(_args: list) -> None:
    specs = _load_spawn_specs()
    if not specs:
        print("Spawn queue: empty")
        return
    print(f"=== Spawn queue ({len(specs)} specs) ===")
    for s in specs:
        status = "APPROVED" if s.get("approved") else "PENDING "
        print(f"  [{status}] {s.get('task_id','?')[:12]}  capability={s.get('required_capability','?'):12s}  "
              f"desc={s.get('description','')[:50]}")


def cmd_approve(args: list) -> None:
    if not args:
        print("Usage: approve <task_id>")
        return
    task_id = args[0]
    spec, path = _find_spec(task_id)
    if spec is None:
        print(f"Not found: {task_id}")
        return
    if spec.get("approved"):
        print(f"Already approved: {task_id}")
        return
    spec["approved"] = True
    spec["pending_approval"] = False
    import datetime
    spec["approved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _save_spec(spec, path)
    print(f"Approved: {task_id}  ({spec.get('required_capability','?')} agent)")


def cmd_reject(args: list) -> None:
    if not args:
        print("Usage: reject <task_id>")
        return
    task_id = args[0]
    spec, path = _find_spec(task_id)
    if spec is None:
        print(f"Not found: {task_id}")
        return
    path.unlink()
    print(f"Rejected and removed: {task_id}")


def cmd_stub(args: list) -> None:
    """Generate an agent stub .py from an approved spawn spec."""
    if not args:
        print("Usage: stub <task_id>")
        return
    task_id = args[0]
    spec, _ = _find_spec(task_id)
    if spec is None:
        print(f"Not found: {task_id}")
        return
    if not spec.get("approved"):
        print(f"Not approved yet. Run: approve {task_id}")
        return
    _write_stub(spec)


def _write_stub(spec: dict) -> Path:
    import re
    capability = spec.get("required_capability", "query")
    agent_name = spec.get("agent_name") or f"{capability}_agent"
    agent_name = re.sub(r"[^a-z0-9_]", "_", agent_name.lower())
    class_name = "".join(w.capitalize() for w in agent_name.split("_"))

    import datetime
    agents_dir = str(_QA_LAB_DIR / "agents")
    stub = f'''"""
{agent_name} — auto-generated stub from QA_AGENT_SPAWN_SPEC.v1
Generated:    {datetime.datetime.now(datetime.timezone.utc).isoformat()}
Spawn reason: {spec.get("description", "unhandled task")}
Task ID:      {spec.get("task_id", "?")}

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
            observation_body=f"Stub response for: {{getattr(task, 'description', '')}}",
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
    out_path = _QA_LAB_DIR / "agents" / f"{agent_name}.py"
    out_path.write_text(stub, encoding="utf-8")
    print(f"Stub written: {out_path.relative_to(_REPO_ROOT)}")
    print(f"  Class: {class_name}  capability: {capability}")
    print(f"  Next: implement handle(), then register with kernel for TaskType.{capability.upper()}")
    return out_path


def cmd_close(args: list) -> None:
    """Full bootstrap closure: approve → stub → test-import → report."""
    if not args:
        print("Usage: close <task_id>")
        return
    task_id = args[0]
    spec, path = _find_spec(task_id)
    if spec is None:
        print(f"Not found: {task_id}")
        return

    print(f"=== Bootstrap closure: {task_id} ===")

    # Step 1: approve
    if not spec.get("approved"):
        spec["approved"] = True
        spec["pending_approval"] = False
        import datetime
        spec["approved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _save_spec(spec, path)
        print("  [1/3] Approved ✓")
    else:
        print("  [1/3] Already approved ✓")

    # Step 2: write stub
    stub_path = _write_stub(spec)
    print(f"  [2/3] Stub written: {stub_path.name} ✓")

    # Step 3: validate import
    import importlib.util
    spec_mod = importlib.util.spec_from_file_location(stub_path.stem, stub_path)
    mod = importlib.util.module_from_spec(spec_mod)
    if str(_QA_LAB_DIR / "agents") not in sys.path:
        sys.path.insert(0, str(_QA_LAB_DIR / "agents"))
    if str(_QA_LAB_DIR) not in sys.path:
        sys.path.insert(0, str(_QA_LAB_DIR))
    try:
        spec_mod.loader.exec_module(mod)
        print(f"  [3/3] Import OK ✓")
    except Exception as exc:
        print(f"  [3/3] Import FAILED: {exc}")
        return

    capability = spec.get("required_capability", "query")
    print()
    print(f"Bootstrap closure COMPLETE for capability: {capability}")
    print(f"Register with kernel:")
    print(f"  kernel.register_agent(TaskType.{capability.upper()}, {stub_path.stem.replace('_agent','').capitalize()}Agent())")
    print(f"Then rerun the original task to close the loop.")


def cmd_inject(args: list) -> None:
    """Append context text to the injected_context file for next SYNTHESIZE cycle."""
    if not args:
        print("Usage: inject \"<context text>\"")
        return
    text = " ".join(args)
    _CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONTEXT_FILE, "a", encoding="utf-8") as f:
        import datetime
        f.write(f"\n[{datetime.datetime.now(datetime.timezone.utc).isoformat()}]\n{text}\n")
    print(f"Context injected ({len(text)} chars) → {_CONTEXT_FILE.name}")
    print("Kernel will consume this on next SYNTHESIZE cycle via kernel.inject_context().")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "status": cmd_status,
    "cycles": cmd_cycles,
    "queue": cmd_queue,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "stub": cmd_stub,
    "close": cmd_close,
    "inject": cmd_inject,
}


def main(argv: list | None = None) -> None:
    args = (argv or sys.argv)[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[cmd](args[1:])


if __name__ == "__main__":
    main()
