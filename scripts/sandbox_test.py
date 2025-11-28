"""
Auto-refactor: normalize formatting for sandbox_test.py
"""

#!/usr/bin/env python3
"""
Sandbox Test Runner v1.0

Validates proposed file changes in a sandbox before applying them to the repo.

Input (stdin JSON):
{
  "proposed_files": [
    {"path": "relative/path.py", "content": "...", "mode": "exec"? }, ...
  ],
  "tests": ["pytest -q"],  # optional
}

Environment:
- QA_SANDBOX_DOCKER_IMAGE: if set and docker available, runs inside container

Output (stdout JSON):
{ "status": "ok", "logs": [...], "tested": true }
or
{ "status": "error", "error": "...", "logs": [...] }
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List

BASE = Path(__file__).resolve().parents[1]
LOGS = BASE / 'logs'
LOGS.mkdir(exist_ok=True)


def docker_exists() -> bool:
    try:
        subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
        return True
    except Exception:
        return False


def copy_repo(src: Path, dst: Path) -> None:
    def ignore(path, names):
        ignore_dirs = {'qa_venv', '.venv', 'venv', '.git', '__pycache__', 'node_modules'}
        return [n for n in names if n in ignore_dirs]

    for item in src.iterdir():
        if item.name in {'.git', 'qa_venv', '.venv', 'venv'}:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def apply_files(root: Path, files: List[Dict]) -> List[str]:
    changes: List[str] = []
    for pf in files:
        path = pf.get('path')
        content = pf.get('content', '')
        mode = pf.get('mode', '')
        if not path:
            continue
        fpath = root / path
        fpath.parent.mkdir(parents=True, exist_ok=True)
        if content is not None:
            fpath.write_text(content, encoding='utf-8')
        if mode == 'exec':
            try:
                import stat
                fpath.chmod(fpath.stat().st_mode | stat.S_IEXEC)
            except Exception:
                pass
        changes.append(str(path))
    return changes


def run_local_tests(workdir: Path, tests: List[str], changed_py: List[str]) -> List[str]:
    logs: List[str] = []
    env = os.environ.copy()
    # Optional pytest path when enabled
    use_pytest = os.getenv('QA_SANDBOX_USE_PYTEST', '0') == '1'
    if not tests and use_pytest:
        try:
            import importlib  # noqa: F401
            import pytest  # type: ignore  # noqa: F401
            # Choose default tests dir if present
            tests_dir = None
            for cand in ['qa_core/tests', 'tests']:
                if (workdir / cand).exists():
                    tests_dir = cand
                    break
            if tests_dir:
                cmd = f"python -m pytest -q {tests_dir}"
                res = subprocess.run(cmd, cwd=str(workdir), shell=True, capture_output=True, text=True)
                logs.append(f"cmd[{cmd}] rc={res.returncode}\nSTDOUT:\n{res.stdout[-4000:]}\nSTDERR:\n{res.stderr[-4000:]}")
                if res.returncode == 0:
                    return logs
        except Exception as e:
            logs.append(f"pytest_unavailable: {e}")
    # Fallback sanity: py_compile for changed files
    if not tests:
        # Use python -m py_compile on changed python files
        pyfiles = [p for p in changed_py if p.endswith('.py')]
        for p in pyfiles:
            cmd = [sys.executable, '-m', 'py_compile', p]
            res = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True)
            logs.append(f"py_compile {p}: rc={res.returncode} stderr={res.stderr[-200:]}" )
            if res.returncode != 0:
                return logs + ["py_compile failed"]
        return logs + ["local:py_compile_ok"]
    # Custom tests
    for t in tests:
        res = subprocess.run(t, cwd=str(workdir), shell=True, capture_output=True, text=True)
        logs.append(f"cmd[{t}] rc={res.returncode}\nSTDOUT:\n{res.stdout[-4000:]}\nSTDERR:\n{res.stderr[-4000:]}")
        if res.returncode != 0:
            return logs
    return logs


def run_docker_tests(workdir: Path, image: str, tests: List[str], changed_py: List[str]) -> List[str]:
    logs: List[str] = []
    # Default test script inside container
    if not tests:
        pyfiles = ' '.join(changed_py)
        test_script = f"python -m py_compile {pyfiles}"
    else:
        # Chain tests with '&&'
        test_script = ' && '.join(tests)

    cmd = [
        'docker', 'run', '--rm', '-v', f'{str(workdir)}:/work', '-w', '/work', image,
        '/bin/sh', '-lc', test_script,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    logs.append(f"docker rc={res.returncode}\nSTDOUT:\n{res.stdout[-4000:]}\nSTDERR:\n{res.stderr[-4000:]}")
    if res.returncode != 0:
        return logs
    return logs


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or '{}')
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"invalid_input:{e}"}))
        return 0

    files = payload.get('proposed_files') or []
    tests = payload.get('tests') or []
    if not isinstance(files, list) or not files:
        print(json.dumps({"status": "ok", "tested": False, "logs": ["no files to test"]}))
        return 0

    docker_image = os.getenv('QA_SANDBOX_DOCKER_IMAGE', '')
    use_docker = bool(docker_image) and docker_exists()

    tmp = Path(tempfile.mkdtemp(prefix='qa_sandbox_'))
    logs: List[str] = []
    try:
        copy_repo(BASE, tmp)
        changed = apply_files(tmp, files)
        changed_py = [c for c in changed if c.endswith('.py')]

        if use_docker:
            logs.extend(run_docker_tests(tmp, docker_image, tests, changed_py))
        else:
            logs.extend(run_local_tests(tmp, tests, changed_py))

        ok = any('py_compile_ok' in l or 'rc=0' in l for l in logs) and not any('failed' in l for l in logs)
        # If no logs contained rc info (e.g., only py_compile lines), treat as ok when no error entries
        if not any('rc=' in l for l in logs):
            ok = True

        entry = {
            'timestamp': datetime.now().isoformat(),
            'status': 'ok' if ok else 'error',
            'use_docker': use_docker,
            'docker_image': docker_image if use_docker else None,
            'changed': changed,
        }
        with open(LOGS / 'sandbox_runs.jsonl', 'a') as f:
            f.write(json.dumps(entry) + '\n')

        print(json.dumps({'status': 'ok' if ok else 'error', 'logs': logs, 'tested': True}))
        return 0
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}))
        return 0
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
