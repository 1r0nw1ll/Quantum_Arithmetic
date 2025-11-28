QA Lab – Rust Port Integration (Python Bridge)

Overview
- The Rust port now exposes a minimal PyO3 extension module named `qa_lab_rs`.
- Python code can optionally call into Rust to compute QA invariants via a small bridge (`qa_rust_bridge.py`).
- The integration is opt-in and safe: if Rust is unavailable, Python falls back automatically.

What’s Included
- Rust PyO3 module: src/lib.rs defines `qa_lab_rs` with `compute_bundle_py(b,e,d,a)` and `ping()`.
- Python bridge: `qa_rust_bridge.py` provides `rust_available()` and `compute_all(b,e,d,a)` returning torch tensors.
- Encoder integration: `qa_jepa_encoder.py` will use Rust for invariants when `QA_USE_RUST=1` and the module imports.
- Makefile target: `make rust-py-build` builds the shared object and copies it to an importable path.

Build Instructions
1) Ensure Rust toolchain is installed (rustup/cargo).
2) Build the extension:
   make rust-py-build
   - On Linux, this places `qa_lab_rs.so` at the repo root for direct import.
3) Verify import:
   python - <<'PY'
   import qa_lab_rs; print(qa_lab_rs.ping())
   PY

Enable in Python
Set the environment variable to opt in:
  export QA_USE_RUST=1

Then any code path that computes invariants through `QAEncoder` will try to use Rust first and fall back automatically.

Quick Functional Test
python - <<'PY'
import os
os.environ['QA_USE_RUST'] = '1'
from qa_rust_bridge import rust_available, compute_all
import torch
print('rust_available:', rust_available())
b,e,d,a = [1.0],[1.0],[2.0],[3.0]
out = compute_all(torch.tensor(b), torch.tensor(e), torch.tensor(d), torch.tensor(a))
print({k: float(out[k].reshape(-1)[0]) for k in ['J','K','X','W','Y','Z','C','F','G']})
PY

Notes
- This initial bridge computes invariants per element from Python; it is correct but not yet maximally fast.
- Future work: add batch APIs in Rust to minimize Python↔Rust overhead and wire more functions (e.g., E8 alignment).
- The integration is non-invasive: disabling `QA_USE_RUST` reverts to pure Python automatically.

