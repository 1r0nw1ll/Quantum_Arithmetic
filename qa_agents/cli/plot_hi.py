"""
Auto-refactor: normalize formatting for plot_hi.py
"""

#!/usr/bin/env python3
"""
Plot (or summarize) E8 Harmonic Index from logs/metrics_e8.jsonl.
If matplotlib is not available, writes a JSON summary instead of a PNG.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent.parent
LOG = BASE / 'logs' / 'metrics_e8.jsonl'
OUT = BASE / 'artifacts' / 'plots'
OUT.mkdir(parents=True, exist_ok=True)

records = []
if LOG.exists():
    with open(LOG, 'r') as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except Exception:
                continue

if not records:
    print("No HI logs found.")
    raise SystemExit(0)

# Extract series
xs = list(range(len(records)))
ys = [float(r.get('harmonic_index', 0.0)) for r in records]

def write_summary():
    out = OUT / 'hi_trend_summary.json'
    summary = {
        'count': len(ys),
        'min': min(ys),
        'max': max(ys),
        'mean': sum(ys)/len(ys) if ys else 0.0,
    }
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Wrote {out}")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.figure(figsize=(6,3))
    plt.plot(xs, ys, marker='o')
    plt.title('E8 Harmonic Index Trend')
    plt.xlabel('step')
    plt.ylabel('HI')
    plt.tight_layout()
    out = OUT / 'hi_trend.png'
    plt.savefig(out, dpi=150)
    print(f"Wrote {out}")
except Exception:
    write_summary()

