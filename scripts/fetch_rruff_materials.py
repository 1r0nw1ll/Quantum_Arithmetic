#!/usr/bin/env python3
"""
Bulk fetch Raman spectra for a list of mineral/material names from RRUFF.

Note: RRUFF site structure may change. This is a best-effort miner that:
  - Hits https://rruff.info/<material>
  - Extracts sample page links that look like /<mineral>/R######
  - For each sample page, follows intermediate links (/jcamp/, /txt/) to find
    .txt/.jdx files and downloads them.

Usage:
  python scripts/fetch_rruff_materials.py \
    --materials hematite,graphite,graphene,MoS2,corundum,anatase,rutile \
    --max-per-class 500 \
    --dest qa_data/raman \
    [--sleep 0.5] [--force]

Outputs under: <dest>/<material>/<RRUFF_ID>_Raman.<ext>
Log appended to: artifacts/rruff_download_log.csv
"""

from __future__ import annotations

import argparse
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

LOG_CSV = Path('artifacts/rruff_download_log.csv')


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def append_log(rows: List[Tuple[str, str, str, str, str, str, str]]) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    newfile = not LOG_CSV.exists()
    with open(LOG_CSV, 'a', encoding='utf-8') as f:
        if newfile:
            f.write('id,mineral,modality,source_url,status,final_url,local_path_or_message\n')
        for r in rows:
            f.write(','.join(x.replace('\n',' ').replace(',',';') for x in r) + '\n')


def is_data_link(href: str) -> bool:
    h = href.lower()
    return h.endswith('.txt') or h.endswith('.jdx') or ('.txt' in h) or ('.jdx' in h)


def pick_candidate_link(hrefs: List[str], rid: str) -> Optional[str]:
    for h in hrefs:
        if rid.lower() in h.lower() and is_data_link(h):
            return h
    for h in hrefs:
        if is_data_link(h):
            return h
    return None


def mine_rruff_sample_page(session: requests.Session, sample_url: str, rid: str) -> Tuple[str, str]:
    """Return (status, found_url_or_msg)."""
    r = session.get(sample_url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')
    hrefs = [a.get('href') for a in soup.find_all('a', href=True) if a.get('href')]
    # Prefer intermediate paths
    inter = [urljoin(sample_url, h) for h in hrefs if any(tag in h for tag in ['/jcamp/', '/txt/', '/xrd/'])]
    for ilink in inter:
        try:
            ir = session.get(ilink, timeout=20)
            ir.raise_for_status()
            isoup = BeautifulSoup(ir.content, 'html.parser')
            ihrefs = [a.get('href') for a in isoup.find_all('a', href=True) if a.get('href')]
            cand = pick_candidate_link(ihrefs, rid)
            if cand:
                return 'found', urljoin(ilink, cand)
        except requests.RequestException:
            continue
    # Fallback: direct links on page
    cand2 = pick_candidate_link(hrefs, rid)
    if cand2:
        return 'found', urljoin(sample_url, cand2)
    return 'no_link', 'no .txt/.jdx in sample or intermediates'


def fetch_url_to_path(session: requests.Session, url: str, dest_dir: Path, base_name: str) -> Tuple[str, str, str]:
    try:
        rr = session.get(url, timeout=30)
        rr.raise_for_status()
        parsed = urlparse(url)
        name = os.path.basename(parsed.path)
        ext = os.path.splitext(name)[1] or '.dat'
        dest = dest_dir / (base_name + ext)
        with open(dest, 'wb') as f:
            f.write(rr.content)
        return 'ok', url, str(dest)
    except Exception as e:
        return 'error', url, f'download error: {e}'


def sample_links_from_material(session: requests.Session, material: str, root_url: str) -> List[Tuple[str, str]]:
    """Return list of (rid, sample_url)."""
    r = session.get(root_url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')
    out: List[Tuple[str, str]] = []
    for a in soup.find_all('a', href=True):
        href = a.get('href')
        # Matches paths like /quartz/R040031 or /diamond/R150087
        m = re.search(r'/[A-Za-z0-9_\-]+/(R\d{5,})', href or '')
        if m:
            rid = m.group(1)
            out.append((rid, urljoin(root_url, href)))
    # Deduplicate by rid
    seen = set()
    uniq = []
    for rid, u in out:
        if rid in seen:
            continue
        seen.add(rid)
        uniq.append((rid, u))
    return uniq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--materials', required=True, type=str, help='Comma-separated materials')
    ap.add_argument('--max-per-class', type=int, default=500)
    ap.add_argument('--dest', type=Path, default=Path('qa_data/raman'))
    ap.add_argument('--sleep', type=float, default=0.5)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    mats = [m.strip() for m in args.materials.split(',') if m.strip()]
    ensure_dir(args.dest)
    session = requests.Session()
    session.headers.update({'User-Agent': 'QA-RRUFF-BulkFetcher/1.0'})

    logs = []
    for mat in mats:
        mat_dir = args.dest / mat
        ensure_dir(mat_dir)
        root_url = f'https://rruff.info/{mat}'
        try:
            samples = sample_links_from_material(session, mat, root_url)
        except Exception as e:
            print(f"{mat}: root fetch error: {e}")
            logs.append(('', mat, 'Raman', root_url, 'error', '', f'root fetch error: {e}'))
            continue

        print(f"{mat}: found {len(samples)} sample pages")
        cnt = 0
        for rid, sample_url in samples:
            base_name = f"{rid}_Raman"
            existing = list(mat_dir.glob(base_name + '.*'))
            if existing and not args.force:
                logs.append((rid, mat, 'Raman', sample_url, 'skipped', '', str(existing[0])))
                cnt += 1
                if args.max_per_class and cnt >= args.max_per_class:
                    break
                continue

            try:
                status, found, msg = mine_rruff_sample_page(session, sample_url, rid)
                if status == 'found':
                    st, url, dest = fetch_url_to_path(session, found, mat_dir, base_name)
                    print(f"  {mat} {rid}: {st} -> {dest if st=='ok' else url}")
                    logs.append((rid, mat, 'Raman', sample_url, st, url, dest))
                else:
                    print(f"  {mat} {rid}: {status} ({msg})")
                    logs.append((rid, mat, 'Raman', sample_url, status, '', msg))
            except Exception as e:
                print(f"  {mat} {rid}: error {e}")
                logs.append((rid, mat, 'Raman', sample_url, 'error', '', str(e)))
            cnt += 1
            if args.max_per_class and cnt >= args.max_per_class:
                break
            time.sleep(max(0.0, args.sleep))

    append_log(logs)
    print(f"Log appended to {LOG_CSV}")


if __name__ == '__main__':
    main()
