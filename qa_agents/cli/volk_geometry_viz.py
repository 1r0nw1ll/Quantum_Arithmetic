"""
Auto-refactor: normalize formatting for volk_geometry_viz.py
"""

#!/usr/bin/env python3

import json
from pathlib import Path
import sys
BASE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE))
from projects.volk_triangle.geometry import bipolar_to_cartesian

OUT = BASE / 'artifacts' / 'plots'
OUT.mkdir(parents=True, exist_ok=True)

# Emit a small set of points for E/M circles (constant eta and rho)
def main():
    a = 6.0
    etas = [0.5, 1.0, 1.5]
    rhos = [0.5, 1.0, 1.5]
    data = {"e_circles": [], "m_circles": []}
    # Sample points on circles
    for eta in etas:
        pts=[]
        for t in [i*0.314 for i in range(0,21)]:
            x,y = bipolar_to_cartesian(eta, t, a)
            pts.append([x,y])
        data['e_circles'].append({"eta": eta, "points": pts})
    for rho in rhos:
        pts=[]
        for t in [i*0.314 for i in range(0,21)]:
            x,y = bipolar_to_cartesian(t, rho, a)
            pts.append([x,y])
        data['m_circles'].append({"rho": rho, "points": pts})
    out = OUT / 'volk_geometry_sample.json'
    out.write_text(json.dumps(data), encoding='utf-8')
    print(f'Wrote {out}')

if __name__ == '__main__':
    main()
