#!/usr/bin/env python3
"""
Ingest a single ODT document into qa_lab artifacts.

Writes:
- qa_lab/tmp/<stem>.txt
- qa_lab/artifacts/ingestion/<stem>_ANALYSIS.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Tuple


BASE = Path(__file__).resolve().parents[1]  # qa_lab
REPO_ROOT = BASE.parent
TMP_DIR = BASE / "tmp"
INGESTION_ARTIFACTS = BASE / "artifacts" / "ingestion"
PRE_CONTROL_CUTOFF = dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc).timestamp()


def _normalize_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_odt_text(path: Path, max_chars: int | None = None) -> str:
    with zipfile.ZipFile(path, "r") as zf:
        with zf.open("content.xml") as f:
            xml_bytes = f.read()

    root = ET.fromstring(xml_bytes)
    raw_text = ET.tostring(root, encoding="unicode", method="text")
    text = _normalize_text(raw_text)
    if max_chars and max_chars > 0:
        text = text[:max_chars]
    return text


def build_analysis_markdown(
    source_path: Path,
    extracted_text: str,
    extracted_txt_rel: str,
    historical_regression: bool,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    preview = extracted_text[:2500]
    if len(extracted_text) > 2500:
        preview += "\n..."

    lines = [
        f"# Analysis: {source_path.name}",
        "",
        f"**Date:** {now}",
        f"**Source:** {source_path.resolve()}",
        f"**Extracted Content Length:** {len(extracted_text)} chars",
        "",
        "## Extraction Status",
        "✅ Successfully extracted ODT content",
        "",
        "## Content Preview",
        "```",
        preview,
        "```",
        "",
        "## QA Control-Theorem Mapping (Initial)",
        "- **State space candidate**: document-defined objects and transitions represented as QA states.",
        "- **Generators candidate**: transformations/theorems/procedures described by the document.",
        "- **Invariants candidate**: identities or constraints that remain stable across valid moves.",
        "- **Failure algebra candidate**: explicit obstruction classes where mappings or constraints break.",
        "",
        "## Notes",
    ]
    if historical_regression:
        lines.append("- Historical regression ingest for a pre-2026-01-10 candidate.")
    lines.append(f"- Full extracted text: `{extracted_txt_rel}`")
    lines.append("")
    return "\n".join(lines)


def ingest_single(input_path: Path, max_chars: int | None) -> Tuple[Path, Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")
    if input_path.suffix.lower() != ".odt":
        raise ValueError(f"expected .odt file, got: {input_path}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    INGESTION_ARTIFACTS.mkdir(parents=True, exist_ok=True)

    text = extract_odt_text(input_path, max_chars=max_chars)
    stem = input_path.stem
    extracted_txt = TMP_DIR / f"{stem}.txt"
    analysis_md = INGESTION_ARTIFACTS / f"{stem}_ANALYSIS.md"

    extracted_txt.write_text(text, encoding="utf-8")

    is_historical = input_path.stat().st_mtime < PRE_CONTROL_CUTOFF
    extracted_rel = str(extracted_txt.relative_to(REPO_ROOT))
    analysis = build_analysis_markdown(
        source_path=input_path,
        extracted_text=text,
        extracted_txt_rel=extracted_rel,
        historical_regression=is_historical,
    )
    analysis_md.write_text(analysis, encoding="utf-8")

    return extracted_txt, analysis_md


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one ODT document into QA analysis artifacts.")
    parser.add_argument("--input", required=True, help="Path to .odt input file")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=50000,
        help="Maximum extracted text length (default: 50000; use 0 for unlimited)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = (REPO_ROOT / input_path).resolve()
    max_chars = None if args.max_chars == 0 else args.max_chars

    extracted_txt, analysis_md = ingest_single(input_path, max_chars=max_chars)
    print(
        json.dumps(
            {
                "status": "ok",
                "input": str(input_path),
                "extracted_txt": str(extracted_txt),
                "analysis_md": str(analysis_md),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
