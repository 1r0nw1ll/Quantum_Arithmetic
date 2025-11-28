#!/usr/bin/env python3
"""
qa_kg_summary.py — Append a brief Knowledge Graph summary to the daily report.

Outputs
  - Prints summary to stdout by default.
  - With --append, appends a short KG section to qa_lab/artifacts/evals/daily_summary_latest.txt.

Reads
  - ../artifacts/knowledge/qa_entity_encodings.json
  - ../artifacts/knowledge/qa_knowledge_graph.graphml

Usage
  python scripts/qa_kg_summary.py            # print-only
  python scripts/qa_kg_summary.py --append   # append to latest daily summary
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Tuple, List

try:
    import networkx as nx  # type: ignore
except Exception:
    nx = None  # type: ignore


def prefer_paths(candidates: List[Path]) -> Path | None:
    for p in candidates:
        if p.exists():
            return p
    return None


def load_counts() -> Tuple[int, int, list]:
    # Try repo-root artifacts first, then local qa_lab artifacts (fallback)
    enc_path = prefer_paths([
        Path('..') / 'artifacts' / 'knowledge' / 'qa_entity_encodings.json',
        Path('artifacts') / 'knowledge' / 'qa_entity_encodings.json',
    ])
    gml_path = prefer_paths([
        Path('..') / 'artifacts' / 'knowledge' / 'qa_knowledge_graph.graphml',
        Path('artifacts') / 'knowledge' / 'qa_knowledge_graph.graphml',
    ])

    entities_count = 0
    edges_count = 0
    top_hi = []  # list of (name, hi, e8)

    if enc_path and enc_path.exists():
        try:
            data = json.loads(enc_path.read_text(encoding='utf-8'))
            encs = data.get('encodings', [])
            entities_count = len(encs)
            # sort by hi (fallback e8)
            def score(rec):
                hi = rec.get('hi', None)
                if hi is None:
                    return float(rec.get('e8_alignment', 0.0))
                return float(hi)
            encs_sorted = sorted(encs, key=score, reverse=True)
            for rec in encs_sorted[:5]:
                top_hi.append((rec.get('name', ''), float(rec.get('hi', rec.get('e8_alignment', 0.0))), float(rec.get('e8_alignment', 0.0))))
        except Exception:
            pass

    if gml_path and gml_path.exists():
        if nx is not None:
            try:
                G = nx.read_graphml(str(gml_path))
                edges_count = G.number_of_edges()
            except Exception:
                edges_count = 0
        else:
            # Fallback: count edge tags in GraphML text
            try:
                text = gml_path.read_text(encoding='utf-8', errors='ignore')
                edges_count = text.count('<edge ')
            except Exception:
                edges_count = 0

    return entities_count, edges_count, top_hi


def format_section(entities_count: int, edges_count: int, top_hi: list) -> str:
    lines = []
    lines.append("")
    lines.append("Knowledge Graph Summary")
    lines.append("-")
    lines.append(f"Entities: {entities_count}")
    lines.append(f"Edges: {edges_count}")
    if top_hi:
        lines.append("Top by HI (fallback E8):")
        for name, hi, e8 in top_hi:
            lines.append(f"- {name}: HI={hi:.4f} E8={e8:.4f}")
    lines.append("See: ../artifacts/knowledge/qa_knowledge_graph.graphml")
    return '\n'.join(lines) + '\n'


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description='Append Knowledge Graph summary to daily report')
    parser.add_argument('--append', action='store_true', help='Append to artifacts/evals/daily_summary_latest.txt')
    args = parser.parse_args(argv)

    entities_count, edges_count, top_hi = load_counts()
    section = format_section(entities_count, edges_count, top_hi)

    if not args.append:
        print(section, end='')
        return 0

    # Append to qa_lab daily summary
    out_latest = Path('artifacts') / 'evals' / 'daily_summary_latest.txt'
    out_latest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_latest.open('a', encoding='utf-8') as f:
            f.write(section)
    except Exception:
        # Fallback: print to stdout
        print(section, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
