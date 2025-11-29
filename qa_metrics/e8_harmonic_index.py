#!/usr/bin/env python3
from pathlib import Path
import json
from datetime import datetime
from typing import Dict
try:
    from qa_e8_alignment import compute_harmonic_index as _compute
except Exception:
    def _compute(e8_score: float, loss: float) -> float:
        import math
        return float(e8_score) * math.exp(-1.0 * float(loss))
LOG = Path('logs') / 'metrics_e8.jsonl'
LOG.parent.mkdir(parents=True, exist_ok=True)

def compute_harmonic_index(e8_score: float, loss: float) -> float:
    return _compute(e8_score, loss)

def log_harmonic_index(tag: str, e8: float, loss: float, extra: Dict=None) -> float:
    hi = compute_harmonic_index(e8, loss)
    rec = {"ts": datetime.now().isoformat(), "tag": tag, "e8": e8, "loss": loss, "harmonic_index": hi}
    if extra: rec.update(extra)
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec)+'\n')
    return hi
