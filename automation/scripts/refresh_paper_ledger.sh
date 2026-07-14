#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

DRY_RUN=0
VERBOSE=0
FORCE=0

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN=1
      ;;
    --verbose)
      VERBOSE=1
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
exec >> "${LOG_DIR}/paper-refresh.log" 2>> "${LOG_DIR}/paper-refresh-error.log"

log_line "Paper ledger refresh starting."
validate_project

MARKET_NOW="$(market_now)"
MARKET_DATE="$(market_date)"
MARKET_STATE="UNKNOWN"

log_line "Market timezone: ${MARKET_TIMEZONE}"
log_line "New York market timestamp: ${MARKET_NOW}"
log_line "New York market date: ${MARKET_DATE}"

if (( FORCE != 1 )) && ! is_regular_market_window_ny; then
  log_line "Outside regular New York market window; refresh skipped safely."
  exit 0
fi

if (( FORCE != 1 )); then
  MARKET_STATE="$(market_state_authority)"
  if [[ "${MARKET_STATE}" != "OPEN" ]]; then
    log_line "MarketDataService reports market_state=${MARKET_STATE}; refresh skipped safely."
    exit 0
  fi
fi

acquire_lock "paper-refresh" 7200 "Previous portfolio refresh still running; this cycle was skipped."
load_local_env
cd "${PROJECT_ROOT}"

ARGS=()
if (( DRY_RUN == 1 )); then
  ARGS+=(--dry-run)
fi
if (( VERBOSE == 1 )); then
  ARGS+=(--verbose)
fi

log_line "Refreshing market snapshot."
if (( DRY_RUN == 1 )); then
  "${PYTHON_BIN}" refresh_market_snapshot.py --dry-run
else
  "${PYTHON_BIN}" refresh_market_snapshot.py
fi

log_line "Running paper-trading refresh command using shared market snapshot batch."
ARGS+=(--market-snapshot data/market_snapshot.json)
"${PYTHON_BIN}" refresh_paper_trading.py "${ARGS[@]}"

if (( DRY_RUN != 1 )); then
  log_line "Exporting system status."
  "${PYTHON_BIN}" system_status_exporter.py
fi

log_line "Paper ledger refresh completed successfully."
