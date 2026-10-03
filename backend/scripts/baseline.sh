#!/usr/bin/env bash
#
# Phase 0 baseline runner.
#
# Runs the frozen Tier A contract suite plus the full backend unit/integration suite
# and writes a summary to .kilo/baseline/. Tier A must not drift: a failure there means
# a public HTTP contract changed and needs a deliberate golden re-record, not an
# incidental edit.
#
# Usage:
#   backend/scripts/baseline.sh              # contract + full suite
#   backend/scripts/baseline.sh --contract   # contract suite only
#   SKIP_FRONTEND=1 backend/scripts/baseline.sh
#
# Exit codes:
#   0  contract suite green (other tiers may still have known reds)
#   1  contract suite red, or the run could not start
set -uo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
OUT_DIR="${REPO_ROOT}/.kilo/baseline"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT="${OUT_DIR}/run-${STAMP}.txt"

mkdir -p "${OUT_DIR}"

CONTRACT_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --contract) CONTRACT_ONLY=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# shellcheck source=/dev/null
if [ -f "${BACKEND_DIR}/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.venv/bin/activate"
fi

cd "${BACKEND_DIR}" || exit 1

{
  echo "Phase 0 baseline run ${STAMP}"
  echo "database: ${OMNICARE_TEST_DATABASE_URL:-<default: 127.0.0.1:5432/omnicare>}"
  echo
} > "${REPORT}"

run_suite() {
  local label="$1"
  shift
  echo "--- ${label} ---" | tee -a "${REPORT}"
  python -m pytest -q -p no:randomly "$@" 2>&1 | tail -30 | tee -a "${REPORT}"
  echo | tee -a "${REPORT}"
}

CONTRACT_STATUS=0
run_suite "Tier A contract" tests/contract || CONTRACT_STATUS=$?

if [ "${CONTRACT_ONLY}" -eq 1 ]; then
  echo "contract-only run complete: ${REPORT}"
  exit "${CONTRACT_STATUS}"
fi

run_suite "Full backend suite" tests || true

if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  if command -v node >/dev/null 2>&1; then
    {
      echo "--- frontend typecheck ---"
      ( cd "${REPO_ROOT}/frontend" && npm run typecheck 2>&1 | tail -15 )
      echo
      echo "--- frontend tests ---"
      ( cd "${REPO_ROOT}/frontend" && npm test 2>&1 | tail -12 )
    } 2>&1 | tee -a "${REPORT}"
  else
    echo "node not on PATH; skipping frontend tiers" | tee -a "${REPORT}"
  fi
fi

echo "report: ${REPORT}"
exit "${CONTRACT_STATUS}"
