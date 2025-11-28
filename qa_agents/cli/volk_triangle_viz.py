"""
Auto-refactor: normalize formatting for volk_triangle_viz.py
"""

#!/usr/bin/env python3
"""
Volk–Grant QA Triangle visualization helper.
Writes a JSON summary for default (b,e)=(1,2) and attempts a simple plot.
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE))
from projects.volk_triangle.triangle_util import compute_summary
OUT_DIR = BASE / "artifacts" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    summary = compute_summary(1.0, 2.0)
    out_json = OUT_DIR / "volk_triangle_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")

    # Optional plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        tri = summary["triangle"]
        labels = ["C", "F", "G"]
        values = [tri["C"], tri["F"], tri["G"]]
        plt.figure(figsize=(5,3))
        plt.bar(labels, values)
        plt.title("Volk–Grant QA Triangle (b=1,e=2)")
        plt.tight_layout()
        out_png = OUT_DIR / "volk_triangle_summary.png"
        plt.savefig(out_png, dpi=150)
        print(f"Wrote {out_png}")
    except Exception as e:
        print(f"Plot skipped: {e}")

if __name__ == "__main__":
    main()
