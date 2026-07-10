#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

LABELS=(
  "com.aistockhunter.daily-pipeline"
  "com.aistockhunter.paper-refresh"
)
USER_AGENT_DIR="${HOME}/Library/LaunchAgents"
UID_VALUE="$(id -u)"

show_one() {
  local label="$1"
  local target="${USER_AGENT_DIR}/${label}.plist"

  printf "\n%s\n" "${label}"
  if [[ -f "${target}" ]]; then
    printf "  installed: yes (%s)\n" "${target}"
  else
    printf "  installed: no\n"
  fi

  if launchctl print "gui/${UID_VALUE}/${label}" >/dev/null 2>&1; then
    printf "  loaded: yes\n"
  else
    printf "  loaded: no\n"
  fi
}

show_log_tail() {
  local name="$1"
  local path="${LOG_DIR}/${name}"

  printf "\nLast log lines: %s\n" "${path}"
  if [[ -f "${path}" ]]; then
    tail -n 8 "${path}"
  else
    printf "  no log file yet\n"
  fi
}

ensure_runtime_dirs

for label in "${LABELS[@]}"; do
  show_one "${label}"
done

show_log_tail "daily-pipeline.log"
show_log_tail "daily-pipeline-error.log"
show_log_tail "paper-refresh.log"
show_log_tail "paper-refresh-error.log"

printf "\nTroubleshooting next steps:\n"
printf "  Validate plists: plutil -lint %s/automation/launchd/*.plist\n" "${PROJECT_ROOT}"
printf "  Test daily wrapper: %s/automation/scripts/run_daily_pipeline.sh --dry-run\n" "${PROJECT_ROOT}"
printf "  Test refresh wrapper: %s/automation/scripts/refresh_paper_ledger.sh --dry-run --force\n" "${PROJECT_ROOT}"

