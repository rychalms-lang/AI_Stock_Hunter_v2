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

LABELS=(
  "com.aistockhunter.daily-pipeline"
  "com.aistockhunter.paper-refresh"
)
USER_AGENT_DIR="${HOME}/Library/LaunchAgents"
UID_VALUE="$(id -u)"

confirm() {
  if (( YES == 1 )); then
    return 0
  fi

  printf "Unload and remove AI Stock Hunter launch agents only? [y/N] "
  read -r reply
  [[ "${reply}" == "y" || "${reply}" == "Y" ]] || fail "Uninstall cancelled."
}

uninstall_one() {
  local label="$1"
  local target="${USER_AGENT_DIR}/${label}.plist"

  if [[ -f "${target}" ]]; then
    launchctl bootout "gui/${UID_VALUE}" "${target}" >/dev/null 2>&1 || true
    rm -f "${target}"
    log_line "Removed ${label}."
  else
    log_line "${label} is not installed."
  fi
}

ensure_runtime_dirs
confirm

for label in "${LABELS[@]}"; do
  uninstall_one "${label}"
done

log_line "AI Stock Hunter launch agents uninstalled. Project data, reports, logs, and ledger state were not deleted."

