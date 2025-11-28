#!/usr/bin/env python3
"""Quick Rust integration smoke test.
Build with `make rust-py-build` first, then run:

  QA_USE_RUST=1 python scripts/test_rust_integration.py
"""
import os
os.environ.setdefault('QA_USE_RUST', '1')

try:
    import qa_lab_rs
    print('qa_lab_rs.ping():', getattr(qa_lab_rs, 'ping', lambda: 'missing')())
except Exception as e:
    print('Failed to import qa_lab_rs:', e)

from qa_rust_bridge import rust_available, compute_all
import torch

print('rust_available():', rust_available())

b,e,d,a = torch.tensor([1.0]), torch.tensor([1.0]), torch.tensor([2.0]), torch.tensor([3.0])
out = compute_all(b,e,d,a)
if out is None:
    print('compute_all returned None (bridge disabled or module unavailable)')
else:
    flat = {k: float(out[k].reshape(-1)[0]) for k in ['J','K','X','W','Y','Z','C','F','G']}
    print('invariants:', flat)

