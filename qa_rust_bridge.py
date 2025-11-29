"""
qa_rust_bridge.py - Optional Rust acceleration for QA Lab

This bridge tries to import the PyO3 extension module built from the Rust port
(`qa_lab_rs`) and exposes helpers that return torch tensors with the same shape
as the inputs. When the Rust module is not available or disabled, functions
return None and callers should fall back to pure-Python implementations.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

# Default to Rust backend enabled (set QA_USE_RUST=0 to disable)
_USE_RUST = os.getenv("QA_USE_RUST", "1") == "1"
_RS = None

def rust_available() -> bool:
    global _RS
    if not _USE_RUST:
        return False
    if _RS is not None:
        return True
    try:
        # Common locations: project root target/release copy or installed wheel
        import importlib
        _mod = importlib.import_module("qa_lab_rs")
        # basic health check if present
        if hasattr(_mod, "ping") and _mod.ping() != "qa_lab_rs:ok":
            return False
        globals()["_RS"] = _mod
        return True
    except Exception:
        return False

def compute_all(b, e, d, a) -> Optional[Dict[str, "torch.Tensor"]]:
    """Compute full QA bundle invariants via Rust.

    Args:
        b, e, d, a: torch.Tensor shapes broadcastable to a common shape.

    Returns:
        dict with keys J,K,X,W,Y,Z,C,F,G as tensors, or None if unavailable.
    """
    if not rust_available():
        return None
    try:
        import torch  # import here to avoid top-level dependency
        import numpy as np

        # Broadcast to common shape
        b_t = torch.as_tensor(b)
        e_t = torch.as_tensor(e)
        d_t = torch.as_tensor(d)
        a_t = torch.as_tensor(a)
        shape = torch.broadcast_shapes(b_t.shape, e_t.shape, d_t.shape, a_t.shape)

        b_b = b_t.expand(shape).contiguous().detach().cpu()
        e_b = e_t.expand(shape).contiguous().detach().cpu()
        d_b = d_t.expand(shape).contiguous().detach().cpu()
        a_b = a_t.expand(shape).contiguous().detach().cpu()

        # Prefer high-performance NumPy batch path if available
        # Try closure-optimized path if: env enabled or quick heuristic passes
        assume_closure = os.getenv("QA_ASSUME_CLOSURE", "0") == "1"
        has_closure_fn = hasattr(_RS, 'compute_bundle_batch_numpy_closure_py')
        if hasattr(_RS, 'compute_bundle_batch_numpy_py') or has_closure_fn:
            b_np = b_b.numpy().astype(np.float64, copy=False).reshape(-1)
            e_np = e_b.numpy().astype(np.float64, copy=False).reshape(-1)
            d_np = d_b.numpy().astype(np.float64, copy=False).reshape(-1)
            a_np = a_b.numpy().astype(np.float64, copy=False).reshape(-1)
            batch = None
            if has_closure_fn and (assume_closure or _looks_like_closure(b_np, e_np, d_np, a_np)):
                batch = _RS.compute_bundle_batch_numpy_closure_py(b_np, e_np)
            else:
                batch = _RS.compute_bundle_batch_numpy_py(b_np, e_np, d_np, a_np)
            keys = ("J","K","X","W","Y","Z","C","F","G")
            device = b_t.device if hasattr(b_t, "device") else None
            dtype = b_t.dtype if hasattr(b_t, "dtype") else torch.float32
            out = {}
            for k in keys:
                arr = batch[k]  # numpy.ndarray float64 1D
                t = torch.from_numpy(arr).reshape(shape).to(dtype)
                if device is not None:
                    t = t.to(device)
                out[k] = t
            return out

        # Fallback to Python-list batch or per-element path
        b_list = b_b.reshape(-1).double().tolist()
        e_list = e_b.reshape(-1).double().tolist()
        d_list = d_b.reshape(-1).double().tolist()
        a_list = a_b.reshape(-1).double().tolist()

        if hasattr(_RS, 'compute_bundle_batch_py'):
            batch_results = _RS.compute_bundle_batch_py(b_list, e_list, d_list, a_list)
            out_lists = {k: [] for k in ("J","K","X","W","Y","Z","C","F","G")}
            for dct in batch_results:
                for k in out_lists:
                    out_lists[k].append(float(dct[k]))
        else:
            out_lists = {k: [] for k in ("J","K","X","W","Y","Z","C","F","G")}
            for bi, ei, di, ai in zip(b_list, e_list, d_list, a_list):
                dct = _RS.compute_bundle_py(bi, ei, di, ai)
                for k in out_lists:
                    out_lists[k].append(float(dct[k]))

        device = b_t.device if hasattr(b_t, "device") else None
        dtype = b_t.dtype if hasattr(b_t, "dtype") else torch.float32
        out = {}
        for k, lst in out_lists.items():
            t = torch.tensor(lst, dtype=torch.float64)
            t = t.reshape(shape).to(dtype)
            if device is not None:
                t = t.to(device)
            out[k] = t
        return out
    except Exception:
        return None


def _looks_like_closure(b_np, e_np, d_np, a_np, tol=1e-9):
    """Cheap heuristic: sample a few positions to test d≈b+e and a≈e+d."""
    try:
        n = b_np.shape[0]
        if n == 0:
            return False
        # Sample at most 8 points uniformly
        idxs = [0, n//7, (2*n)//7, (3*n)//7, (4*n)//7, (5*n)//7, (6*n)//7, n-1]
        idxs = [i for i in idxs if 0 <= i < n]
        for i in idxs:
            if abs(d_np[i] - (b_np[i] + e_np[i])) > tol:
                return False
            if abs(a_np[i] - (e_np[i] + d_np[i])) > tol:
                return False
        return True
    except Exception:
        return False
