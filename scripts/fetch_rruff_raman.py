#!/usr/bin/env python3
"""
Fetch Raman spectra from RRUFF (or similar pages) using a CSV manifest.

Manifest CSV columns (header required):
  id,mineral,source_url,modality

Behavior:
  - For each row, attempts to download .txt or .jdx files.
  - Saves to: <output_dir>/<mineral>/<id>_<modality>.<ext>
  - Idempotent: skips existing files unless --force.
  - Logs results to artifacts/rruff_download_log.csv

Usage:
  python scripts/fetch_rruff_raman.py \
    --manifest artifacts/rruff_manifest.csv \
    --output-dir qa_data/raman/rruff \
    [--force] [--sleep 0.8]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


LOG_CSV = Path('artifacts/rruff_download_log.csv')


@dataclass
class ManifestRow:
    id: str
    mineral: str
    source_url: str
    modality: str


def read_manifest(path: Path) -> List[ManifestRow]:
    out: List[ManifestRow] = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = (row.get('id') or '').strip()
            mineral = (row.get('mineral') or '').strip()
            surl = (row.get('source_url') or '').strip()
            modality = (row.get('modality') or '').strip() or 'Raman'
            if not (rid and mineral and surl):
                continue
            out.append(ManifestRow(rid, mineral, surl, modality))
    return out


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def is_data_link(href: str) -> bool:
    h = href.lower()
    return h.endswith('.txt') or h.endswith('.jdx') or ('.txt' in h) or ('.jdx' in h)


def pick_candidate_link(links: List[str], rid: str) -> Optional[str]:
    # Prefer link with id
    for h in links:
        if rid.lower() in h.lower() and is_data_link(h):
            return h
    # Else first data link
    for h in links:
        if is_data_link(h):
            return h
    return None


def mine_rruff_page(session: requests.Session, row: ManifestRow, surl: str) -> tuple[str, str, str]:
    """
    Mines a RRUFF sample page for data links, following intermediate pages.
    """
    try:
        r = session.get(surl, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        hrefs = [a.get('href') for a in soup.find_all('a', href=True) if a.get('href')]

        # Stage 1: Find intermediate page links (e.g., '.../jcamp/', '.../txt/')
        intermediate_links = []
        for href in hrefs:
            if any(tag in href for tag in ['/jcamp/', '/txt/', '/xrd/']):
                intermediate_links.append(urljoin(surl, href))

        if intermediate_links:
            for ilink in intermediate_links:
                try:
                    ir = session.get(ilink, timeout=20)
                    ir.raise_for_status()
                    isoup = BeautifulSoup(ir.content, 'html.parser')
                    ihrefs = [a.get('href') for a in isoup.find_all('a', href=True) if a.get('href')]
                    cand = pick_candidate_link(ihrefs, row.id)
                    if cand:
                        full_url = urljoin(ilink, cand)
                        return 'found', full_url, ''
                except requests.RequestException:
                    continue # Try next intermediate link

        # Stage 2: Fallback to original direct link search on the same page
        cand = pick_candidate_link(hrefs, row.id)
        if cand:
            full_url = urljoin(surl, cand)
            return 'found', full_url, ''

        # Stage 3: If this looks like a mineral index page, follow sample links then mine those pages
        # Heuristics for RRUFF sample links (e.g., '/R040031', '?sampleID=R040031', '/samples/R040031')
        sample_like = []
        sample_pat = re.compile(r"R\d{5,}")
        for href in hrefs:
            if not href:
                continue
            if sample_pat.search(href) or 'sampleid=' in href.lower() or '/R0' in href:
                sample_like.append(urljoin(surl, href))

        # De-duplicate and limit to a few to avoid hammering the site
        seen = set()
        limited = []
        for h in sample_like:
            if h in seen:
                continue
            seen.add(h)
            limited.append(h)
            if len(limited) >= 6:
                break

        for slink in limited:
            try:
                sr = session.get(slink, timeout=20)
                sr.raise_for_status()
                ssoup = BeautifulSoup(sr.content, 'html.parser')
                shrefs = [a.get('href') for a in ssoup.find_all('a', href=True) if a.get('href')]
                # First try explicit data links
                cand = pick_candidate_link(shrefs, row.id)
                if cand:
                    return 'found', urljoin(slink, cand), ''
                # Then try intermediate '/jcamp/' '/txt/' within the sample page
                inter = []
                for h in shrefs:
                    if any(tag in h for tag in ['/jcamp/', '/txt/', '/xrd/']):
                        inter.append(urljoin(slink, h))
                for il in inter:
                    try:
                        ir = session.get(il, timeout=20)
                        ir.raise_for_status()
                        isoup = BeautifulSoup(ir.content, 'html.parser')
                        ihrefs = [a.get('href') for a in isoup.find_all('a', href=True) if a.get('href')]
                        cc = pick_candidate_link(ihrefs, row.id)
                        if cc:
                            return 'found', urljoin(il, cc), ''
                    except requests.RequestException:
                        continue
            except requests.RequestException:
                continue

        return 'no_link', '', 'no .txt/.jdx link found in page, intermediate pages, or sample pages'

    except Exception as e:
        return 'error', '', f'page fetch error: {e}'


def download_one(session: requests.Session, row: ManifestRow, out_dir: Path, force: bool) -> tuple[str, str, str]:
    # Returns (status, final_url, local_path or message)
    ensure_dir(out_dir)
    base = f"{row.id}_{row.modality}"
    # Skip if already exists
    existing = list(out_dir.glob(base + '.*'))
    if existing and not force:
        return 'skipped', '', str(existing[0])

    surl = row.source_url
    # Direct download if URL looks like a data file
    if is_data_link(surl):
        return fetch_url_to_path(session, surl, out_dir, base)

    # Else, fetch HTML and mine links
    status, url, msg = mine_rruff_page(session, row, surl)

    if status == 'found':
        return fetch_url_to_path(session, url, out_dir, base)
    else:
        return status, url, msg


def fetch_url_to_path(session: requests.Session, url: str, out_dir: Path, base: str) -> tuple[str, str, str]:
    try:
        rr = session.get(url, timeout=30)
        rr.raise_for_status()
        # Guess extension
        parsed = urlparse(url)
        name = os.path.basename(parsed.path)
        ext = os.path.splitext(name)[1] or '.dat'
        dest = out_dir / (base + ext)
        with open(dest, 'wb') as f:
            f.write(rr.content)
        return ('ok', url, str(dest))
    except Exception as e:
        return ('error', url, f'download error: {e}')


def append_log(rows: List[tuple[str, str, str, str, str, str, str]]) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    newfile = not LOG_CSV.exists()
    with open(LOG_CSV, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if newfile:
            w.writerow(['id','mineral','modality','source_url','status','final_url','local_path_or_message'])
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--output-dir', type=Path, default=Path('qa_data/raman/rruff'))
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.8)
    args = ap.parse_args()

    manifest = read_manifest(args.manifest)
    if not manifest:
        print('Manifest is empty or unreadable')
        return

    ensure_dir(args.output_dir)
    session = requests.Session()
    session.headers.update({'User-Agent': 'QA-RRUFF-Fetcher/1.0'})

    logs = []
    for row in manifest:
        mineral_dir = args.output_dir / row.mineral
        ensure_dir(mineral_dir)
        status, final_url, dest_or_msg = download_one(session, row, mineral_dir, args.force)
        print(f"{row.id} {row.mineral}: {status} -> {final_url or dest_or_msg}")
        logs.append((row.id, row.mineral, row.modality, row.source_url, status, final_url, dest_or_msg))
        time.sleep(max(0.0, args.sleep))

    append_log(logs)
    print(f"Log appended to {LOG_CSV}")


if __name__ == '__main__':
    main()
