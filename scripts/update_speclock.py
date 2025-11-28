"""
Auto-refactor: normalize formatting for update_speclock.py
"""

#!/usr/bin/env python3
"""
QA SpecLock Manifest Updater v4.0
Updates the SpecLock manifest with current file hashes.
Use only after approved changes to protected files.
"""

import hashlib
import os
import sys
from pathlib import Path

MANIFEST_PATH = Path("context/SPECLOCK.manifest")
PROTECTED_FILES = [
    "context/QA_RULES.yaml",
    "qa_core/geometry/inner_ellipse.py",
    "qa_core/geometry/quantum_ellipse.py",
    "qa_core/arithmetic/qa_tuple.py",
    "qa_core/arithmetic/invariants.py",
]

def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def update_manifest():
    """Update the SpecLock manifest with current hashes."""
    print("🔄 Updating SpecLock manifest...")

    # Read existing manifest to preserve comments
    existing_content = ""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r") as f:
            existing_content = f.read()

    # Generate new manifest content
    new_lines = [
        "# QA SpecLock Manifest v4.0",
        "# Critical files that must not be modified without explicit override",
        "# Format: <sha256sum> <filepath>",
        "",
        "# Core QA Rules - NEVER MODIFY WITHOUT MANUAL APPROVAL"
    ]

    for filepath in PROTECTED_FILES:
        path = Path(filepath)
        if path.exists():
            hash_value = calculate_sha256(path)
            new_lines.append(f"{hash_value} {filepath}")
        else:
            print(f"⚠️  Warning: Protected file not found: {filepath}")

    new_lines.extend([
        "",
        "# Update this manifest after any approved changes using:",
        "# ./scripts/update_speclock.py"
    ])

    # Write new manifest
    with open(MANIFEST_PATH, "w") as f:
        f.write("\n".join(new_lines) + "\n")

    print("✅ SpecLock manifest updated")
    print("🔒 Remember: Only update after approved changes to protected files!")

if __name__ == "__main__":
    # Safety check - require explicit confirmation
    if "--yes-i-know-what-im-doing" not in sys.argv:
        print("❌ Safety check: This will update the SpecLock manifest.")
        print("   Only run this after approved changes to protected files.")
        print("   Add --yes-i-know-what-im-doing to confirm.")
        sys.exit(1)

    update_manifest()
