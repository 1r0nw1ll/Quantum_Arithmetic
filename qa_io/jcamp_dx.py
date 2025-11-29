"""
Minimal JCAMP-DX loader (best-effort) for XY pairs.

Parses .jdx files by ignoring header lines starting with '##' and extracting
numeric pairs (x,y) from lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional, List
import re
import numpy as np


def load_jdx(path: Path) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        try:
            text = path.read_bytes().decode('latin-1', errors='ignore')
        except Exception:
            return None

    xs: List[float] = []
    ys: List[float] = []
    float_pair = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*[,\t\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
    for line in text.splitlines():
        l = line.strip()
        if not l or l.startswith('##'):
            continue
        m = float_pair.search(l)
        if m:
            try:
                xs.append(float(m.group(1)))
                ys.append(float(m.group(2)))
            except Exception:
                continue
    if len(xs) >= 8:
        return np.array(xs, dtype=float), np.array(ys, dtype=float)
    return None

