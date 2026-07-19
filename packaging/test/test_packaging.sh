#!/usr/bin/env bash
# test_packaging.sh — Validation stubs for vnalpha Debian package
#
# Usage:
#   ./packaging/test/test_packaging.sh [path/to/vnalpha.deb]
#
# With a .deb path, performs structural checks on the package file.
# Without a .deb path, performs tree/script checks on the staging tree.
#
# Exit codes:
#   0  — all checks passed
#   1  — one or more checks failed
#
# These tests are designed to run in CI without root privileges and
# without actually installing the package. They validate:
#   - Package tree structure
#   - Required files present and permissions correct
#   - Launcher scripts are syntactically valid bash
#   - DEBIAN/control has required fields
#   - postinst/prerm/postrm are syntactically valid sh
#   - .deb file contents (if path provided)
#   - Launcher scripts contain no references to forbidden endpoints
#
# TODO(maintainer): extend with:
#   - Test that postinst creates /opt/vnalpha/venv in a chroot
#   - Test that postrm does NOT remove /var/lib/openstock/warehouse
#   - Test that vnalpha launcher forwards args correctly (requires install)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGING_DIR="${REPO_ROOT}/packaging"
DEB_TREE="${PACKAGING_DIR}/deb"
DEB_FILE="${1:-}"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ok() {
  echo "[OK]  $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "[FAIL] $1" >&2
  FAIL=$((FAIL + 1))
}

check_file_exists() {
  local path="$1"
  if [ -f "${path}" ]; then
    ok "File exists: ${path#"${REPO_ROOT}/"}"
  else
    fail "Missing file: ${path#"${REPO_ROOT}/"}"
  fi
}

check_executable() {
  local path="$1"
  if [ -x "${path}" ]; then
    ok "Executable: ${path#"${REPO_ROOT}/"}"
  else
    fail "Not executable: ${path#"${REPO_ROOT}/"}"
  fi
}

check_syntax_bash() {
  local path="$1"
  if bash -n "${path}" 2>/dev/null; then
    ok "Bash syntax OK: ${path#"${REPO_ROOT}/"}"
  else
    fail "Bash syntax error: ${path#"${REPO_ROOT}/"}"
  fi
}

check_syntax_sh() {
  local path="$1"
  if sh -n "${path}" 2>/dev/null; then
    ok "sh syntax OK: ${path#"${REPO_ROOT}/"}"
  else
    fail "sh syntax error: ${path#"${REPO_ROOT}/"}"
  fi
}

# ---------------------------------------------------------------------------
# Test group: required files exist
# ---------------------------------------------------------------------------

echo ""
echo "=== Required files ==="

check_file_exists "${DEB_TREE}/DEBIAN/control"
check_file_exists "${DEB_TREE}/DEBIAN/conffiles"
check_file_exists "${DEB_TREE}/DEBIAN/postinst"
check_file_exists "${DEB_TREE}/DEBIAN/prerm"
check_file_exists "${DEB_TREE}/DEBIAN/postrm"
check_file_exists "${DEB_TREE}/usr/bin/vnalpha"
check_file_exists "${DEB_TREE}/usr/bin/vnalpha-poc"
check_file_exists "${DEB_TREE}/etc/vnalpha/vnalpha.env"
check_file_exists "${PACKAGING_DIR}/build-deb.sh"

# ---------------------------------------------------------------------------
# Test group: permissions
# ---------------------------------------------------------------------------

echo ""
echo "=== Permissions ==="

check_executable "${DEB_TREE}/usr/bin/vnalpha"
check_executable "${DEB_TREE}/usr/bin/vnalpha-poc"
check_executable "${DEB_TREE}/DEBIAN/postinst"
check_executable "${DEB_TREE}/DEBIAN/prerm"
check_executable "${DEB_TREE}/DEBIAN/postrm"
check_executable "${PACKAGING_DIR}/build-deb.sh"

if grep -q 'chmod 0640.*vnalpha.env' "${PACKAGING_DIR}/build-deb.sh" && \
   grep -q 'chown root:openstock /etc/vnalpha/vnalpha.env' "${DEB_TREE}/DEBIAN/postinst"; then
  ok "vnalpha.env is packaged for root/openstock credential access"
else
  fail "vnalpha.env credential permissions are not root/openstock scoped"
fi

# ---------------------------------------------------------------------------
# Test group: script syntax
# ---------------------------------------------------------------------------

echo ""
echo "=== Script syntax ==="

check_syntax_bash "${DEB_TREE}/usr/bin/vnalpha"
check_syntax_bash "${DEB_TREE}/usr/bin/vnalpha-poc"
check_syntax_bash "${PACKAGING_DIR}/build-deb.sh"
check_syntax_sh "${DEB_TREE}/DEBIAN/postinst"
check_syntax_sh "${DEB_TREE}/DEBIAN/prerm"
check_syntax_sh "${DEB_TREE}/DEBIAN/postrm"

# ---------------------------------------------------------------------------
# Test group: control file fields
# ---------------------------------------------------------------------------

echo ""
echo "=== DEBIAN/control fields ==="

CONTROL="${DEB_TREE}/DEBIAN/control"

for field in Package Version Architecture Depends Description; do
  if grep -q "^${field}:" "${CONTROL}"; then
    ok "control: ${field} present"
  else
    fail "control: ${field} missing"
  fi
done

# ---------------------------------------------------------------------------
# Test group: conffiles
# ---------------------------------------------------------------------------

echo ""
echo "=== conffiles ==="

CONFFILES="${DEB_TREE}/DEBIAN/conffiles"
if grep -q "/etc/vnalpha/vnalpha.env" "${CONFFILES}"; then
  ok "conffiles: /etc/vnalpha/vnalpha.env listed"
else
  fail "conffiles: /etc/vnalpha/vnalpha.env NOT listed"
fi

# Warehouse must NOT be in conffiles (it is not managed by the package)
# Ignore comment lines (starting with #) when checking
if grep -v "^#" "${CONFFILES}" | grep -q "warehouse"; then
  fail "conffiles: warehouse path found — it must NOT be managed by the package"
else
  ok "conffiles: warehouse path not listed (correct)"
fi

# ---------------------------------------------------------------------------
# Test group: safety boundary — forbidden endpoint references
# ---------------------------------------------------------------------------

echo ""
echo "=== Safety boundary ==="

FORBIDDEN_PATTERNS=("v1/order" "v1/account" "v1/portfolio" "v1/trading" "execute_order")

for launcher in vnalpha vnalpha-poc; do
  LAUNCHER_PATH="${DEB_TREE}/usr/bin/${launcher}"
  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if grep -v "^#" "${LAUNCHER_PATH}" 2>/dev/null | grep -q "${pattern}"; then
      fail "Safety: '${pattern}' found in ${launcher} launcher"
    else
      ok "Safety: '${pattern}' absent from ${launcher} launcher"
    fi
  done
done

# ---------------------------------------------------------------------------
# Test group: launcher correctness
# ---------------------------------------------------------------------------

echo ""
echo "=== Launcher behaviour ==="

VNALPHA_LAUNCHER="${DEB_TREE}/usr/bin/vnalpha"
VNALPHA_POC_LAUNCHER="${DEB_TREE}/usr/bin/vnalpha-poc"

# vnalpha launcher must source the env file
if grep -q "vnalpha.env" "${VNALPHA_LAUNCHER}"; then
  ok "vnalpha launcher: sources vnalpha.env"
else
  fail "vnalpha launcher: does not reference vnalpha.env"
fi

# vnalpha launcher must exec the venv binary
if grep -v "^#" "${VNALPHA_LAUNCHER}" | grep -qE "^exec.*VNALPHA_BIN|VNALPHA_BIN=.*/opt/vnalpha/venv/bin/vnalpha"; then
  ok "vnalpha launcher: uses exec to venv binary"
else
  fail "vnalpha launcher: missing exec to /opt/vnalpha/venv/bin/vnalpha"
fi

# vnalpha-poc must launch tui
if grep -q "tui" "${VNALPHA_POC_LAUNCHER}"; then
  ok "vnalpha-poc launcher: invokes tui subcommand"
else
  fail "vnalpha-poc launcher: does not invoke tui subcommand"
fi

# vnalpha-poc must use VNALPHA_DEMO_DATE
if grep -q "VNALPHA_DEMO_DATE" "${VNALPHA_POC_LAUNCHER}"; then
  ok "vnalpha-poc launcher: uses VNALPHA_DEMO_DATE"
else
  fail "vnalpha-poc launcher: does not use VNALPHA_DEMO_DATE"
fi

# ---------------------------------------------------------------------------
# Test group: postinst warehouse safety
# ---------------------------------------------------------------------------

echo ""
echo "=== postinst warehouse safety ==="

POSTINST="${DEB_TREE}/DEBIAN/postinst"

# postinst must NOT rm -rf the warehouse
if grep -v "^#" "${POSTINST}" | grep -qE "rm.*warehouse"; then
  fail "postinst: contains rm command referencing warehouse (DANGER)"
else
  ok "postinst: no rm of warehouse"
fi

# postinst must create warehouse dir, not delete it
if grep -qE "install.*WAREHOUSE_DIR|mkdir.*WAREHOUSE_DIR|install.*warehouse|mkdir.*warehouse" "${POSTINST}"; then
  ok "postinst: creates warehouse directory"
else
  fail "postinst: does not create warehouse directory"
fi

# ---------------------------------------------------------------------------
# Test group: postrm warehouse safety
# ---------------------------------------------------------------------------

echo ""
echo "=== postrm warehouse safety ==="

POSTRM="${DEB_TREE}/DEBIAN/postrm"

if grep -v "^#" "${POSTRM}" | sed 's/#.*//' | grep -qE "rm.*warehouse"; then
  fail "postrm: contains rm command referencing warehouse (DANGER)"
else
  ok "postrm: no rm of warehouse"
fi

# ---------------------------------------------------------------------------
# Test group: optional shellcheck
# ---------------------------------------------------------------------------

echo ""
echo "=== shellcheck (optional) ==="

if command -v shellcheck >/dev/null 2>&1; then
  for script in \
    "${DEB_TREE}/usr/bin/vnalpha" \
    "${DEB_TREE}/usr/bin/vnalpha-poc" \
    "${PACKAGING_DIR}/build-deb.sh"; do
    if shellcheck "${script}" 2>/dev/null; then
      ok "shellcheck: ${script##*/}"
    else
      fail "shellcheck: ${script##*/} — run: shellcheck ${script}"
    fi
  done

  for script in \
    "${DEB_TREE}/DEBIAN/postinst" \
    "${DEB_TREE}/DEBIAN/prerm" \
    "${DEB_TREE}/DEBIAN/postrm"; do
    if shellcheck --shell=sh "${script}" 2>/dev/null; then
      ok "shellcheck: ${script##*/}"
    else
      fail "shellcheck: ${script##*/}"
    fi
  done
else
  echo "[SKIP] shellcheck not installed (apt install shellcheck)"
fi

# ---------------------------------------------------------------------------
# Test group: .deb file validation (only when DEB_FILE provided)
# ---------------------------------------------------------------------------

if [[ -n "${DEB_FILE}" ]]; then
  echo ""
  echo "=== .deb file validation: ${DEB_FILE} ==="

  if command -v dpkg-deb >/dev/null 2>&1; then
    if dpkg-deb --info "${DEB_FILE}" >/dev/null 2>&1; then
      ok "dpkg-deb --info succeeded"
    else
      fail "dpkg-deb --info failed"
    fi

    # Check required files are in the .deb
    for entry in "./usr/bin/vnalpha" "./usr/bin/vnalpha-poc" "./etc/vnalpha/vnalpha.env" "./opt/vnalpha/RELEASE"; do
      if dpkg -c "${DEB_FILE}" | grep -F "${entry}" >/dev/null; then
        ok ".deb contains: ${entry}"
      else
        fail ".deb missing: ${entry}"
      fi
    done

    # Warehouse must NOT be in the .deb
    if dpkg -c "${DEB_FILE}" | grep -F "warehouse" >/dev/null; then
      fail ".deb contains warehouse path (it must not be packaged)"
    else
      ok ".deb does not package warehouse (correct)"
    fi

    DEB_ROOT="$(mktemp -d /tmp/vnalpha-deb-test.XXXXXX)"
    dpkg-deb --extract "${DEB_FILE}" "${DEB_ROOT}"
    if [[ "$(stat -c '%a' "${DEB_ROOT}/etc/vnalpha/vnalpha.env")" == "640" ]]; then
      ok ".deb scopes vnalpha.env to mode 0640"
    else
      fail ".deb vnalpha.env is not mode 0640"
    fi
    if grep -Eq '^commit=[0-9a-f]{40}$' "${DEB_ROOT}/opt/vnalpha/RELEASE" && \
       grep -Eq '^tree_state=(clean|dirty)$' "${DEB_ROOT}/opt/vnalpha/RELEASE"; then
      ok ".deb embeds release commit and tree state"
    else
      fail ".deb release metadata is missing or malformed"
    fi
    VNALPHA_WHEEL="$(find "${DEB_ROOT}/opt/vnalpha/wheels" -maxdepth 1 -name 'vnalpha-*.whl' -print -quit)"
    if [[ -n "${VNALPHA_WHEEL}" ]]; then
      ok ".deb bundles the vnalpha application wheel"
      if find "${DEB_ROOT}/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*.whl' -print -quit | grep -q .; then
        ok ".deb bundles runtime dependency wheels"
      else
        fail ".deb is missing runtime dependency wheels"
      fi
      if find "${DEB_ROOT}/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp310-*.whl' -print -quit | grep -q . && \
         find "${DEB_ROOT}/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp311-*.whl' -print -quit | grep -q . && \
         find "${DEB_ROOT}/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp312-*.whl' -print -quit | grep -q .; then
        ok ".deb dependency wheels cover supported CPython 3.10-3.12 hosts"
      else
        fail ".deb dependency wheel ABI set does not cover CPython 3.10-3.12"
      fi
      if unzip -Z1 "${VNALPHA_WHEEL}" | grep -F "vnalpha/evals/runtime_cases/invalid_explicit_date.json" >/dev/null; then
        ok ".deb application wheel bundles runtime eval resources"
      else
        fail ".deb application wheel is missing runtime eval resources"
      fi
      if python3 -c 'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 13)))'; then
        DEB_EVAL_ROOT="$(mktemp -d /tmp/vnalpha-deb-eval.XXXXXX)"
        DEB_LOG_ROOT="$(mktemp -d /tmp/vnalpha-deb-logs.XXXXXX)"
        python3 -m venv "${DEB_EVAL_ROOT}/venv"
        if "${DEB_EVAL_ROOT}/venv/bin/pip" install \
        --quiet \
        --no-index \
        --find-links "${DEB_ROOT}/opt/vnalpha/wheels" \
        vnalpha; then
          if VNALPHA_LOG_ROOT="${DEB_LOG_ROOT}" VNALPHA_LOG_PATH="${DEB_LOG_ROOT}/vnalpha.log" "${DEB_EVAL_ROOT}/venv/bin/python" -c 'from vnalpha.cli import app; app()' eval research-answers --ci >/dev/null; then
            ok ".deb application wheel runs fixture-contract eval"
          else
            fail ".deb application wheel fixture-contract eval failed"
          fi
          if VNALPHA_LOG_ROOT="${DEB_LOG_ROOT}" VNALPHA_LOG_PATH="${DEB_LOG_ROOT}/vnalpha.log" "${DEB_EVAL_ROOT}/venv/bin/python" -c 'from vnalpha.cli import app; app()' eval research-runtime --ci >/dev/null; then
            ok ".deb application wheel runs runtime-replay eval"
          else
            fail ".deb application wheel runtime-replay eval failed"
          fi
        else
          fail ".deb application wheel could not be installed into an isolated target"
        fi
        rm -rf "${DEB_EVAL_ROOT}" "${DEB_LOG_ROOT}"
      else
        echo "[SKIP] packaged runtime eval requires CPython 3.10-3.12"
      fi
    else
      fail ".deb is missing the vnalpha application wheel"
    fi
    rm -rf "${DEB_ROOT}"
  else
    echo "[SKIP] dpkg-deb not available"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "=== Summary ==="
echo "Passed: ${PASS}  Failed: ${FAIL}"
echo ""

if [[ "${FAIL}" -gt 0 ]]; then
  echo "RESULT: FAIL — ${FAIL} check(s) failed"
  exit 1
else
  echo "RESULT: PASS — all ${PASS} checks passed"
  exit 0
fi
