#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

YES=0
for arg in "$@"; do
  case "${arg}" in
    --yes)
      YES=1
      ;;
    *)
      fail "Unknown argument: ${arg}"
      ;;
  esac
done

DAILY_LABEL="com.aistockhunter.daily-pipeline"
REFRESH_LABEL="com.aistockhunter.paper-refresh"
LAUNCHD_DIR="${PROJECT_ROOT}/automation/launchd"
USER_AGENT_DIR="${HOME}/Library/LaunchAgents"
UID_VALUE="$(id -u)"

print_preview() {
  cat <<EOF
AI Stock Hunter launchd installation preview

Plist destination:
  ${USER_AGENT_DIR}

Labels:
  ${DAILY_LABEL}
  ${REFRESH_LABEL}

Resolved project path:
  ${PROJECT_ROOT}

Resolved Python path:
  ${PYTHON_BIN}

Daily schedule:
  Monday-Friday at 6:00 PM in the Mac's local timezone.
  Wrapper records and deduplicates by New York market date.
  Wrapper runs only after the New York post-close window unless --force is used manually.

Refresh schedule:
  launchd checks every 5 minutes with StartInterval=300.
  Wrapper refreshes only during the New York regular market window unless --force is used manually.
  MarketDataService market_state must be OPEN before scheduled refresh proceeds.
  Successful refreshes generate one market snapshot quote batch, then reuse it for durable paper valuation.

Market timezone:
  ${MARKET_TIMEZONE}

Log locations:
  ${LOG_DIR}/daily-pipeline.log
  ${LOG_DIR}/daily-pipeline-error.log
  ${LOG_DIR}/paper-refresh.log
  ${LOG_DIR}/paper-refresh-error.log

Cron conflict check:
  Run 'crontab -l' manually and disable any old scanner cron job before enabling launchd.

EOF
}

confirm() {
  if (( YES == 1 )); then
    return 0
  fi

  printf "Install AI Stock Hunter launch agents into %s? [y/N] " "${USER_AGENT_DIR}"
  read -r reply
  [[ "${reply}" == "y" || "${reply}" == "Y" ]] || fail "Install cancelled."
}

validate_agent_source() {
  local label="$1"
  local source="${LAUNCHD_DIR}/${label}.plist"
  [[ -f "${source}" ]] || fail "Missing plist template: ${source}"
  /usr/bin/plutil -lint "${source}" >/dev/null
}

install_one() {
  local label="$1"
  local source="${LAUNCHD_DIR}/${label}.plist"
  local target="${USER_AGENT_DIR}/${label}.plist"

  if [[ -e "${target}" ]] && ! /usr/bin/cmp -s "${source}" "${target}"; then
    fail "Refusing to overwrite unrelated existing agent: ${target}"
  fi

  cp "${source}" "${target}"
  /usr/bin/plutil -lint "${target}" >/dev/null

  if launchctl print "gui/${UID_VALUE}/${label}" >/dev/null 2>&1; then
    launchctl bootout "gui/${UID_VALUE}" "${target}" >/dev/null 2>&1 || true
  fi

  launchctl bootstrap "gui/${UID_VALUE}" "${target}"
  log_line "Installed and loaded ${label}."
}

ensure_runtime_dirs
validate_project
validate_agent_source "${DAILY_LABEL}"
validate_agent_source "${REFRESH_LABEL}"
mkdir -p "${USER_AGENT_DIR}"

print_preview
confirm
install_one "${DAILY_LABEL}"
install_one "${REFRESH_LABEL}"

log_line "AI Stock Hunter launch agents installed."
log_line "Check status with: ${PROJECT_ROOT}/automation/scripts/status_launch_agents.sh"
