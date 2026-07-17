#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERIFY="${ROOT}/packaging/scripts/openstock-verify"
WORK="$(mktemp -d /tmp/openstock_verify_warehouse_XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0
ok() { echo "[OK] $*"; PASS=$(( PASS + 1 )); }
fail() { echo "[FAIL] $*"; FAIL=$(( FAIL + 1 )); }

mkdir -p "${WORK}/bin" "${WORK}/warehouse" "${WORK}/knowledge"
: >"${WORK}/warehouse/warehouse.duckdb"
: >"${WORK}/openstock.env"
: >"${WORK}/vnalpha.env"
printf '%s\n' \
  'version=0.1.0' \
  'commit=0123456789abcdef0123456789abcdef01234567' \
  'tree_state=clean' \
  >"${WORK}/release"
printf '%s\n' \
  'version=0.1.0' \
  'commit=0123456789abcdef0123456789abcdef01234567' \
  'tree_state=dirty' \
  >"${WORK}/dirty-release"
printf '%s\n' \
  'VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true' \
  >"${WORK}/approved-vnalpha.env"

cat >"${WORK}/bin/curl" <<'FAKE'
#!/usr/bin/env bash
url="${*: -1}"
if printf '%s\n' "$@" | grep -q -- '--write-out'; then
  case "$url" in
    */healthz) printf '200' ;;
    */version) printf '%s' "${VERSION_HTTP_CODE:-200}" ;;
    */v1/order|*/v1/account|*/v1/portfolio|*/v1/trading) printf '404' ;;
    *) printf '200' ;;
  esac
else
  case "$url" in
    */v1/providers/capabilities)
      if [ -n "${CAPABILITIES_JSON:-}" ]; then
        printf '%s' "$CAPABILITIES_JSON"
      else
        printf '{"capabilities":{"FIINQUANTX":{"equity.ohlcv":{"supported":true,"explicit_only":true},"index.ohlcv":{"supported":true,"explicit_only":true},"reference.index_membership_snapshot":{"supported":true,"explicit_only":true},"reference.sector_membership_snapshot":{"supported":true,"explicit_only":true}}}}'
      fi
      ;;
    *) printf '{"version":"test"}' ;;
  esac
fi
FAKE

cat >"${WORK}/bin/docker" <<'FAKE'
#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then echo "Docker test"; exit 0; fi
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
  echo "Docker Compose test"
  exit 0
fi
exit 0
FAKE

cat >"${WORK}/bin/vnalpha" <<'FAKE'
#!/usr/bin/env bash
if [ "${1:-}" = "warehouse" ] && [ "${2:-}" = "status" ]; then
  echo "${WAREHOUSE_STATUS_JSON:-{\"ready\":true}}"
  exit "${WAREHOUSE_STATUS_RC:-0}"
fi
exit 0
FAKE
chmod +x "${WORK}/bin/curl" "${WORK}/bin/docker" "${WORK}/bin/vnalpha"

run_verify() {
  PATH="${WORK}/bin:/usr/bin:/bin" \
  HOME="$WORK" \
  OPENSTOCK_ENV_FILE="${WORK}/openstock.env" \
  VNALPHA_ENV_FILE="${WORK}/vnalpha.env" \
  OPENSTOCK_RELEASE_FILE="${WORK}/release" \
  VNALPHA_LOG_ROOT="${WORK}/logs" \
  VNALPHA_WAREHOUSE_PATH="${WORK}/warehouse/warehouse.duckdb" \
  OPENSTOCK_WAREHOUSE_DIR="${WORK}/warehouse" \
  OPENSTOCK_LOCK_FILE="${WORK}/pipeline.lock" \
  OPENSTOCK_MIN_FREE_DISK_MB=0 \
  VNALPHA_KNOWLEDGE_ROOT="${WORK}/knowledge" \
  "$@" bash "$VERIFY" --mvp1
}

drift_output="$(run_verify env WAREHOUSE_STATUS_RC=6 \
  WAREHOUSE_STATUS_JSON='{"ready":false,"code":"schema_drift"}' 2>&1)"
drift_rc=$?
if [ "$drift_rc" -ne 0 ] && echo "$drift_output" | grep -q '^\[FAIL\] MVP1 migrations:'; then
  ok "schema drift fails even when the independent LLM check succeeds"
else
  fail "schema drift was not a verifier blocker"
fi

mv "${WORK}/warehouse/warehouse.duckdb" "${WORK}/warehouse/warehouse.absent"
missing_output="$(run_verify 2>&1)"
missing_rc=$?
mv "${WORK}/warehouse/warehouse.absent" "${WORK}/warehouse/warehouse.duckdb"
if [ "$missing_rc" -ne 0 ] && echo "$missing_output" | grep -q '^\[FAIL\] MVP1 warehouse: file not found:'; then
  ok "missing warehouse fails the MVP1 verifier"
else
  fail "missing warehouse was not a verifier blocker"
fi

corrupt_output="$(run_verify env WAREHOUSE_STATUS_RC=6 \
  WAREHOUSE_STATUS_JSON='{"ready":false,"code":"unreadable"}' 2>&1)"
corrupt_rc=$?
if [ "$corrupt_rc" -ne 0 ] && echo "$corrupt_output" | grep -q '^\[FAIL\] MVP1 migrations:'; then
  ok "corrupt warehouse fails the MVP1 verifier"
else
  fail "corrupt warehouse was not a verifier blocker"
fi

ready_output="$(run_verify env WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
ready_rc=$?
if [ "$ready_rc" -eq 0 ] && echo "$ready_output" | grep -q '^\[OK\]   MVP1 migrations:'; then
  ok "compatible warehouse passes the MVP1 verifier"
else
  fail "compatible warehouse did not pass the verifier"
fi

fiinquantx_output="$(run_verify env \
  VNALPHA_ENV_FILE="${WORK}/approved-vnalpha.env" \
  VNSTOCK_INSTALL_FIINQUANTX=true \
  VNSTOCK_FIINQUANTX_LICENSED=true \
  OPENSTOCK_REFERENCE_SOURCE=VCI \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
fiinquantx_rc=$?
if [ "$fiinquantx_rc" -eq 0 ] && echo "$fiinquantx_output" | grep -q '^\[OK\]   MVP1 FiinQuantX:'; then
  ok "configured FiinQuantX approvals and Gate A capabilities pass"
else
  fail "configured FiinQuantX Gate A readiness did not pass"
fi

missing_persistence_approval_output="$(run_verify env \
  VNSTOCK_INSTALL_FIINQUANTX=true \
  VNSTOCK_FIINQUANTX_LICENSED=true \
  OPENSTOCK_REFERENCE_SOURCE=VCI \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
missing_persistence_approval_rc=$?
if [ "$missing_persistence_approval_rc" -ne 0 ] && echo "$missing_persistence_approval_output" | grep -q '^\[FAIL\] MVP1 FiinQuantX:'; then
  ok "missing persistence approval boolean fails FiinQuantX readiness"
else
  fail "missing persistence approval boolean passed FiinQuantX readiness"
fi

missing_runtime_approval_output="$(run_verify env \
  VNALPHA_ENV_FILE="${WORK}/approved-vnalpha.env" \
  VNSTOCK_INSTALL_FIINQUANTX=true \
  OPENSTOCK_REFERENCE_SOURCE=VCI \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
missing_runtime_approval_rc=$?
if [ "$missing_runtime_approval_rc" -ne 0 ] && echo "$missing_runtime_approval_output" | grep -q '^\[FAIL\] MVP1 FiinQuantX:'; then
  ok "missing runtime approval boolean fails FiinQuantX readiness"
else
  fail "missing runtime approval boolean passed FiinQuantX readiness"
fi

invalid_reference_output="$(run_verify env \
  VNALPHA_ENV_FILE="${WORK}/approved-vnalpha.env" \
  VNSTOCK_INSTALL_FIINQUANTX=true \
  VNSTOCK_FIINQUANTX_LICENSED=true \
  OPENSTOCK_REFERENCE_SOURCE=GARBAGE \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
invalid_reference_rc=$?
if [ "$invalid_reference_rc" -ne 0 ] && echo "$invalid_reference_output" | grep -q '^\[FAIL\] MVP1 FiinQuantX:'; then
  ok "unapproved reference provider fails FiinQuantX readiness"
else
  fail "unapproved reference provider passed FiinQuantX readiness"
fi

cross_provider_output="$(run_verify env \
  VNALPHA_ENV_FILE="${WORK}/approved-vnalpha.env" \
  VNSTOCK_INSTALL_FIINQUANTX=true \
  VNSTOCK_FIINQUANTX_LICENSED=true \
  OPENSTOCK_REFERENCE_SOURCE=VCI \
  CAPABILITIES_JSON='{"capabilities":{"FIINQUANTX":{},"OTHER":{"equity.ohlcv":{},"index.ohlcv":{},"reference.index_membership_snapshot":{},"reference.sector_membership_snapshot":{}}}}' \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
cross_provider_rc=$?
if [ "$cross_provider_rc" -ne 0 ] && echo "$cross_provider_output" | grep -q '^\[FAIL\] MVP1 FiinQuantX:'; then
  ok "cross-provider capability text fails FiinQuantX readiness"
else
  fail "cross-provider capability text passed FiinQuantX readiness"
fi

version_404_output="$(run_verify env \
  VERSION_HTTP_CODE=404 \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
if echo "$version_404_output" | grep -q '^\[WARN\] MVP1 service: version endpoint HTTP 404' && \
   ! echo "$version_404_output" | grep -q '^\[OK\]   MVP1 service: version endpoint reachable'; then
  ok "version endpoint 404 is not reported as reachable"
else
  fail "version endpoint 404 was reported as reachable"
fi

dirty_release_output="$(run_verify env \
  OPENSTOCK_RELEASE_FILE="${WORK}/dirty-release" \
  WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
dirty_release_rc=$?
if [ "$dirty_release_rc" -ne 0 ] && echo "$dirty_release_output" | grep -q '^\[FAIL\] MVP1 release: candidate metadata is not clean'; then
  ok "dirty candidate metadata fails exact-release readiness"
else
  fail "dirty candidate metadata passed exact-release readiness"
fi

flock "${WORK}/pipeline.lock" -c 'sleep 10' &
lock_pid=$!
sleep 0.1
locked_output="$(run_verify env WAREHOUSE_STATUS_RC=0 \
  WAREHOUSE_STATUS_JSON='{"ready":true,"code":"ready"}' 2>&1)"
kill "$lock_pid" 2>/dev/null || true
wait "$lock_pid" 2>/dev/null || true
if echo "$locked_output" | grep -q '^\[WARN\] MVP1 writer lock: active writer'; then
  ok "active writer lock is reported truthfully"
else
  fail "active writer lock was not reported"
fi

echo "verify warehouse: ${PASS} OK, ${FAIL} FAIL"
[ "$FAIL" -eq 0 ]
