#!/usr/bin/env bash
# Validate the offline, transactional and shared-state Debian install contract.
# Usage: test_install_contract.sh [path/to/vnalpha.deb]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTINST="${REPO_ROOT}/packaging/deb/DEBIAN/postinst"
SERVICE="${REPO_ROOT}/packaging/deb/usr/lib/systemd/system/openstock-daily-pipeline.service"
BUILD_SCRIPT="${REPO_ROOT}/packaging/build-deb.sh"
ENV_FILE="${REPO_ROOT}/packaging/deb/etc/vnalpha/vnalpha.env"
DEB_FILE="${1:-}"
PASS=0
FAIL=0

ok() { printf '[OK]   %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '[FAIL] %s\n' "$1" >&2; FAIL=$((FAIL + 1)); }

require_grep() {
  pattern="$1"
  file="$2"
  description="$3"
  if grep -Eq -- "$pattern" "$file"; then
    ok "$description"
  else
    fail "$description"
  fi
}

reject_grep() {
  pattern="$1"
  file="$2"
  description="$3"
  if grep -Eq -- "$pattern" "$file"; then
    fail "$description"
  else
    ok "$description"
  fi
}

printf '\n=== Debian install contract ===\n'

if sh -n "$POSTINST"; then
  ok "postinst has valid POSIX shell syntax"
else
  fail "postinst has valid POSIX shell syntax"
fi
if bash -n "$BUILD_SCRIPT"; then
  ok "build-deb.sh has valid Bash syntax"
else
  fail "build-deb.sh has valid Bash syntax"
fi

require_grep '--no-index' "$POSTINST" "postinst installs from bundled wheels only"
require_grep 'vnalpha==\$\{PACKAGE_VERSION\}' "$POSTINST" "postinst installs the exact packaged version"
reject_grep 'falling back to PyPI|https?://|--index-url|--extra-index-url' "$POSTINST" "postinst has no target-host network fallback"
require_grep 'venv\.new\.\$\$' "$POSTINST" "postinst builds a temporary replacement venv"
require_grep 'bin/vnalpha.*--help' "$POSTINST" "postinst smoke-tests the replacement CLI"
require_grep 'mv.*NEW_VENV.*VNALPHA_VENV' "$POSTINST" "postinst swaps the venv only after validation"
require_grep 'root -g openstock.*WAREHOUSE_DIR.*0770|ensure_state_dir.*WAREHOUSE_DIR.*0770' "$POSTINST" "warehouse directory is root:openstock and group-writable"
require_grep 'ensure_state_dir.*KNOWLEDGE_DIR.*0770' "$POSTINST" "knowledge directory is root:openstock and group-writable"
require_grep 'ensure_state_dir.*LOG_DIR.*0770' "$POSTINST" "log directory is root:openstock and group-writable"
reject_grep 'systemctl[[:space:]]+enable|systemctl[[:space:]]+start.*openstock-daily-pipeline' "$POSTINST" "postinst does not enable or start the daily timer"

require_grep '^Group=openstock$' "$SERVICE" "daily service uses the openstock primary group"
require_grep '^UMask=0007$' "$SERVICE" "daily service creates group-readable/writable state"
require_grep 'flock -n -E 75' "$SERVICE" "daily service preserves the one-writer lock contract"

for helper in \
  openstock-verify \
  openstock-mvp1-start \
  openstock-backup-warehouse \
  openstock-restore-warehouse
 do
  require_grep "$helper" "$BUILD_SCRIPT" "builder bundles $helper"
done
require_grep 'usr/share/doc/vnalpha/OPERATOR.md' "$BUILD_SCRIPT" "builder bundles the operator guide"

require_grep '^VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=false$' "$ENV_FILE" "FiinQuantX persistence remains disabled by default"
require_grep '^VNALPHA_LLM_API_KEY=$' "$ENV_FILE" "LLM credentials remain empty by default"

if [[ -n "$DEB_FILE" ]]; then
  printf '\n=== Built package payload ===\n'
  if [[ ! -f "$DEB_FILE" ]]; then
    fail "Debian package exists: $DEB_FILE"
  elif ! command -v dpkg-deb >/dev/null 2>&1; then
    printf '[SKIP] dpkg-deb unavailable; payload inspection skipped\n'
  else
    DEB_ROOT="$(mktemp -d /tmp/vnalpha-install-contract.XXXXXX)"
    trap 'rm -rf "${DEB_ROOT:-}"' EXIT
    dpkg-deb --extract "$DEB_FILE" "$DEB_ROOT"
    for entry in \
      usr/bin/openstock-verify \
      usr/bin/openstock-mvp1-start \
      usr/bin/openstock-backup-warehouse \
      usr/bin/openstock-restore-warehouse
    do
      if [[ -x "$DEB_ROOT/$entry" ]]; then
        ok ".deb contains executable /$entry"
      else
        fail ".deb contains executable /$entry"
      fi
    done
    if [[ -f "$DEB_ROOT/usr/share/doc/vnalpha/OPERATOR.md" ]]; then
      ok ".deb contains the operator guide"
    else
      fail ".deb contains the operator guide"
    fi
    rm -rf "$DEB_ROOT"
    trap - EXIT
  fi
fi

printf '\nPassed: %d  Failed: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
