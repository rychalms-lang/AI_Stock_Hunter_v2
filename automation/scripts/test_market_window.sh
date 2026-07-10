#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=automation/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

failures=0

assert_window() {
  local label="$1"
  local hhmm="$2"
  local weekday="$3"
  local expected="$4"
  local actual="closed"

  if AI_STOCK_HUNTER_TEST_MARKET_HHMM="${hhmm}" \
    AI_STOCK_HUNTER_TEST_MARKET_WEEKDAY="${weekday}" \
    is_regular_market_window_ny; then
    actual="open"
  fi

  if [[ "${actual}" == "${expected}" ]]; then
    printf "PASS %s: hhmm=%s weekday=%s expected=%s\n" "${label}" "${hhmm}" "${weekday}" "${expected}"
  else
    printf "FAIL %s: hhmm=%s weekday=%s expected=%s actual=%s\n" "${label}" "${hhmm}" "${weekday}" "${expected}" "${actual}" >&2
    failures=$((failures + 1))
  fi
}

assert_minutes() {
  local hhmm="$1"
  local expected="$2"
  local actual

  actual="$(hhmm_to_minutes "${hhmm}")"
  if [[ "${actual}" == "${expected}" ]]; then
    printf "PASS minutes: hhmm=%s minutes=%s\n" "${hhmm}" "${actual}"
  else
    printf "FAIL minutes: hhmm=%s expected=%s actual=%s\n" "${hhmm}" "${expected}" "${actual}" >&2
    failures=$((failures + 1))
  fi
}

assert_minutes "0000" "0"
assert_minutes "0905" "545"
assert_minutes "0930" "570"
assert_minutes "1600" "960"
assert_minutes "1800" "1080"

assert_window "09:05 before open" "0905" "5" "closed"
assert_window "09:29 before open" "0929" "5" "closed"
assert_window "09:30 open boundary" "0930" "5" "open"
assert_window "12:00 midday" "1200" "5" "open"
assert_window "15:59 before close" "1559" "5" "open"
assert_window "16:00 close boundary" "1600" "5" "closed"
assert_window "16:05 after close" "1605" "5" "closed"
assert_window "midnight" "0000" "5" "closed"
assert_window "weekend midday" "1200" "6" "closed"

if (( failures > 0 )); then
  exit 1
fi

printf "All market-window tests passed.\n"

