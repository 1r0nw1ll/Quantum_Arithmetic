"""
Auto-refactor: normalize formatting for simulate_hi_logging.py
"""

#!/usr/bin/env python3
"""
Simulate E8 Harmonic Index logging without torch.

Reads qa_data/volk_triangle_dataset.jsonl (if present) and logs several HI entries
to logs/metrics_e8.jsonl using qa_metrics.e8_harmonic_index.log_harmonic_index.
"""
import json
from pathlib import Path
from datetime import datetime

try:
    from qa_metrics.e8_harmonic_index import log_harmonic_index, compute_harmonic_index
except Exception:
    raise SystemExit("qa_metrics.e8_harmonic_index not available")

DATA = Path('qa_data/volk_triangle_dataset.jsonl')
if not DATA.exists():
    print("Dataset not found; skipping HI simulation.")
    raise SystemExit(0)

# Read a handful of entries
rows = []
with open(DATA, 'r') as f:
    for i, line in enumerate(f):
        if i >= 8:
            break
        try:
            rows.append(json.loads(line))
        except Exception:
            continue

# Simulate a decreasing loss schedule
losses = [1.2, 1.0, 0.8, 0.6, 0.55, 0.5, 0.45, 0.4]
for i, (row, loss) in enumerate(zip(rows, losses)):
    tri = row.get('triangle', {})
    C, F, G = tri.get('C', 0.0), tri.get('F', 0.0), tri.get('G', 0.0)
    # crude proxy for e8 score: normalize C,F,G and take G weight
    total = (abs(C) + abs(F) + abs(G)) or 1.0
    e8_score = float(abs(G) / total)
    tag = f"sim_epoch_{i}"
    hi = log_harmonic_index(tag, e8_score, float(loss), {'note': 'simulated', 'ts': datetime.now().isoformat()})
    print(f"HI {tag}: e8={e8_score:.4f} loss={loss:.3f} -> {hi:.4f}")

