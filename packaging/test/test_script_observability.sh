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
  for script in "$PIPELINE_SCRIPT" "$VERIFY_SCRIPT" "$BACKUP_SCRIPT" "$RESTORE_SCRIPT"; do
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

# --- helper: create a real (verifiable) DuckDB file, or return 1 if unavailable ---
_make_duckdb() {
  local db_path="$1"
  local py=""
  py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
  [ -n "$py" ] || return 1
  "$py" - "$db_path" <<'PY' 2>/dev/null || return 1
import sys
try:
    import duckdb
except Exception:
    sys.exit(1)
con = duckdb.connect(sys.argv[1])
con.execute("CREATE TABLE t(a INTEGER)")
con.execute("INSERT INTO t VALUES (1),(2),(3)")
con.execute("CHECKPOINT")
con.close()
PY
  return 0
}

_make_sqlite_queue() {
  local database_path="$1"
  local value="$2"
  python3 - "$database_path" "$value" <<'PY' 2>/dev/null || return 1
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
connection.execute("CREATE TABLE queue_probe(value TEXT NOT NULL)")
connection.execute("INSERT INTO queue_probe VALUES (?)", (sys.argv[2],))
connection.commit()
connection.close()
PY
}

_sqlite_queue_value() {
  python3 - "$1" <<'PY' 2>/dev/null
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
print(connection.execute("SELECT value FROM queue_probe").fetchone()[0])
connection.close()
PY
}

RESTORE_SCRIPT="${SCRIPT_DIR}/openstock-restore-warehouse"

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
  local fake_warehouse="${tmpdir}/warehouse.duckdb"
  echo "fake-duckdb-content" > "$fake_warehouse"
  # Hold the SAME exclusive flock a writer would hold, in a background process,
  # so the backup must actually contend for the lock (file existence alone must
  # not block, and must not falsely succeed either).
  exec 210>"$lock_file"
  flock -n 210
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_LOCK_FILE="$lock_file" \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    bash "$BACKUP_SCRIPT")"
  flock -u 210
  exec 210>&-
  local failed_count created_count
  failed_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  if [ "$failed_count" -ge 1 ] && [ "$created_count" -eq 0 ]; then
    ok "backup: BACKUP_FAILED (no BACKUP_CREATED) when writer holds the flock"
  else
    fail "backup: expected BACKUP_FAILED and no BACKUP_CREATED under held lock, got failed=$failed_count created=$created_count"
  fi
  local queue_lock_file="${tmpdir}/provisioner.lock"
  exec 213>"$queue_lock_file"
  flock -n 213
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_LOCK_FILE="${tmpdir}/free-pipeline.lock" \
    OPENSTOCK_PROVISIONING_LOCK_FILE="$queue_lock_file" \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    bash "$BACKUP_SCRIPT")"
  flock -u 213
  exec 213>&-
  failed_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  if [ "$failed_count" -ge 1 ] && [ "$created_count" -eq 0 ]; then
    ok "backup: refuses a snapshot while the provisioner holds the queue lock"
  else
    fail "backup: expected queue-lock failure, got failed=$failed_count created=$created_count"
  fi
  rm -rf "$tmpdir"
}

test_backup_force_does_not_bypass_writer_lock() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local lock_file="${tmpdir}/pipeline.lock"
  local fake_warehouse="${tmpdir}/warehouse.duckdb"
  echo "fake-duckdb-content" > "$fake_warehouse"
  exec 211>"$lock_file"
  flock -n 211
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_LOCK_FILE="$lock_file" \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    bash "$BACKUP_SCRIPT" --force)"
  flock -u 211
  exec 211>&-
  local failed_count created_count
  failed_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  if [ "$failed_count" -ge 1 ] && [ "$created_count" -eq 0 ]; then
    ok "backup: --force does not bypass an active writer lock"
  else
    fail "backup: --force wrongly bypassed the lock, got failed=$failed_count created=$created_count"
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
  local force_flag=""
  if ! _make_duckdb "$fake_warehouse"; then
    # No duckdb runtime — exercise the success path with --force (verification
    # is skipped, but the copy/atomic-publish path is still covered).
    echo "fake-duckdb-content" > "$fake_warehouse"
    force_flag="--force"
  fi
  local queue_path="${tmpdir}/provisioning.sqlite3"
  if ! _make_sqlite_queue "$queue_path" "backup"; then
    fail "backup: could not create SQLite queue fixture"
    rm -rf "$tmpdir"; return
  fi
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    OPENSTOCK_PROVISIONING_LOCK_FILE="${tmpdir}/provisioner.lock" \
    OPENSTOCK_QUEUE_PATH="$queue_path" \
    bash "$BACKUP_SCRIPT" $force_flag)"
  local started_count created_count backup_count queue_backup_count
  started_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_STARTED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  backup_count="$(find "${tmpdir}/backups" -name 'warehouse-*.duckdb' 2>/dev/null | wc -l)"
  queue_backup_count="$(find "${tmpdir}/backups" -name 'warehouse-*.queue.sqlite3' 2>/dev/null | wc -l)"
  if [ "$started_count" -ge 1 ] && [ "$created_count" -ge 1 ] && [ "$backup_count" -ge 1 ] && [ "$queue_backup_count" -eq 1 ]; then
    ok "backup: publishes one verified warehouse/queue snapshot pair"
  else
    fail "backup: expected started+created+pair, got started=$started_count created=$created_count warehouse=$backup_count queue=$queue_backup_count"
  fi
  # No leftover .partial files.
  local partial_count
  partial_count="$(find "${tmpdir}/backups" -name '*.partial' 2>/dev/null | wc -l)"
  if [ "$partial_count" -eq 0 ]; then
    ok "backup: no .partial files remain after success"
  else
    fail "backup: $partial_count leftover .partial file(s)"
  fi
  rm -rf "$tmpdir"
}

test_backup_corrupt_source_fails_verification() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local fake_warehouse="${tmpdir}/warehouse.duckdb"
  # Not a valid DuckDB file: verification must reject it and publish nothing.
  echo "definitely-not-a-duckdb-file" > "$fake_warehouse"
  if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    ok "backup: verification test skipped (no python runtime)"
    rm -rf "$tmpdir"; return
  fi
  if ! python3 -c "import duckdb" >/dev/null 2>&1 \
     && ! python -c "import duckdb" >/dev/null 2>&1; then
    ok "backup: verification test skipped (no duckdb module)"
    rm -rf "$tmpdir"; return
  fi
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$fake_warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    bash "$BACKUP_SCRIPT")"
  local failed_count created_count file_count
  failed_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_FAILED")"
  created_count="$(_count_events "${jsonl_file:-/dev/null}" "BACKUP_CREATED")"
  file_count="$(find "${tmpdir}/backups" -name 'warehouse-*.duckdb' 2>/dev/null | wc -l)"
  if [ "$failed_count" -ge 1 ] && [ "$created_count" -eq 0 ] && [ "$file_count" -eq 0 ]; then
    ok "backup: corrupt source fails verification and publishes no backup"
  else
    fail "backup: corrupt source not rejected, got failed=$failed_count created=$created_count files=$file_count"
  fi
  rm -rf "$tmpdir"
}

# ==============================
# S9: Restore script tests
# ==============================

test_restore_success_replaces_and_verifies() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local warehouse="${tmpdir}/warehouse.duckdb"
  local backup_dir="${tmpdir}/backups"
  mkdir -p "$backup_dir"
  local backup="${backup_dir}/warehouse-20240101-000000.duckdb"
  local backup_queue="${backup%.duckdb}.queue.sqlite3"
  local queue_path="${tmpdir}/provisioning.sqlite3"
  if ! _make_duckdb "$backup"; then
    ok "restore: success test skipped (no duckdb runtime)"
    rm -rf "$tmpdir"; return
  fi
  _make_duckdb "$warehouse"
  _make_sqlite_queue "$backup_queue" "backup"
  _make_sqlite_queue "$queue_path" "live"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    OPENSTOCK_PROVISIONING_LOCK_FILE="${tmpdir}/provisioner.lock" \
    OPENSTOCK_QUEUE_PATH="$queue_path" \
    bash "$RESTORE_SCRIPT" --backup "$backup" --yes)"
  local started completed pre_backup
  started="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_STARTED")"
  completed="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_COMPLETED")"
  pre_backup="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_PRE_BACKUP")"
  if [ "$started" -ge 1 ] && [ "$completed" -ge 1 ] && [ "$pre_backup" -ge 1 ] && [ -f "$warehouse" ] && [ "$(_sqlite_queue_value "$queue_path")" = "backup" ]; then
    ok "restore: restores the verified warehouse/queue pair"
  else
    fail "restore: expected paired success, got started=$started pre=$pre_backup completed=$completed"
  fi
  rm -rf "$tmpdir"
}

test_restore_corrupt_backup_leaves_warehouse_intact() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local warehouse="${tmpdir}/warehouse.duckdb"
  local backup_dir="${tmpdir}/backups"
  mkdir -p "$backup_dir"
  local backup="${backup_dir}/warehouse-20240101-000000.duckdb"
  if ! _make_duckdb "$warehouse"; then
    ok "restore: rollback test skipped (no duckdb runtime)"
    rm -rf "$tmpdir"; return
  fi
  # Corrupt backup: restore must reject it BEFORE touching the live warehouse.
  echo "corrupt-backup" > "$backup"
  : > "${backup%.duckdb}.queue.absent"
  local original_sum
  original_sum="$(md5sum "$warehouse" | awk '{print $1}')"
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="${tmpdir}/no.lock" \
    bash "$RESTORE_SCRIPT" --backup "$backup" --yes)"
  local failed completed
  failed="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_FAILED")"
  completed="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_COMPLETED")"
  local new_sum
  new_sum="$(md5sum "$warehouse" | awk '{print $1}')"
  if [ "$failed" -ge 1 ] && [ "$completed" -eq 0 ] && [ "$original_sum" = "$new_sum" ]; then
    ok "restore: corrupt backup rejected and original warehouse left intact"
  else
    fail "restore: corrupt backup not handled safely, failed=$failed completed=$completed intact=$([ "$original_sum" = "$new_sum" ] && echo yes || echo no)"
  fi
  rm -rf "$tmpdir"
}

test_restore_lock_contention_aborts() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local warehouse="${tmpdir}/warehouse.duckdb"
  local lock_file="${tmpdir}/pipeline.lock"
  mkdir -p "${tmpdir}/backups"
  local backup="${tmpdir}/backups/warehouse-20240101-000000.duckdb"
  echo "content" > "$warehouse"
  echo "content" > "$backup"
  : > "${backup%.duckdb}.queue.absent"
  exec 212>"$lock_file"
  flock -n 212
  local jsonl_file
  jsonl_file="$(_run_with_logs "$tmpdir" env \
    OPENSTOCK_WAREHOUSE_PATH="$warehouse" \
    OPENSTOCK_WAREHOUSE_DIR="$tmpdir" \
    OPENSTOCK_LOCK_FILE="$lock_file" \
    bash "$RESTORE_SCRIPT" --backup "$backup" --yes)"
  flock -u 212
  exec 212>&-
  local failed completed
  failed="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_FAILED")"
  completed="$(_count_events "${jsonl_file:-/dev/null}" "RESTORE_COMPLETED")"
  if [ "$failed" -ge 1 ] && [ "$completed" -eq 0 ]; then
    ok "restore: aborts under active writer lock"
  else
    fail "restore: expected abort under held lock, got failed=$failed completed=$completed"
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
test_backup_force_does_not_bypass_writer_lock
test_backup_missing_warehouse_logs_backup_failed
test_backup_success_logs_backup_created
test_backup_corrupt_source_fails_verification
test_restore_success_replaces_and_verifies
test_restore_corrupt_backup_leaves_warehouse_intact
test_restore_lock_contention_aborts

echo ""
echo "Results: ${PASS} OK  ${FAIL} FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "Status: PASS"
  exit 0
else
  echo "Status: FAIL"
  exit 1
fi
