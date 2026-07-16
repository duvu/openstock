#!/usr/bin/env bash
# test_mvp1_start.sh — fixture tests for openstock-mvp1-start (issue #166).
#
# Runs the one-command startup against fake `vnalpha`, `docker` and `curl`
# binaries on PATH so the happy path executes without a live service. Asserts
# it creates persistent directories, is idempotent, emits JSONL events and
# prints the exact launch command in --no-launch mode.
#
# Usage: ./packaging/test/test_mvp1_start.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
START_SCRIPT="${SCRIPT_DIR}/openstock-mvp1-start"

PASS=0
FAIL=0
ok()   { echo "[OK]   $*"; PASS=$(( PASS + 1 )); }
fail() { echo "[FAIL] $*"; FAIL=$(( FAIL + 1 )); }

WORK="$(mktemp -d /tmp/mvp1_start_XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# --- fake binaries: healthy service, idempotent init, launch no-op ---
FAKE_BIN="${WORK}/bin"
mkdir -p "$FAKE_BIN"

cat > "${FAKE_BIN}/curl" <<'FAKE'
#!/usr/bin/env bash
# Always report the health endpoint as HTTP 200.
for a in "$@"; do :; done
if printf '%s\n' "$@" | grep -q "write-out"; then
  echo "200"
fi
exit 0
FAKE

cat > "${FAKE_BIN}/vnalpha" <<'FAKE'
#!/usr/bin/env bash
# init/tui are no-ops; --date accepted.
exit 0
FAKE

chmod +x "${FAKE_BIN}/curl" "${FAKE_BIN}/vnalpha"

_run() {
  # Run with fakes first on PATH, isolated persistent roots, no TUI launch.
  PATH="${FAKE_BIN}:${PATH}" \
  VNALPHA_LOG_ROOT="${WORK}/logs" \
  OPENSTOCK_WAREHOUSE_DIR="${WORK}/warehouse" \
  VNALPHA_KNOWLEDGE_ROOT="${WORK}/knowledge" \
  bash "$START_SCRIPT" --no-launch --skip-preflight
}

# --- test 1: first run succeeds and prints the launch command ---
_out1="$(_run 2>&1)"
_rc1=$?
if [ "$_rc1" -eq 0 ] && echo "$_out1" | grep -q "vnalpha tui --date"; then
  ok "first run succeeds and prints the launch command"
else
  fail "first run failed (rc=$_rc1) or missing launch command"
  echo "$_out1" | sed 's/^/  # /'
fi

# --- test 2: persistent directories were created ---
if [ -d "${WORK}/warehouse" ] && [ -d "${WORK}/knowledge" ] && [ -d "${WORK}/logs" ]; then
  ok "persistent directories created (warehouse, knowledge, logs)"
else
  fail "persistent directories missing after startup"
fi

# --- test 3: re-run is idempotent (still exits 0, does not error on existing dirs) ---
_out2="$(_run 2>&1)"
_rc2=$?
if [ "$_rc2" -eq 0 ] && echo "$_out2" | grep -q "directory present"; then
  ok "second run is idempotent and reuses existing directories"
else
  fail "second run not idempotent (rc=$_rc2)"
  echo "$_out2" | sed 's/^/  # /'
fi

# --- test 4: JSONL events were emitted ---
_jsonl="$(find "${WORK}/logs" -name commands.jsonl 2>/dev/null | head -1)"
if [ -n "$_jsonl" ] && grep -q "MVP1_START_STARTED" "$_jsonl" && grep -q "MVP1_START_COMPLETED" "$_jsonl"; then
  ok "startup emitted MVP1_START_STARTED and MVP1_START_COMPLETED JSONL events"
else
  fail "expected JSONL start/complete events not found"
fi

echo ""
echo "mvp1-start: ${PASS} OK, ${FAIL} FAIL"
[ "$FAIL" -eq 0 ]
