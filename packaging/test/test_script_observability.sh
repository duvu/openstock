#!/usr/bin/env bash
# test_script_observability.sh — Fixture tests for JSONL event emission in shell scripts
#
# Tests S6.10, S6.11 (pipeline JSONL parseability), S7.9, S7.10 (verify JSONL),
# and S8 (backup JSONL).
#
# Usage:
#   ./packaging/test/test_script_observability.sh
#
# Exit codes:
#   0  — all tests passed
#   1  — one or more tests failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PIPELINE_SCRIPT="${SCRIPT_DIR}/openstock-run-pipeline"
VERIFY_SCRIPT="${SCRIPT_DIR}/openstock-verify"
BACKUP_SCRIPT="${SCRIPT_DIR}/openstock-backup-warehouse"

PASS=0
FAIL=0

ok()   { echo "[OK]   $*"; PASS=$(( PASS + 1 )); }
fail() { echo "[FAIL] $*"; FAIL=$(( FAIL + 1 )); }

# --- test: bash -n syntax (already covered by openstock-verify --ci, but re-assert) ---
test_syntax() {
  for script in "$PIPELINE_SCRIPT" "$VERIFY_SCRIPT" "$BACKUP_SCRIPT"; do
    if bash -n "$script" 2>/dev/null; then
      ok "bash -n $(basename "$script") is valid"
    else
      fail "bash -n $(basename "$script") syntax error"
    fi
  done
}

# --- helper: run script and collect JSONL ---
_run_with_logs() {
  local log_root="$1"
  shift
  VNALPHA_LOG_ROOT="$log_root" "$@" >/dev/null 2>&1 || true
  find "$log_root" -name "commands.jsonl" 2>/dev/null | head -1
}

# --- helper: assert JSONL file is parseable ---
_assert_jsonl_parseable() {
  local jsonl_file="$1"
  local label="$2"
  if [ ! -f "$jsonl_file" ]; then
    fail "$label: commands.jsonl not found"
    return
  fi
  local bad_lines=0
  while IFS= read -r line; do
    if ! python3 -c "import json,sys; json.loads(sys.argv[1])" "$line" 2>/dev/null; then
      bad_lines=$(( bad_lines + 1 ))
    fi
  done < "$jsonl_file"
  if [ "$bad_lines" -eq 0 ]; then
    ok "$label: all JSONL lines are valid JSON"
  else
    fail "$label: $bad_lines invalid JSON line(s)"
  fi
}

# --- helper: count event_type in JSONL ---
_count_events() {
  local jsonl_file="$1"
  local event_type="$2"
  python3 -c "
import json, sys
count = 0
with open(sys.argv[1]) as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('event_type') == sys.argv[2]:
                count += 1
        except Exception:
            pass
print(count)
" "$jsonl_file" "$event_type" 2>/dev/null || echo 0
}

# ==============================
# S6: Pipeline script JSONL tests
# ==============================

test_pipeline_jsonl_parseable() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$PIPELINE_SCRIPT" --dry-run --ci-fixture --date 2026-01-01)"
  _assert_jsonl_parseable "$jsonl_file" "pipeline dry-run JSONL"
  rm -rf "$tmpdir"
}

test_pipeline_has_started_event() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$PIPELINE_SCRIPT" --dry-run --ci-fixture --date 2026-01-01)"
  local count
  count="$(_count_events "$jsonl_file" "PIPELINE_STARTED")"
  if [ "$count" -ge 1 ]; then
    ok "pipeline: PIPELINE_STARTED event present"
  else
    fail "pipeline: PIPELINE_STARTED event missing"
  fi
  rm -rf "$tmpdir"
}

test_pipeline_has_step_events() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$PIPELINE_SCRIPT" --dry-run --ci-fixture --date 2026-01-01)"
  local count_started count_succeeded
  count_started="$(_count_events "$jsonl_file" "PIPELINE_STEP_STARTED")"
  count_succeeded="$(_count_events "$jsonl_file" "PIPELINE_STEP_SUCCEEDED")"
  if [ "$count_started" -ge 4 ]; then
    ok "pipeline: $count_started PIPELINE_STEP_STARTED events (>=4 expected for ci-fixture)"
  else
    fail "pipeline: only $count_started PIPELINE_STEP_STARTED events (expected >=4)"
  fi
  if [ "$count_succeeded" -ge 4 ]; then
    ok "pipeline: $count_succeeded PIPELINE_STEP_SUCCEEDED events (>=4 expected)"
  else
    fail "pipeline: only $count_succeeded PIPELINE_STEP_SUCCEEDED events (expected >=4)"
  fi
  rm -rf "$tmpdir"
}

test_pipeline_has_completed_event() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$PIPELINE_SCRIPT" --dry-run --ci-fixture --date 2026-01-01)"
  local count
  count="$(_count_events "$jsonl_file" "PIPELINE_COMPLETED")"
  if [ "$count" -ge 1 ]; then
    ok "pipeline: PIPELINE_COMPLETED event present"
  else
    fail "pipeline: PIPELINE_COMPLETED event missing"
  fi
  rm -rf "$tmpdir"
}

test_pipeline_step_has_step_name() {
  # Verify PIPELINE_STEP_STARTED summary contains 'step=' field
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$PIPELINE_SCRIPT" --dry-run --ci-fixture --date 2026-01-01)"
  if python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('event_type') == 'PIPELINE_STEP_STARTED':
            assert 'step=' in obj.get('summary',''), f'step= missing from {obj}'
print('ok')
" "$jsonl_file" 2>/dev/null | grep -q ok; then
    ok "pipeline: PIPELINE_STEP_STARTED events contain step= in summary"
  else
    fail "pipeline: PIPELINE_STEP_STARTED events missing step= in summary"
  fi
  rm -rf "$tmpdir"
}

# ==============================
# S7: Verify script JSONL tests
# ==============================

test_verify_jsonl_parseable() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$VERIFY_SCRIPT" --ci)"
  _assert_jsonl_parseable "$jsonl_file" "verify --ci JSONL"
  rm -rf "$tmpdir"
}

test_verify_has_started_event() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$VERIFY_SCRIPT" --ci)"
  local count
  count="$(_count_events "$jsonl_file" "VERIFY_STARTED")"
  if [ "$count" -ge 1 ]; then
    ok "verify: VERIFY_STARTED event present"
  else
    fail "verify: VERIFY_STARTED event missing"
  fi
  rm -rf "$tmpdir"
}

test_verify_has_check_events() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$VERIFY_SCRIPT" --ci)"
  local count_passed count_skipped
  count_passed="$(_count_events "$jsonl_file" "VERIFY_CHECK_PASSED")"
  count_skipped="$(_count_events "$jsonl_file" "VERIFY_CHECK_SKIPPED")"
  local total_checks=$(( count_passed + count_skipped ))
  if [ "$total_checks" -ge 5 ]; then
    ok "verify: $total_checks VERIFY_CHECK_* events (PASSED=$count_passed SKIPPED=$count_skipped)"
  else
    fail "verify: only $total_checks VERIFY_CHECK_* events (expected >=5)"
  fi
  rm -rf "$tmpdir"
}

test_verify_has_completed_event() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" bash "$VERIFY_SCRIPT" --ci)"
  local count
  count="$(_count_events "$jsonl_file" "VERIFY_RUN_COMPLETED")"
  if [ "$count" -ge 1 ]; then
    ok "verify: VERIFY_RUN_COMPLETED event present"
  else
    fail "verify: VERIFY_RUN_COMPLETED event missing"
  fi
  rm -rf "$tmpdir"
}

# ==============================
# S8: Backup script JSONL tests
# ==============================

test_backup_lock_failure_logs_backup_failed() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local lock_file="${tmpdir}/pipeline.lock"
  touch "$lock_file"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env OPENSTOCK_LOCK_FILE="$lock_file" bash "$BACKUP_SCRIPT")"
  local count
  count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  if [ "$count" -ge 1 ]; then
    ok "backup: BACKUP_FAILED event written when lock file held"
  else
    fail "backup: BACKUP_FAILED event missing when lock file held"
  fi
  rm -rf "$tmpdir"
}

test_backup_missing_warehouse_logs_backup_failed() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="${tmpdir}/nonexistent.duckdb" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    bash "$BACKUP_SCRIPT")"
  local count
  count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  if [ "$count" -ge 1 ]; then
    ok "backup: BACKUP_FAILED event written when warehouse missing"
  else
    fail "backup: BACKUP_FAILED event missing when warehouse missing"
  fi
  rm -rf "$tmpdir"
}

test_backup_success_logs_backup_created() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local fake_warehouse="${tmpdir}/warehouse.duckdb"
  local backup_dir="${tmpdir}/backups"
  echo "fake-duckdb-content" > "$fake_warehouse"
  mkdir -p "$backup_dir"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    bash "$BACKUP_SCRIPT")"
  local started_count created_count
  started_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_STARTED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  if [ "$started_count" -ge 1 ] && [ "$created_count" -ge 1 ]; then
    ok "backup: BACKUP_STARTED and BACKUP_CREATED events written on success"
  else
    fail "backup: expected BACKUP_STARTED+BACKUP_CREATED, got started=$started_count created=$created_count"
  fi
  rm -rf "$tmpdir"
}

# ==============================
# Run all tests
# ==============================

echo "test_script_observability.sh — JSONL event emission tests"
echo ""

test_syntax
test_pipeline_jsonl_parseable
test_pipeline_has_started_event
test_pipeline_has_step_events
test_pipeline_has_completed_event
test_pipeline_step_has_step_name
test_verify_jsonl_parseable
test_verify_has_started_event
test_verify_has_check_events
test_verify_has_completed_event
test_backup_lock_failure_logs_backup_failed
test_backup_missing_warehouse_logs_backup_failed
test_backup_success_logs_backup_created

echo ""
echo "Results: ${PASS} OK  ${FAIL} FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "Status: PASS"
  exit 0
else
  echo "Status: FAIL"
  exit 1
fi
