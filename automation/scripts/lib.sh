#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="/Users/rileychalmers/AI_Stock_Hunter/AI_Stock_Hunter_v2"
PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
AUTOMATION_DIR="${PROJECT_ROOT}/automation"
LOG_DIR="${AUTOMATION_DIR}/logs"
LOCK_DIR="${AUTOMATION_DIR}/locks"
MARKET_TIMEZONE="America/New_York"

PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

timestamp() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

market_now() {
  "${PYTHON_BIN}" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds"))
PY
}

market_date() {
  "${PYTHON_BIN}" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo("America/New_York")).date().isoformat())
PY
}

market_hhmm() {
  "${PYTHON_BIN}" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo("America/New_York")).strftime("%H%M"))
PY
}

market_weekday() {
  "${PYTHON_BIN}" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo("America/New_York")).isoweekday())
PY
}

log_line() {
  printf "[%s] %s\n" "$(timestamp)" "$*"
}

fail() {
  log_line "ERROR: $*" >&2
  exit 1
}

ensure_runtime_dirs() {
  mkdir -p "${LOG_DIR}" "${LOCK_DIR}"
}

validate_project() {
  [[ -d "${PROJECT_ROOT}" ]] || fail "Project root missing: ${PROJECT_ROOT}"
  [[ -x "${PYTHON_BIN}" ]] || fail "Python venv executable missing: ${PYTHON_BIN}"
  [[ -f "${PROJECT_ROOT}/main.py" ]] || fail "Missing main.py"
  [[ -f "${PROJECT_ROOT}/web_exporter.py" ]] || fail "Missing web_exporter.py"
  [[ -f "${PROJECT_ROOT}/refresh_paper_trading.py" ]] || fail "Missing refresh_paper_trading.py"
}

load_local_env() {
  if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
  fi
}

acquire_lock() {
  local name="$1"
  local max_age_seconds="$2"
  local lock_path="${LOCK_DIR}/${name}.lock"
  local now
  local created
  local age
  local pid

  now="$(date +%s)"

  if mkdir "${lock_path}" 2>/dev/null; then
    printf "%s\n" "$$" > "${lock_path}/pid"
    printf "%s\n" "${now}" > "${lock_path}/created_at"
    trap 'release_lock "'"${lock_path}"'"' EXIT
    return 0
  fi

  pid="$(cat "${lock_path}/pid" 2>/dev/null || true)"
  created="$(cat "${lock_path}/created_at" 2>/dev/null || echo 0)"

  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    log_line "Another ${name} run is already active with pid ${pid}; skipping."
    exit 0
  fi

  age=$((now - created))
  if (( age > max_age_seconds )); then
    log_line "Removing stale ${name} lock after ${age}s."
    rm -rf "${lock_path}"
    mkdir "${lock_path}" || fail "Could not acquire ${name} lock after stale cleanup."
    printf "%s\n" "$$" > "${lock_path}/pid"
    printf "%s\n" "${now}" > "${lock_path}/created_at"
    trap 'release_lock "'"${lock_path}"'"' EXIT
    return 0
  fi

  fail "Lock exists for ${name} and is not old enough to remove: ${lock_path}"
}

release_lock() {
  local lock_path="$1"
  rm -rf "${lock_path}"
}

is_market_weekday() {
  local weekday
  weekday="$(market_weekday)"
  [[ "${weekday}" -ge 1 && "${weekday}" -le 5 ]]
}

is_regular_market_window_ny() {
  local hhmm
  hhmm="$(market_hhmm)"
  is_market_weekday && [[ "${hhmm}" -ge 0930 && "${hhmm}" -lt 1600 ]]
}

is_daily_pipeline_window_ny() {
  local hhmm
  hhmm="$(market_hhmm)"
  is_market_weekday && [[ "${hhmm}" -ge 1800 ]]
}

market_state_authority() {
  cd "${PROJECT_ROOT}"
  "${PYTHON_BIN}" - <<'PY'
from market_data_service import MarketDataService

print(MarketDataService().get_market_state())
PY
}
