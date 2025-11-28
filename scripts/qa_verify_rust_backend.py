#!/usr/bin/env python3
"""
Verify Rust backend is active and matches Python QA mapping for invariants.

Checks:
  - qa_lab_rs importable (PyO3 extension present)
  - compute_bundle_py matches qa_raman_effect.to_triangle for several seeds
  - No torch/tensorflow imports in QA scripts used in step 1
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib

def check_rust() -> bool:
    try:
        qa_lab_rs = importlib.import_module('qa_lab_rs')
        ok = getattr(qa_lab_rs, 'ping', lambda: '')() == 'qa_lab_rs:ok'
        print(f"qa_lab_rs import: {ok}")
        return ok
    except Exception as e:
        print(f"qa_lab_rs import failed: {e}")
        return False

def compare_invariants() -> bool:
    from qa_raman_effect import QATuple, to_triangle
    qa_lab_rs = importlib.import_module('qa_lab_rs')

    seeds = [(1.0,1.0),(1.0,2.0),(2.0,3.0),(1.0,3.0)]
    tol = 1e-9
    ok_all = True
    for b,e in seeds:
        t = QATuple.from_b_e(b,e)
        tri = to_triangle(t)
        rb = qa_lab_rs.compute_bundle_py(b,e,t.d,t.a)
        mismatches = []
        for k_py, v_py in (('J', t.b*t.d), ('K', t.d*t.a), ('X', t.d*t.e),
                           ('C', 2*t.d*t.e), ('F', t.b*t.a), ('G', t.e*t.e + t.d*t.d)):
            v_rs = float(rb[k_py])
            if abs(v_rs - v_py) > tol:
                mismatches.append((k_py, v_py, v_rs))
        if mismatches:
            print(f"Seed (b={b},e={e}) mismatch: {mismatches}")
            ok_all = False
        else:
            print(f"Seed (b={b},e={e}) OK")
    return ok_all

def grep_no_torch_tf() -> None:
    import subprocess
    try:
        out = subprocess.check_output(['bash','-lc',
          'grep -RIn "import torch\|tensorflow\|keras" scripts qa_raman_effect.py || true'
        ], text=True)
        print("Torch/TF imports found in scripts?\n" + (out or "<none>"))
    except Exception as e:
        print(f"grep failed: {e}")

def main() -> None:
    rust_ok = check_rust()
    inv_ok = compare_invariants() if rust_ok else False
    grep_no_torch_tf()
    if rust_ok and inv_ok:
        print("Rust backend verified and invariants match Python mapping.")
    else:
        print("Rust verification failed; see messages above.")

if __name__ == '__main__':
    main()

