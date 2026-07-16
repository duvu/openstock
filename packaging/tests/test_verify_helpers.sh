#!/usr/bin/env bash
# test_verify_helpers.sh — TAP-style unit tests for openstock-verify helper functions
# Tests ok/warn/fail/skip output format and counter behavior without live services.
# Usage: bash packaging/tests/test_verify_helpers.sh
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo /home/beou/IdeaProjects/openstock)"

# --- TAP harness ---
TAP_COUNT=0
TAP_FAIL=0

tap_ok() {
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  echo "ok ${TAP_COUNT} - $1"
}

tap_not_ok() {
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - $1"
  echo "  # got:      $2"
  echo "  # expected: $3"
}

assert_eq() {
  local desc="$1" got="$2" expected="$3"
  if [ "$got" = "$expected" ]; then
    tap_ok "$desc"
  else
    tap_not_ok "$desc" "$got" "$expected"
  fi
}

# --- load helpers in isolation ---
# Define the exact helper functions from openstock-verify in a subshell-safe way.
# We source a minimal stub so tests are independent of the full script's side-effects.
_helpers_tmpfile="$(mktemp /tmp/openstock_verify_helpers_XXXXXX.sh)"
trap 'rm -f "$_helpers_tmpfile"' EXIT

cat > "$_helpers_tmpfile" <<'HELPERS'
PASS=0
WARN=0
FAIL=0
ok()   { echo "[OK]   $*"; PASS=$(( PASS + 1 )); }
warn() { echo "[WARN] $*"; WARN=$(( WARN + 1 )); }
fail() { echo "[FAIL] $*"; FAIL=$(( FAIL + 1 )); }
skip() { echo "[SKIP] $*"; }
HELPERS

# --- test 1: ok() output format ---
_out="$(bash -c ". \"$_helpers_tmpfile\"; ok 'all good'")"
assert_eq "ok() prints [OK]   prefix" "$_out" "[OK]   all good"

# --- test 2: ok() increments PASS ---
_pass="$(bash -c ". \"$_helpers_tmpfile\"; ok 'msg'; echo \$PASS")"
assert_eq "ok() increments PASS to 1" "$_pass" "$(printf '[OK]   msg\n1')"

# --- test 3: warn() output format ---
_out="$(bash -c ". \"$_helpers_tmpfile\"; warn 'something off'")"
assert_eq "warn() prints [WARN] prefix" "$_out" "[WARN] something off"

# --- test 4: warn() increments WARN ---
_warn="$(bash -c ". \"$_helpers_tmpfile\"; warn 'msg'; echo \$WARN")"
assert_eq "warn() increments WARN to 1" "$_warn" "$(printf '[WARN] msg\n1')"

# --- test 5: fail() output format ---
_out="$(bash -c ". \"$_helpers_tmpfile\"; fail 'broken'")"
assert_eq "fail() prints [FAIL] prefix" "$_out" "[FAIL] broken"

# --- test 6: fail() increments FAIL ---
_fail="$(bash -c ". \"$_helpers_tmpfile\"; fail 'msg'; echo \$FAIL")"
assert_eq "fail() increments FAIL to 1" "$_fail" "$(printf '[FAIL] msg\n1')"

# --- test 7: skip() output format ---
_out="$(bash -c ". \"$_helpers_tmpfile\"; skip 'not now'")"
assert_eq "skip() prints [SKIP] prefix" "$_out" "[SKIP] not now"

# --- test 8: skip() does NOT increment any counter ---
_counters="$(bash -c ". \"$_helpers_tmpfile\"; skip 'msg'; echo \${PASS}:\${WARN}:\${FAIL}")"
assert_eq "skip() leaves all counters at 0" "$_counters" "$(printf '[SKIP] msg\n0:0:0')"

# --- test 9: multiple ok() calls accumulate PASS ---
_multi="$(bash -c ". \"$_helpers_tmpfile\"; ok 'a'; ok 'b'; ok 'c'; echo \$PASS")"
assert_eq "three ok() calls set PASS=3" "$(echo "$_multi" | tail -1)" "3"

# --- test 10: openstock-verify --ci exits 0 (no live services required) ---
if bash packaging/scripts/openstock-verify --ci >/dev/null 2>&1; then
  tap_ok "openstock-verify --ci exits 0"
else
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-verify --ci exits 0"
  echo "  # script returned non-zero in --ci mode"
fi

# --- test 11: openstock-verify --ci produces no [FAIL] lines ---
_ci_output="$(bash packaging/scripts/openstock-verify --ci 2>&1 || true)"
if echo "$_ci_output" | grep -q '^\[FAIL\]'; then
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-verify --ci emits no [FAIL] lines"
  echo "  # found [FAIL] in CI output:"
  echo "$_ci_output" | grep '^\[FAIL\]' | sed 's/^/  # /'
else
  tap_ok "openstock-verify --ci emits no [FAIL] lines"
fi

# --- test 12: openstock-verify --mvp1 --ci exits 0 (issue #166) ---
if bash packaging/scripts/openstock-verify --mvp1 --ci >/dev/null 2>&1; then
  tap_ok "openstock-verify --mvp1 --ci exits 0"
else
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-verify --mvp1 --ci exits 0"
  echo "  # script returned non-zero in --mvp1 --ci mode"
fi

# --- test 13: openstock-verify --mvp1 --ci emits no [FAIL] lines ---
_mvp1_output="$(bash packaging/scripts/openstock-verify --mvp1 --ci 2>&1 || true)"
if echo "$_mvp1_output" | grep -q '^\[FAIL\]'; then
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-verify --mvp1 --ci emits no [FAIL] lines"
  echo "$_mvp1_output" | grep '^\[FAIL\]' | sed 's/^/  # /'
else
  tap_ok "openstock-verify --mvp1 --ci emits no [FAIL] lines"
fi

# --- test 14: openstock-mvp1-start --help exits 0 and documents flags ---
_start_help="$(bash packaging/scripts/openstock-mvp1-start --help 2>&1)"
if echo "$_start_help" | grep -q -- "--no-launch"; then
  tap_ok "openstock-mvp1-start --help documents --no-launch"
else
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-mvp1-start --help documents --no-launch"
fi

# --- test 15: openstock-mvp1-start rejects unknown options ---
if bash packaging/scripts/openstock-mvp1-start --bogus >/dev/null 2>&1; then
  TAP_COUNT=$(( TAP_COUNT + 1 ))
  TAP_FAIL=$(( TAP_FAIL + 1 ))
  echo "not ok ${TAP_COUNT} - openstock-mvp1-start rejects unknown options"
else
  tap_ok "openstock-mvp1-start rejects unknown options"
fi

# --- TAP summary ---
echo ""
echo "1..${TAP_COUNT}"
echo "# tests: ${TAP_COUNT}  failed: ${TAP_FAIL}"

if [ "${TAP_FAIL}" -eq 0 ]; then
  echo "# All tests passed."
  exit 0
else
  echo "# ${TAP_FAIL} test(s) FAILED."
  exit 1
fi
