#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

INGEST_CMD=(python3 qa_lab/scripts/ingest_single_odt.py)
AGG_CMD=(python3 qa_lab/scripts/aggregate_artifacts_delta.py)
PUBLISH_CMD=(python3 qa_lab/scripts/publish_run.py)
VALIDATOR_CMD=(python3 qa_alphageometry_ptolemy/qa_fst/validators/qa_run_artifact_validate.py)
SCHEMA_DIR="qa_alphageometry_ptolemy/qa_fst/schemas"
TMPDIR_SMOKE="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_SMOKE}"' EXIT
CUTOFF_DATE_UTC="2026-01-10"

pick_candidate_and_count() {
  python3 - <<'PY'
from pathlib import Path
import datetime as dt

cutoff = dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc).timestamp()
root = Path("ingestion candidates")
cands = []
for p in root.rglob("*.odt"):
    try:
        mt = p.stat().st_mtime
    except OSError:
        continue
    if mt < cutoff:
        cands.append((mt, p))
cands.sort(reverse=True, key=lambda t: t[0])
print(len(cands))
print(cands[0][1] if cands else "")
PY
}

if [[ $# -ge 1 ]]; then
  CANDIDATE="$1"
  CANDIDATE_COUNT="explicit"
else
  mapfile -t CAND_PICK < <(pick_candidate_and_count)
  CANDIDATE_COUNT="${CAND_PICK[0]:-0}"
  CANDIDATE="${CAND_PICK[1]:-}"
fi

echo "Cutoff: ${CUTOFF_DATE_UTC} UTC"
if [[ "${CANDIDATE_COUNT}" != "explicit" ]]; then
  echo "Found ${CANDIDATE_COUNT} pre-cutoff candidates"
fi

if [[ -z "${CANDIDATE}" ]]; then
  echo "No pre-2026-01-10 .odt candidate found under 'ingestion candidates/'" >&2
  exit 1
fi

if [[ ! -f "${CANDIDATE}" ]]; then
  echo "Candidate file not found: ${CANDIDATE}" >&2
  exit 1
fi

if [[ "${CANDIDATE##*.}" != "odt" ]]; then
  echo "Candidate must be an .odt file: ${CANDIDATE}" >&2
  exit 1
fi

STEM="$(basename "${CANDIDATE}" .odt)"
ANALYSIS_PATH="qa_lab/artifacts/ingestion/${STEM}_ANALYSIS.md"

echo "Candidate: ${CANDIDATE}"
echo "Single-doc ingest command: ${INGEST_CMD[*]} --input \"${CANDIDATE}\""
"${INGEST_CMD[@]}" --input "${CANDIDATE}" >"${TMPDIR_SMOKE}/ingest_single.json"

if [[ ! -f "${ANALYSIS_PATH}" ]]; then
  echo "Missing expected analysis artifact: ${ANALYSIS_PATH}" >&2
  exit 1
fi
echo "Analysis artifact exists: ${ANALYSIS_PATH}"

"${AGG_CMD[@]}" >"${TMPDIR_SMOKE}/artifact_delta.json"
echo "Artifact delta refreshed."

if ! "${PUBLISH_CMD[@]}" >"${TMPDIR_SMOKE}/publish_run.json"; then
  echo "publish_run.py failed" >&2
  cat "${TMPDIR_SMOKE}/publish_run.json" >&2 || true
  exit 1
fi
echo "publish_run.py succeeded."

LATEST_CERT_DIR="$(ls -1dt qa_lab/certs/run_artifact/* 2>/dev/null | head -n 1)"
if [[ -z "${LATEST_CERT_DIR}" ]]; then
  echo "No cert directory found under qa_lab/certs/run_artifact/" >&2
  exit 1
fi

VALIDATOR_OUT="$("${VALIDATOR_CMD[@]}" "${LATEST_CERT_DIR}" "${SCHEMA_DIR}")"
if [[ "${VALIDATOR_OUT}" != "OK" ]]; then
  echo "Validator did not return OK. Output: ${VALIDATOR_OUT}" >&2
  exit 1
fi

LATEST_REPORT="$(ls -1t qa_lab/logs/run_report_*.json | head -n 1)"
if [[ -z "${LATEST_REPORT}" ]]; then
  echo "No run report found under qa_lab/logs/" >&2
  exit 1
fi

python3 - "${LATEST_REPORT}" <<'PY'
import json, sys
from pathlib import Path

report = Path(sys.argv[1])
data = json.loads(report.read_text(encoding="utf-8"))
ok = bool(data.get("run_artifact_cert", {}).get("validated", False))
if not ok:
    raise SystemExit("run_report check failed: run_artifact_cert.validated != true")
print(f"Run report cert validated=true: {report}")
PY

echo "Latest cert dir: ${LATEST_CERT_DIR}"
echo "Validator: OK"
echo "SMOKE TEST OK"
