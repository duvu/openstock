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
mkdir -p "${WORK}/openstock"
: >"${WORK}/openstock/docker-compose.yml"

cat > "${FAKE_BIN}/curl" <<'FAKE'
#!/usr/bin/env bash
for a in "$@"; do :; done
if printf '%s\n' "$@" | grep -q "write-out"; then
  if [ "${UNHEALTHY:-false}" = "true" ]; then echo "000"; else echo "200"; fi
fi
exit 0
FAKE

cat > "${FAKE_BIN}/vnalpha" <<'FAKE'
#!/usr/bin/env bash
if [ "${FAIL_INIT:-false}" = "true" ] && [ "${1:-}" = "init" ]; then
  echo "init failed: ${VNALPHA_LLM_API_KEY:-no-secret}" >&2
  exit 9
fi
exit 0
FAKE

cat > "${FAKE_BIN}/docker" <<'FAKE'
#!/usr/bin/env bash
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then exit 0; fi
if [ "${1:-}" = "compose" ] && printf '%s\n' "$@" | grep -q '^up$'; then
  printf 'compose args: %s\n' "$*" >&2
  echo "compose failed: ${VNALPHA_LLM_API_KEY:-no-secret}" >&2
  if [ "${FAIL_COMPOSE:-false}" = "true" ]; then exit 8; fi
fi
exit 0
FAKE

cat > "${FAKE_BIN}/openstock-verify" <<'FAKE'
#!/usr/bin/env bash
echo "preflight failed: ${VNALPHA_LLM_API_KEY:-no-secret}" >&2
if [ "${FAIL_PREFLIGHT:-false}" = "true" ]; then exit 7; fi
exit 0
FAKE

chmod +x "${FAKE_BIN}/curl" "${FAKE_BIN}/vnalpha" \
  "${FAKE_BIN}/docker" "${FAKE_BIN}/openstock-verify"

_run() {
  # Run with fakes first on PATH, isolated persistent roots, no TUI launch.
  PATH="${FAKE_BIN}:${PATH}" \
  VNALPHA_LOG_ROOT="${WORK}/logs" \
  OPENSTOCK_HOME="${WORK}/openstock" \
  OPENSTOCK_WAREHOUSE_DIR="${WORK}/warehouse" \
  VNALPHA_KNOWLEDGE_ROOT="${WORK}/knowledge" \
  bash "$START_SCRIPT" --no-launch --skip-preflight
}

_run_preflight() {
  PATH="${FAKE_BIN}:${PATH}" \
  VNALPHA_LOG_ROOT="${WORK}/logs" \
  OPENSTOCK_HOME="${WORK}/openstock" \
  OPENSTOCK_WAREHOUSE_DIR="${WORK}/warehouse" \
  VNALPHA_KNOWLEDGE_ROOT="${WORK}/knowledge" \
  VNALPHA_LLM_API_KEY="startup-secret-fixture" \
  "$@" bash "$START_SCRIPT" --no-launch
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

_init_out="$(_run_preflight env FAIL_INIT=true 2>&1)"
_init_rc=$?
_init_log="$(printf '%s\n' "$_init_out" | sed -n 's/.*inspect //p' | tail -1)"
if [ "$_init_rc" -eq 9 ] && [ -s "$_init_log" ] && \
   [ "$(stat -c '%a' "$_init_log")" = "600" ] && \
   echo "$_init_out" | grep -q "$_init_log" && \
   ! grep -q "startup-secret-fixture" "$_init_log" && \
   ! find "${WORK}/logs" -name '*.raw' -type f -print -quit | grep -q .; then
  ok "init failure preserves exit and writes an exact redacted log"
else
  fail "init failure did not preserve exit/log/redaction contract"
  echo "$_init_out" | sed 's/^/  # /'
fi

_preflight_out="$(_run_preflight env FAIL_PREFLIGHT=true 2>&1)"
_preflight_rc=$?
_preflight_log="$(find "${WORK}/logs" -name mvp1-preflight.log -type f -print | tail -1)"
if [ "$_preflight_rc" -eq 7 ] && [ -s "$_preflight_log" ] && \
   echo "$_preflight_out" | grep -q "$_preflight_log"; then
  ok "preflight failure preserves exit and writes an exact log"
else
  fail "preflight failure did not preserve exit/log contract"
  echo "$_preflight_out" | sed 's/^/  # /'
fi

_compose_out="$(_run_preflight env UNHEALTHY=true FAIL_COMPOSE=true 2>&1)"
_compose_rc=$?
_compose_log="$(find "${WORK}/logs" -name compose-up.log -type f -print | tail -1)"
if [ "$_compose_rc" -eq 8 ] && [ -s "$_compose_log" ] && \
   echo "$_compose_out" | grep -q "$_compose_log" && \
   grep -q -- "--project-directory ${WORK}/openstock up -d vnstock-service" "$_compose_log"; then
  ok "compose failure preserves exit and writes an exact log"
else
  fail "compose failure did not preserve exit/log contract"
  echo "$_compose_out" | sed 's/^/  # /'
fi

_isolated_start="${WORK}/isolated-start"
cp "$START_SCRIPT" "$_isolated_start"
chmod +x "$_isolated_start"
rm -f "${FAKE_BIN}/openstock-verify"
_missing_out="$(PATH="${FAKE_BIN}:/bin" \
  VNALPHA_LOG_ROOT="${WORK}/logs" \
  OPENSTOCK_WAREHOUSE_DIR="${WORK}/warehouse" \
  VNALPHA_KNOWLEDGE_ROOT="${WORK}/knowledge" \
  bash "$_isolated_start" --no-launch 2>&1)"
_missing_rc=$?
if [ "$_missing_rc" -ne 0 ] && echo "$_missing_out" | grep -q "openstock-verify"; then
  ok "missing verifier blocks startup with remediation"
else
  fail "missing verifier did not block startup"
fi

echo ""
echo "mvp1-start: ${PASS} OK, ${FAIL} FAIL"
[ "$FAIL" -eq 0 ]
