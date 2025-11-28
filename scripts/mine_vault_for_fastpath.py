#!/usr/bin/env python3
"""
mine_vault_for_fastpath.py - Mine vault markdown for fast-path suggestions.

Scans qa_lab/vault and private/QAnotes (if present) for QA-native concepts and
outputs suggested toggles/weights to:
  - artifacts/evals/fastpath_mining.json
  - artifacts/evals/fastpath_mining.txt

This script does NOT apply changes; it only recommends settings.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re


ROOT = Path('.')
VAULTS = [ROOT / 'qa_lab' / 'vault', ROOT / 'private' / 'QAnotes']
OUT_DIR = ROOT / 'artifacts' / 'evals'
OUT_JSON = OUT_DIR / 'fastpath_mining.json'
OUT_TXT = OUT_DIR / 'fastpath_mining.txt'


TERMS = {
    'fibonacci': re.compile(r'\bfib(?:onacci)?\b', re.I),
    'lucas': re.compile(r'\blucas\b', re.I),
    'wheel': re.compile(r'\b(mod-?24|24-?wheel|wheel)\b', re.I),
    'eisenstein': re.compile(r'\beisenstein\b', re.I),
    'triangle': re.compile(r'\btriangle\b', re.I),
    'positivity': re.compile(r'\bpositive|positivity\b', re.I),
    'curvature': re.compile(r'\bcurvature|non-abelian|commutator\b', re.I),
    'ideal': re.compile(r'\bgrant\'?s\s+lrt|\b\[1,\s*1,\s*2,\s*3\]\b', re.I),
}


def scan_text(text: str) -> dict[str, int]:
    counts = {k: 0 for k in TERMS}
    for key, rx in TERMS.items():
        counts[key] += len(rx.findall(text))
    return counts


def aggregate_counts() -> dict[str, int]:
    total = {k: 0 for k in TERMS}
    for base in VAULTS:
        if not base.exists():
            continue
        for p in base.rglob('*.md'):
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            c = scan_text(text)
            for k, v in c.items():
                total[k] += v
    return total


def build_suggestions(counts: dict[str, int]) -> dict:
    sug = {
        'wheel': {'enable': counts['wheel'] > 0},
        'family': {
            'enable': (counts['fibonacci'] + counts['lucas']) > 0,
            'phi_tol': 0.05,
        },
        'positivity': {'min': 0.0 if counts['positivity'] > 0 else 0.0},
        'triangle': {'enable': counts['triangle'] > 0, 'tol': 1e-9},
        'curvature': {'qe_weight': 0.25 if counts['curvature'] > 0 else 0.25},
        'ideal': {'qe_weight': 0.1 if counts['ideal'] > 0 else 0.0},
    }
    return sug


def format_txt(counts: dict[str, int], sug: dict) -> str:
    lines = []
    lines.append('Vault Mining Suggestions (fast-path)')
    lines.append('=')
    lines.append('Signals:')
    for k in sorted(counts):
        lines.append(f'- {k}: {counts[k]} occurrences')
    lines.append('')
    lines.append('Recommended toggles/weights:')
    lines.append(f"- QA_FP_ENABLE_WHEEL={1 if sug['wheel']['enable'] else 1}")
    lines.append(f"- QA_FP_ENABLE_FAMILY={1 if sug['family']['enable'] else 1}")
    lines.append(f"- QA_FP_FAMILY_TOL={sug['family']['phi_tol']}")
    lines.append(f"- QA_FP_POS_MIN={sug['positivity']['min']}")
    lines.append(f"- QA_QE_CURV_WEIGHT={sug['curvature']['qe_weight']}")
    lines.append(f"- QA_QE_IDEAL_WEIGHT={sug['ideal']['qe_weight']}")
    return '\n'.join(lines) + '\n'


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = aggregate_counts()
    sug = build_suggestions(counts)
    OUT_JSON.write_text(json.dumps({'counts': counts, 'suggestions': sug}, indent=2))
    OUT_TXT.write_text(format_txt(counts, sug))


if __name__ == '__main__':
    main()

