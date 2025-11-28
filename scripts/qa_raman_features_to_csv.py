#!/usr/bin/env python3
"""
Export QA features to CSV from artifacts/qa_raman_mapping.json for downstream
training and fusion with Spec-CNN.

Each row corresponds to one spectrum file. Features include:
  - label, top peak wavenumbers, calibration scalar
  - QA invariants (C,F,G,J,X,K) from a seed selected by label
  - mod-24 residues and mod-9 digital roots for C and F
  - Stokes/Anti-Stokes relative shifts for Δe in {-1, +1, +2}

Usage:
  python scripts/qa_raman_features_to_csv.py
Outputs:
  artifacts/qa_raman_features.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import importlib
import argparse
import sys

# Ensure project root on path for qa_lab_rs
sys.path.insert(0, str(Path(__file__).parent.parent))

MAP_JSON = Path('artifacts/qa_raman_mapping.json')
OUT_CSV = Path('artifacts/qa_raman_features.csv')


def digital_root_mod9(n: int) -> int:
    if n == 0:
        return 9
    r = abs(n) % 9
    return r if r != 0 else 9


def choose_seed_key(label: str) -> str:
    l = (label or '').lower()
    if 'diamond' in l:
        return 'Diamond'
    if 'quartz' in l:
        return 'Quartz'
    if 'silicon' in l:
        return 'Silicon'
    # fallback
    return 'Diamond'


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', type=str, default='', help='Comma-separated label filter (e.g., diamond,quartz,silicon)')
    ap.add_argument('--modality', type=str, default='Raman', help='Modality filter (e.g., Raman, IR, XRD, or empty for all)')
    ap.add_argument('--max-rows', type=int, default=0, help='Optional cap on number of rows to export after filtering')
    args = ap.parse_args(argv)

    label_filter: Optional[set] = None
    if args.labels:
        label_filter = {s.strip().lower() for s in args.labels.split(',') if s.strip()}
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not MAP_JSON.exists():
        print(f"Missing {MAP_JSON}; run scripts/qa_raman_map_files.py first")
        return

    # Require Rust backend for invariants
    try:
        qa_lab_rs = importlib.import_module('qa_lab_rs')
        assert getattr(qa_lab_rs, 'ping', lambda: '')() == 'qa_lab_rs:ok'
    except Exception as e:
        print(f"Rust backend qa_lab_rs not available: {e}")
        return

    data = json.loads(MAP_JSON.read_text(encoding='utf-8'))
    results = data.get('results', [])
    calib = data.get('calibration_C_to_cm-1', None)

    cols = [
        'file', 'label',
        'peak1_cm-1', 'peak2_cm-1', 'peak3_cm-1', 'peak4_cm-1', 'peak5_cm-1',
        'p1_int', 'p2_int', 'p3_int', 'p4_int', 'p5_int',
        'frac1', 'frac2', 'frac3', 'frac4', 'frac5',
        'p1_over_p2', 'p2_over_p3', 'p1_over_p3', 'p3_over_p4', 'p4_over_p5',
        'p2_over_p4', 'p3_over_p5', 'p1_over_p4', 'p1_over_p5', 'p2_over_p5',
        'calib_C_to_cm-1',
        'C', 'F', 'G', 'J', 'X', 'K', 'W', 'Y', 'Z',
        'J_over_K', 'C_over_F', 'G_over_F',
        'delta12', 'delta23', 'skew',
        'C1', 'C2', 'C3', 'C4', 'C5', 'C1_mod24', 'C2_mod24', 'C3_mod24', 'C4_mod24', 'C5_mod24',
        'dC12_mod24', 'dC23_mod24', 'dC13_mod24',
        'C_mod24', 'F_mod24', 'C_dr9', 'F_dr9',
        'de_-1_rel', 'de_+1_rel', 'de_+2_rel',
        'scaled_C_cm-1',
    ]

    rows = []
    for r in results:
        file = r.get('file', '')
        label = (r.get('label', '') or '').lower()
        modality = (r.get('modality', '') or '').strip()

        if args.modality and modality and modality.lower() != args.modality.lower():
            continue

        if label_filter is not None and label not in label_filter:
            continue
        peaks = r.get('top_peaks_cm-1', [])
        peak_ints = r.get('top_peak_ints', [])
        p1 = peaks[0] if len(peaks) > 0 else ''
        p2 = peaks[1] if len(peaks) > 1 else ''
        p3 = peaks[2] if len(peaks) > 2 else ''
        p4 = peaks[3] if len(peaks) > 3 else ''
        p5 = peaks[4] if len(peaks) > 4 else ''
        i1 = peak_ints[0] if len(peak_ints) > 0 else ''
        i2 = peak_ints[1] if len(peak_ints) > 1 else ''
        i3 = peak_ints[2] if len(peak_ints) > 2 else ''
        i4 = peak_ints[3] if len(peak_ints) > 3 else ''
        i5 = peak_ints[4] if len(peak_ints) > 4 else ''

        seed_key = choose_seed_key(label)
        seeds: Dict[str, Any] = r.get('qa_seeds', {})
        seed = seeds.get(seed_key, {})

        # Prefer Rust-backed invariants computed from tuple
        tup = seed.get('tuple')
        if tup and len(tup) == 4:
            b, e, d, a = map(float, tup)
            inv = qa_lab_rs.compute_bundle_py(b, e, d, a)
            C = float(inv['C'])
            F = float(inv['F'])
            G = float(inv['G'])
            J = float(inv['J'])
            X = float(inv['X'])
            K = float(inv['K'])
            Wv = float(inv['W'])
            Yv = float(inv['Y'])
            Zv = float(inv['Z'])
        else:
            # Fallback to existing values if tuple missing
            C = float(seed.get('C', 0) or 0)
            F = float(seed.get('F', 0) or 0)
            G = float(seed.get('G', 0) or 0)
            J = float(seed.get('J', 0) or 0)
            X = float(seed.get('X', 0) or 0)
            K = float(seed.get('K', 0) or 0)
            Wv = float(seed.get('W', 0) or 0)
            Yv = float(seed.get('Y', 0) or 0)
            Zv = float(seed.get('Z', 0) or 0)

        scaled_C = seed.get('scaled_C_cm-1', '')

        try:
            C_i = int(round(C))
            F_i = int(round(F))
            C_mod24 = C_i % 24
            F_mod24 = F_i % 24
            C_dr9 = digital_root_mod9(C_i)
            F_dr9 = digital_root_mod9(F_i)
        except Exception:
            C_mod24 = ''
            F_mod24 = ''
            C_dr9 = ''
            F_dr9 = ''

        sidebands = seed.get('sidebands', {})
        de_m1 = sidebands.get('-1', {}).get('rel_shift', '')
        de_p1 = sidebands.get('1', {}).get('rel_shift', '')
        de_p2 = sidebands.get('2', {}).get('rel_shift', '')

        # Derived ratios and spacing features
        def safe_div(a, b):
            try:
                return float(a) / float(b) if float(b) != 0 else ''
            except Exception:
                return ''

        J_over_K = safe_div(J, K)
        C_over_F = safe_div(C, F)
        G_over_F = safe_div(G, F)

        # Peak spacing
        delta12 = ''
        delta23 = ''
        skew = ''
        try:
            if p1 != '' and p2 != '':
                delta12 = float(p2) - float(p1)
            if p2 != '' and p3 != '':
                delta23 = float(p3) - float(p2)
            if delta12 != '' and delta23 != '' and float(delta23) != 0:
                skew = float(delta12) / float(delta23)
        except Exception:
            pass

        # Intensities and fractions
        frac1 = frac2 = frac3 = frac4 = frac5 = ''
        p1_over_p2 = p2_over_p3 = p1_over_p3 = ''
        p3_over_p4 = p4_over_p5 = ''
        p2_over_p4 = p3_over_p5 = ''
        p1_over_p4 = p1_over_p5 = p2_over_p5 = ''
        try:
            ints = [v for v in [i1,i2,i3,i4,i5] if v != '']
            if ints:
                sI = sum(float(v) for v in ints)
                if sI > 0:
                    frac1 = float(i1)/sI if i1 != '' else ''
                    frac2 = float(i2)/sI if i2 != '' else ''
                    frac3 = float(i3)/sI if i3 != '' else ''
                    frac4 = float(i4)/sI if i4 != '' else ''
                    frac5 = float(i5)/sI if i5 != '' else ''
            p1_over_p2 = safe_div(i1, i2)
            p2_over_p3 = safe_div(i2, i3)
            p1_over_p3 = safe_div(i1, i3)
            p3_over_p4 = safe_div(i3, i4)
            p4_over_p5 = safe_div(i4, i5)
            p2_over_p4 = safe_div(i2, i4)
            p3_over_p5 = safe_div(i3, i5)
            p1_over_p4 = safe_div(i1, i4)
            p1_over_p5 = safe_div(i1, i5)
            p2_over_p5 = safe_div(i2, i5)
        except Exception:
            pass

        # Peak-based C units and residues using calibration
        C1 = C2 = C3 = C4 = C5 = C1m = C2m = C3m = C4m = C5m = ''
        dC12m = dC23m = dC13m = ''
        try:
            if calib and calib != '' and float(calib) != 0:
                s = float(calib)
                if p1 != '':
                    C1 = float(p1) / s
                    C1m = int(round(C1)) % 24
                if p2 != '':
                    C2 = float(p2) / s
                    C2m = int(round(C2)) % 24
                if p3 != '':
                    C3 = float(p3) / s
                    C3m = int(round(C3)) % 24
                if p4 != '':
                    C4 = float(p4) / s
                    C4m = int(round(C4)) % 24
                if p5 != '':
                    C5 = float(p5) / s
                    C5m = int(round(C5)) % 24
                # Differences modulo 24
                if C1m != '' and C2m != '':
                    dC12m = (int(C2m) - int(C1m)) % 24
                if C2m != '' and C3m != '':
                    dC23m = (int(C3m) - int(C2m)) % 24
                if C1m != '' and C3m != '':
                    dC13m = (int(C3m) - int(C1m)) % 24
        except Exception:
            pass

        row = [
            file, label,
            p1, p2, p3, p4, p5,
            i1, i2, i3, i4, i5, frac1, frac2, frac3, frac4, frac5,
            p1_over_p2, p2_over_p3, p1_over_p3, p3_over_p4, p4_over_p5,
            p2_over_p4, p3_over_p5, p1_over_p4, p1_over_p5, p2_over_p5,
            calib,
            C, F, G, J, X, K, Wv, Yv, Zv,
            J_over_K, C_over_F, G_over_F,
            delta12, delta23, skew,
            C1, C2, C3, C4, C5, C1m, C2m, C3m, C4m, C5m, dC12m, dC23m, dC13m,
            C_mod24, F_mod24, C_dr9, F_dr9,
            de_m1, de_p1, de_p2,
            scaled_C,
        ]
        rows.append(row)

        if args.max_rows and len(rows) >= args.max_rows:
            break

    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")


if __name__ == '__main__':
    main()
