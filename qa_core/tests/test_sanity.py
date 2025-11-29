#!/usr/bin/env python3
"""
Basic sanity tests for QA Lab.

These tests avoid heavyweight deps and validate core invariants and structure.
"""

from pathlib import Path
import hashlib


BASE = Path(__file__).resolve().parents[2]


def test_tasks_directories_exist():
    for d in ["tasks/inbox", "tasks/active", "tasks/completed"]:
        assert (BASE / d).exists(), f"Missing directory: {d}"


def test_speclock_manifest_matches_rules_hash():
    manifest = BASE / "context" / "SPECLOCK.manifest"
    rules = BASE / "context" / "QA_RULES.yaml"
    assert manifest.exists(), "SPECLOCK.manifest not found"
    assert rules.exists(), "QA_RULES.yaml not found"

    # Read expected hash from manifest (first non-comment, non-empty line)
    expected = None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == str(rules.relative_to(BASE)):
            expected = parts[0]
            break
    assert expected, "Could not parse expected hash from manifest"

    # Compute actual hash
    h = hashlib.sha256()
    h.update(rules.read_bytes())
    actual = h.hexdigest()
    assert actual == expected, f"SpecLock hash mismatch: expected {expected}, got {actual}"

