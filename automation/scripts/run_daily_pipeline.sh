#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

DRY_RUN=0
FORCE=0

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN=1
      ;;
    --force)
      FORCE=1
      ;;
    *)
      fail "Unknown argument: ${arg}"
      ;;
  esac
done

ensure_runtime_dirs
exec >> "${LOG_DIR}/daily-pipeline.log" 2>> "${LOG_DIR}/daily-pipeline-error.log"

log_line "Daily pipeline starting."
validate_project

MARKET_DATE="$(market_date)"
MARKET_NOW="$(market_now)"
SUCCESS_MARKER="${LOCK_DIR}/daily-pipeline-${MARKET_DATE}.done"

if (( DRY_RUN == 1 )); then
  log_line "Dry run only. No scanner, exporter, paper ledger, or reports will be modified."
  log_line "Project root: ${PROJECT_ROOT}"
  log_line "Python: ${PYTHON_BIN}"
  log_line "Market timezone: ${MARKET_TIMEZONE}"
  log_line "New York market timestamp: ${MARKET_NOW}"
  log_line "New York market date: ${MARKET_DATE}"
  log_line "Scanner command: ${PYTHON_BIN} main.py"
  log_line "Exporter command: ${PYTHON_BIN} web_exporter.py"
  log_line "Success marker: ${SUCCESS_MARKER}"
  log_line "Daily pipeline dry run completed."
  exit 0
fi

if (( FORCE != 1 )) && ! is_daily_pipeline_window_ny; then
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
log_line "Stage 1/2: running scanner pipeline."
"${PYTHON_BIN}" main.py

log_line "Stage 2/4: exporting web and paper-trading JSON."
"${PYTHON_BIN}" web_exporter.py

log_line "Stage 3/4: exporting research archive index."
"${PYTHON_BIN}" research_archive_exporter.py

log_line "Stage 4/4: exporting system status."
"${PYTHON_BIN}" system_status_exporter.py

printf "completed_at=%s\n" "$(timestamp)" > "${SUCCESS_MARKER}"
printf "market_timezone=%s\n" "${MARKET_TIMEZONE}" >> "${SUCCESS_MARKER}"
printf "market_date=%s\n" "${MARKET_DATE}" >> "${SUCCESS_MARKER}"
printf "market_timestamp=%s\n" "${MARKET_NOW}" >> "${SUCCESS_MARKER}"
log_line "Daily pipeline completed successfully for New York market date ${MARKET_DATE}."
