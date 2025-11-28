#!/usr/bin/env python3
"""
Scan local Raman spectra files and compute a lightweight QA mapping summary.

Inputs:
  - data/ (default): scans recursively for *.txt, *.csv, *.jdx
  - qa_data/raman/ (optional): additional scan path

Outputs:
  - artifacts/qa_raman_mapping.json (summary per file)
  - Console summary of top peaks and QA seed invariants/signatures

Assumptions:
  - Text files contain (x,y) numeric pairs (wavenumber, intensity)
  - Lines starting with # or ## are skipped
  - For JCAMP-DX-like files, the script extracts numeric pairs from lines, best-effort

Dependencies: numpy
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from qa_raman_effect import QATuple, to_triangle, signatures, stokes, antistokes, relative_shift, preset_crystals
from qa_io.jcamp_dx import load_jdx


DEFAULT_SCAN_DIRS = [Path('data'), Path('qa_data/raman')]
OUT_JSON = Path('artifacts/qa_raman_mapping.json')


def list_candidate_files(roots: List[Path], glob_pat: Optional[str], max_files: int) -> List[Path]:
    out: List[Path] = []
    for base in roots:
        if not base.exists():
            continue
        it = base.rglob(glob_pat) if glob_pat else base.rglob('*')
        for p in it:
            if not p.is_file():
                continue
            if p.suffix.lower() in ('.txt', '.csv', '.jdx'):
                out.append(p)
                if max_files and len(out) >= max_files:
                    return out
    return out


def parse_xy_file(path: Path) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        # Fallback to binary read then decode
        try:
            text = path.read_bytes().decode('latin-1', errors='ignore')
        except Exception:
            return None

    xs: List[float] = []
    ys: List[float] = []

    # JCAMP-DX
    if path.suffix.lower() == '.jdx':
        return load_jdx(path)

    # Heuristic: try CSV first if commas are common
    if path.suffix.lower() == '.csv' or text.count(',') > 50:
        for line in text.splitlines():
            if not line.strip():
                continue
            # skip headers
            if any(line.lower().startswith(h) for h in ('#', '##', 'x', 'wavenumber', 'shift')):
                continue
            parts = [p.strip() for p in line.split(',')]
            nums = []
            for p in parts[:2]:
                try:
                    nums.append(float(p))
                except Exception:
                    nums = []
                    break
            if len(nums) == 2:
                xs.append(nums[0]); ys.append(nums[1])
        if len(xs) >= 8:
            return np.array(xs, dtype=float), np.array(ys, dtype=float)
        # fallthrough to generic parser

    # Generic: read pairs of floats per line, skip comments
    float_pair = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*[,\t\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
    for line in text.splitlines():
        l = line.strip()
        if not l or l.startswith('#') or l.startswith('##'):
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


def find_top_peaks(x: np.ndarray, y: np.ndarray, k: int = 5, min_sep: float = 5.0) -> List[Tuple[float, float]]:
    # Simple local maxima
    if len(x) < 5:
        return []
    # Ensure sorted by x
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    peaks = []
    for i in range(1, len(x) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1]:
            peaks.append((x[i], y[i]))
    # Sort by intensity desc
    peaks.sort(key=lambda t: -t[1])
    # Non-maximum suppression by x separation
    selected: List[Tuple[float, float]] = []
    for px, py in peaks:
        if all(abs(px - qx) >= min_sep for qx, _ in selected):
            selected.append((px, py))
        if len(selected) >= k:
            break
    return selected


def label_from_filename(p: Path) -> str:
    name = p.name.lower()
    sp = str(p).lower()
    if 'diamond' in name:
        return 'diamond'
    if 'silicon' in name or re.search(r'\bsi\b', name):
        return 'silicon'
    if 'quartz' in name:
        return 'quartz'
    if 'calcite' in name:
        return 'calcite'
    if 'hematite' in name:
        return 'hematite'
    if 'graphite' in name:
        return 'graphite'
    if 'graphene' in name or 'graphene' in sp:
        return 'graphene'
    if 'mos2' in name or 'mos2' in sp or 'mo s2' in name or 'molybdenum disulfide' in name or 'molybdenite' in name or 'molybdenite' in sp:
        return 'mos2'
    if 'corundum' in name or 'al2o3' in name:
        return 'corundum'
    if 'anatase' in name:
        return 'anatase'
    if 'rutile' in name:
        return 'rutile'
    return 'unknown'


def modality_from_path(p: Path) -> str:
    name = p.name.lower()
    sp = str(p).lower()
    if 'raman' in name or 'raman' in sp:
        return 'Raman'
    if 'infrared' in name or 'ir' in name or 'infrared' in sp or 'ir' in sp:
        return 'IR'
    if 'xray' in name or 'xrd' in name or 'xray' in sp or 'xrd' in sp:
        return 'XRD'
    return 'unknown'


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', nargs='*', default=[], help='Directories to scan (default: data qa_data/raman)')
    ap.add_argument('--glob', type=str, default='', help='Optional glob pattern for filenames (e.g., *.txt)')
    ap.add_argument('--labels', type=str, default='', help='Comma-separated label filter (e.g., diamond,quartz)')
    ap.add_argument('--max-files', type=int, default=0, help='Maximum files to process (0 = no cap)')
    args = ap.parse_args(argv)

    roots = [Path(p) for p in args.roots] if args.roots else DEFAULT_SCAN_DIRS
    glob_pat = args.glob or None
    label_filter: Optional[Set[str]] = None
    if args.labels:
        label_filter = {s.strip().lower() for s in args.labels.split(',') if s.strip()}

    OUT_JSON.parent.mkdir(exist_ok=True, parents=True)
    results: List[Dict] = []

    files = list_candidate_files(roots, glob_pat, args.max_files)
    if not files:
        print("No candidate spectra found in data/ or qa_data/raman/")
        return

    print(f"Found {len(files)} candidate spectra files")

    # Optional calibration using diamond seed if a diamond file exists
    calib_s: Optional[float] = None
    for p in files:
        if label_from_filename(p) == 'diamond':
            xy = parse_xy_file(p)
            if not xy:
                continue
            x, y = xy
            peaks = find_top_peaks(x, y, k=3)
            if not peaks:
                continue
            # Assume primary diamond line is the strongest
            peak_cm = peaks[0][0]
            diamond = QATuple.from_b_e(1.0, 1.0)
            tri = to_triangle(diamond)
            if tri.C != 0:
                calib_s = peak_cm / tri.C
                print(f"Calibration from {p.name}: s ≈ {calib_s:.3f} cm^-1 per C-unit")
                break

    seeds = preset_crystals()  # Diamond, Graphene, Quartz, Silicon

    for p in files:
        xy = parse_xy_file(p)
        if not xy:
            continue
        x, y = xy
        peaks = find_top_peaks(x, y, k=5)
        label = label_from_filename(p)
        if label_filter is not None and label not in label_filter:
            continue

        entry: Dict = {
            'file': str(p),
            'label': label,
            'modality': modality_from_path(p),
            'n_points': int(len(x)),
            'top_peaks_cm-1': [float(px) for px, _ in peaks],
            'top_peak_ints': [float(py) for _, py in peaks],
        }

        # Attach QA seed summaries
        seed_summaries = {}
        for name, tau in seeds.items():
            tri = to_triangle(tau)
            sig = signatures(tau)
            scaled_C = (calib_s * tri.C) if calib_s is not None else None
            # Δe sidebands
            sb = {}
            for de in (-1.0, 1.0, 2.0):
                try:
                    child = antistokes(tau, -de) if de < 0 else stokes(tau, de)
                    sb[str(int(de))] = {
                        'C': to_triangle(child).C,
                        'rel_shift': relative_shift(tau, child),
                    }
                except Exception:
                    pass
            seed_summaries[name] = {
                'tuple': (tau.b, tau.e, tau.d, tau.a),
                'C': tri.C,
                'F': tri.F,
                'G': tri.G,
                'J': tri.J,
                'X': tri.X,
                'K': tri.K,
                'scaled_C_cm-1': scaled_C,
                'signatures': sig,
                'sidebands': sb,
            }
        entry['qa_seeds'] = seed_summaries

        results.append(entry)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'results': results, 'calibration_C_to_cm-1': calib_s}, f, indent=2)

    # Console summary
    print(f"Wrote {OUT_JSON}")
    for r in results[:6]:
        print(f"- {Path(r['file']).name}: peaks {r['top_peaks_cm-1'][:3]}")


if __name__ == '__main__':
    main()
