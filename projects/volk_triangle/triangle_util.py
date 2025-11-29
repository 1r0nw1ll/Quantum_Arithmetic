"""
Auto-refactor: normalize formatting for triangle_util.py
"""

#!/usr/bin/env python3
"""
Volk–Grant QA Triangle utilities

Provides helpers to compute QA triangle (C,F, G) and torus parameters
from (b,e) using qa_toroid_sumproduct.
"""

from typing import Dict
from qa_toroid_sumproduct import (
    qa_triangle_from_tuple,
    torus_from_triangle,
)

def compute_summary(b: float, e: float) -> Dict:
    d = b + e
    a = e + d
    tri = qa_triangle_from_tuple(b, e, d, a)
    tor = torus_from_triangle(tri)
    return {
        "tuple": {"b": b, "e": e, "d": d, "a": a},
        "triangle": {"C": tri.C, "F": tri.F, "G": tri.G},
        "torus": {"a": tor.a, "R": tor.R, "r": tor.r, "b": tor.b, "k": tor.k},
    }

if __name__ == "__main__":
    import sys, json
    b = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    e = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    print(json.dumps(compute_summary(b, e), indent=2))
