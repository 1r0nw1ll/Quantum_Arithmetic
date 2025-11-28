"""
Auto-refactor: normalize formatting for generate_volk_triangle_dataset.py
"""

#!/usr/bin/env python3
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projects.volk_triangle.triangle_util import compute_summary

OUT = Path('qa_data/volk_triangle_dataset.jsonl')
OUT.parent.mkdir(parents=True, exist_ok=True)

with open(OUT, 'w') as f:
    for b in [1,2,3,5]:
        for e in [1,2,3,5]:
            s = compute_summary(float(b), float(e))
            f.write(json.dumps(s)+'
')
print(f'Wrote {OUT}')
