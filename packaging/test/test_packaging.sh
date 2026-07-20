#!/usr/bin/env bash
# Validate deterministic source-tree contracts for the vnalpha Debian package.
# Package payload/runtime checks live in test_install_contract.sh.
# Usage: test_packaging.sh [path/to/vnalpha.deb]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGING_DIR="${REPO_ROOT}/packaging"
DEB_TREE="${PACKAGING_DIR}/deb"
DEB_FILE="${1:-}"
PASS=0
FAIL=0

ok() { printf '[OK]   %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '[FAIL] %s\n' "$1" >&2; FAIL=$((FAIL + 1)); }

check_file() {
  path="$1"
  if [[ -f "$path" ]]; then
    ok "file exists: ${path#"${REPO_ROOT}/"}"
  else
    fail "file exists: ${path#"${REPO_ROOT}/"}"
  fi
}

check_executable() {
  path="$1"
  if [[ -x "$path" ]]; then
    ok "executable: ${path#"${REPO_ROOT}/"}"
  else
    fail "executable: ${path#"${REPO_ROOT}/"}"
  fi
}

printf '\n=== Required source files ===\n'
for path in \
  "${DEB_TREE}/DEBIAN/control" \
  "${DEB_TREE}/DEBIAN/conffiles" \
  "${DEB_TREE}/DEBIAN/postinst" \
  "${DEB_TREE}/DEBIAN/prerm" \
  "${DEB_TREE}/DEBIAN/postrm" \
  "${DEB_TREE}/usr/bin/vnalpha" \
  "${DEB_TREE}/usr/bin/vnalpha-poc" \
  "${DEB_TREE}/etc/vnalpha/vnalpha.env" \
  "${DEB_TREE}/usr/lib/systemd/system/openstock-daily-pipeline.service" \
  "${DEB_TREE}/usr/lib/systemd/system/openstock-daily-pipeline.timer" \
  "${PACKAGING_DIR}/build-deb.sh" \
  "${PACKAGING_DIR}/test/test_install_contract.sh"
 do
  check_file "$path"
done

printf '\n=== Executable source files ===\n'
for path in \
  "${DEB_TREE}/DEBIAN/postinst" \
  "${DEB_TREE}/DEBIAN/prerm" \
  "${DEB_TREE}/DEBIAN/postrm" \
  "${DEB_TREE}/usr/bin/vnalpha" \
  "${DEB_TREE}/usr/bin/vnalpha-poc" \
  "${PACKAGING_DIR}/build-deb.sh"
 do
  check_executable "$path"
done

printf '\n=== Shell syntax ===\n'
for path in \
  "${DEB_TREE}/usr/bin/vnalpha" \
  "${DEB_TREE}/usr/bin/vnalpha-poc" \
  "${PACKAGING_DIR}/build-deb.sh" \
  "${PACKAGING_DIR}/test/test_install_contract.sh"
 do
  if bash -n "$path"; then
    ok "bash syntax: ${path#"${REPO_ROOT}/"}"
  else
    fail "bash syntax: ${path#"${REPO_ROOT}/"}"
  fi
done
for path in \
  "${DEB_TREE}/DEBIAN/postinst" \
  "${DEB_TREE}/DEBIAN/prerm" \
  "${DEB_TREE}/DEBIAN/postrm"
 do
  if sh -n "$path"; then
    ok "POSIX shell syntax: ${path#"${REPO_ROOT}/"}"
  else
    fail "POSIX shell syntax: ${path#"${REPO_ROOT}/"}"
  fi
done

printf '\n=== Debian metadata ===\n'
CONTROL="${DEB_TREE}/DEBIAN/control"
for field in Package Version Architecture Depends Description Homepage; do
  if grep -q "^${field}:" "$CONTROL"; then
    ok "control field present: $field"
  else
    fail "control field present: $field"
  fi
done
if grep -qx '/etc/vnalpha/vnalpha.env' "${DEB_TREE}/DEBIAN/conffiles"; then
  ok "vnalpha.env is a Debian conffile"
else
  fail "vnalpha.env is a Debian conffile"
fi
if grep -v '^#' "${DEB_TREE}/DEBIAN/conffiles" | grep -q '/var/lib/openstock'; then
  fail "research state is not managed as a conffile"
else
  ok "research state is not managed as a conffile"
fi

printf '\n=== Launcher and research boundary ===\n'
for launcher in \
  "${DEB_TREE}/usr/bin/vnalpha" \
  "${DEB_TREE}/usr/bin/vnalpha-poc"
 do
  for forbidden in '/v1/order' '/v1/account' '/v1/portfolio' '/v1/trading' 'execute_order'; do
    if grep -v '^#' "$launcher" | grep -Fq "$forbidden"; then
      fail "forbidden surface absent from ${launcher##*/}: $forbidden"
    else
      ok "forbidden surface absent from ${launcher##*/}: $forbidden"
    fi
  done
done
if grep -q '/etc/vnalpha/vnalpha.env' "${DEB_TREE}/usr/bin/vnalpha" && \
   grep -q '/opt/vnalpha/venv/bin/vnalpha' "${DEB_TREE}/usr/bin/vnalpha"; then
  ok "vnalpha launcher loads config and execs the vendored venv"
else
  fail "vnalpha launcher loads config and execs the vendored venv"
fi
if grep -q 'VNALPHA_DEMO_DATE' "${DEB_TREE}/usr/bin/vnalpha-poc" && \
   grep -q 'tui' "${DEB_TREE}/usr/bin/vnalpha-poc"; then
  ok "vnalpha-poc preserves the bounded TUI demo contract"
else
  fail "vnalpha-poc preserves the bounded TUI demo contract"
fi

printf '\n=== State preservation and opt-in scheduling ===\n'
POSTINST="${DEB_TREE}/DEBIAN/postinst"
POSTRM="${DEB_TREE}/DEBIAN/postrm"
if grep -v '^#' "$POSTINST" | grep -Eq 'rm[^\n]*/var/lib/openstock|rm[^\n]*WAREHOUSE_DIR'; then
  fail "postinst never removes research state"
else
  ok "postinst never removes research state"
fi
if grep -v '^#' "$POSTRM" | grep -Eq 'rm[^\n]*/var/lib/openstock|rm[^\n]*WAREHOUSE_DIR'; then
  fail "postrm never removes research state"
else
  ok "postrm never removes research state"
fi
if grep -Eq 'systemctl[[:space:]]+(enable|start).*openstock-daily-pipeline' "$POSTINST"; then
  fail "postinst leaves the daily timer disabled"
else
  ok "postinst leaves the daily timer disabled"
fi
if grep -q 'chmod 0640.*vnalpha.env' "${PACKAGING_DIR}/build-deb.sh" && \
   grep -q 'chown root:openstock /etc/vnalpha/vnalpha.env' "$POSTINST"; then
  ok "vnalpha.env uses the root:openstock credential boundary"
else
  fail "vnalpha.env uses the root:openstock credential boundary"
fi

if [[ -n "$DEB_FILE" ]]; then
  printf '\n=== Delegated package validation ===\n'
  if bash "${PACKAGING_DIR}/test/test_install_contract.sh" "$DEB_FILE"; then
    ok "built package satisfies the install/runtime contract"
  else
    fail "built package satisfies the install/runtime contract"
  fi
fi

printf '\nPassed: %d  Failed: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
