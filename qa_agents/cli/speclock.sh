#!/bin/bash
# QA SpecLock Verification Script v4.0
# Ensures critical QA files haven't been tampered with

set -euo pipefail

MANIFEST="context/SPECLOCK.manifest"
LOG_FILE="logs/speclock_$(date +%Y%m%d_%H%M%S).log"

echo "[$(date)] 🔒 Starting SpecLock verification..." | tee -a "$LOG_FILE"

# Check if manifest exists
if [[ ! -f "$MANIFEST" ]]; then
    echo "❌ SpecLock manifest not found: $MANIFEST" | tee -a "$LOG_FILE"
    exit 1
fi

# Verify each file in manifest
ERRORS=0
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue

    expected_hash=$(echo "$line" | awk '{print $1}')
    filepath=$(echo "$line" | awk '{print $2}')

    if [[ ! -f "$filepath" ]]; then
        echo "❌ Protected file missing: $filepath" | tee -a "$LOG_FILE"
        ((ERRORS++))
        continue
    fi

    actual_hash=$(sha256sum "$filepath" | awk '{print $1}')

    if [[ "$expected_hash" != "$actual_hash" ]]; then
        echo "❌ HASH MISMATCH: $filepath" | tee -a "$LOG_FILE"
        echo "  Expected: $expected_hash" | tee -a "$LOG_FILE"
        echo "  Actual:   $actual_hash" | tee -a "$LOG_FILE"
        ((ERRORS++))
    else
        echo "✅ Verified: $filepath" | tee -a "$LOG_FILE"
    fi
done < "$MANIFEST"

if [[ $ERRORS -gt 0 ]]; then
    echo "❌ SpecLock verification FAILED ($ERRORS errors)" | tee -a "$LOG_FILE"
    echo "🔧 To fix: Either restore original files or update manifest with --override-speclock" | tee -a "$LOG_FILE"
    exit 1
else
    echo "✅ SpecLock verification PASSED" | tee -a "$LOG_FILE"
fi