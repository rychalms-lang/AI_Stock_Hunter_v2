#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

DRY_RUN=0
FORCE=0
ALLOW_NON_TRADING_DAY_PRODUCTION=0
CURRENT_STAGE="initialization"

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN=1
      ;;
    --force)
      FORCE=1
      ;;
    --allow-non-trading-day-production)
      ALLOW_NON_TRADING_DAY_PRODUCTION=1
      ;;
    *)
      fail "Unknown argument: ${arg}"
      ;;
  esac
done

ensure_runtime_dirs
exec >> "${LOG_DIR}/daily-pipeline.log" 2>> "${LOG_DIR}/daily-pipeline-error.log"

on_pipeline_error() {
  local exit_code="$?"
  log_line "ERROR: Daily pipeline failed during ${CURRENT_STAGE} with exit code ${exit_code}. Previous website and paper JSON are preserved unless the failed stage wrote its own partial output."
  if [[ -x "${PYTHON_BIN}" && -f "${PROJECT_ROOT}/system_status_exporter.py" ]]; then
    (cd "${PROJECT_ROOT}" && "${PYTHON_BIN}" system_status_exporter.py) || true
  fi
  exit "${exit_code}"
}

trap on_pipeline_error ERR

log_line "Daily pipeline starting."
validate_project

MARKET_DATE="$(market_date)"
MARKET_NOW="$(market_now)"
SUCCESS_MARKER="${LOCK_DIR}/daily-pipeline-${MARKET_DATE}.done"
RUN_TYPE="production"

if ! is_market_weekday; then
  if (( ALLOW_NON_TRADING_DAY_PRODUCTION == 1 )); then
    RUN_TYPE="production"
  elif (( FORCE == 1 )); then
    RUN_TYPE="manual_test"
  else
    log_line "Non-trading New York market day; skipping production pipeline."
    log_line "Use --force for a manual test or --allow-non-trading-day-production for an explicit production override."
    exit 0
  fi
fi

if (( DRY_RUN == 1 )); then
  log_line "Dry run only. No scanner, exporter, paper ledger, or reports will be modified."
  log_line "Project root: ${PROJECT_ROOT}"
  log_line "Python: ${PYTHON_BIN}"
  log_line "Market timezone: ${MARKET_TIMEZONE}"
  log_line "New York market timestamp: ${MARKET_NOW}"
  log_line "New York market date: ${MARKET_DATE}"
  log_line "Run classification: ${RUN_TYPE}"
  if [[ "${RUN_TYPE}" == "manual_test" ]]; then
    log_line "Scanner command: ${PYTHON_BIN} main.py --manual-test"
    log_line "Exporter command: skipped for manual test"
  else
    log_line "Scanner command: ${PYTHON_BIN} main.py"
    log_line "Exporter command: ${PYTHON_BIN} web_exporter.py"
  fi
  log_line "Success marker: ${SUCCESS_MARKER}"
  log_line "Daily pipeline dry run completed."
  exit 0
fi

if [[ "${RUN_TYPE}" == "production" ]] && ! is_daily_pipeline_window_ny; then
  log_line "Outside post-close New York daily pipeline window; skipping to avoid processing the wrong market date."
  log_line "Market timezone: ${MARKET_TIMEZONE}; market timestamp: ${MARKET_NOW}; market date: ${MARKET_DATE}"
  exit 0
fi

if [[ -f "${SUCCESS_MARKER}" && "${FORCE}" -ne 1 ]]; then
  log_line "Daily pipeline already completed for New York market date ${MARKET_DATE}; skipping. Use --force for a manual rerun."
  exit 0
fi

acquire_lock "daily-pipeline" 21600
load_local_env
cd "${PROJECT_ROOT}"

log_line "New York market date for this run: ${MARKET_DATE}"
log_line "New York market timestamp for this run: ${MARKET_NOW}"
log_line "Run classification: ${RUN_TYPE}"
log_line "Stage 1/5: running scanner pipeline."
CURRENT_STAGE="scanner pipeline"
if [[ "${RUN_TYPE}" == "manual_test" ]]; then
  "${PYTHON_BIN}" main.py --manual-test
else
  if (( ALLOW_NON_TRADING_DAY_PRODUCTION == 1 )); then
    "${PYTHON_BIN}" main.py --allow-non-trading-day-production
  else
    "${PYTHON_BIN}" main.py
  fi
fi

if [[ "${RUN_TYPE}" == "manual_test" ]]; then
  log_line "Manual test completed. Production web/paper exports and success marker were intentionally skipped."
  CURRENT_STAGE="system status export"
  "${PYTHON_BIN}" system_status_exporter.py
  exit 0
fi

log_line "Stage 2/4: publishing atomic research package and paper-trading JSON."
CURRENT_STAGE="atomic research package export"
"${PYTHON_BIN}" web_exporter.py

log_line "Stage 3/4: exporting system status."
CURRENT_STAGE="system status export"
"${PYTHON_BIN}" system_status_exporter.py

CURRENT_STAGE="success marker creation"
printf "completed_at=%s\n" "$(timestamp)" > "${SUCCESS_MARKER}"
printf "market_timezone=%s\n" "${MARKET_TIMEZONE}" >> "${SUCCESS_MARKER}"
printf "market_date=%s\n" "${MARKET_DATE}" >> "${SUCCESS_MARKER}"
printf "market_timestamp=%s\n" "${MARKET_NOW}" >> "${SUCCESS_MARKER}"
log_line "Daily pipeline completed successfully for New York market date ${MARKET_DATE}."
