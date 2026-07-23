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
require_grep 'OLD_VENV_STAGED=true' "$POSTINST" "postinst records rollback state before activation"
require_grep 'mv.*NEW_VENV.*VNALPHA_VENV' "$POSTINST" "postinst swaps the venv only after validation"
require_grep 'install.*0770.*WAREHOUSE_DIR|ensure_state_dir.*WAREHOUSE_DIR.*0770' "$POSTINST" "warehouse directory is root:openstock and group-writable"
require_grep 'ensure_state_dir.*KNOWLEDGE_DIR.*0770' "$POSTINST" "knowledge directory is root:openstock and group-writable"
require_grep 'ensure_state_dir.*QUEUE_DIR.*0770' "$POSTINST" "queue directory is root:openstock and group-writable"
require_grep 'ensure_state_dir.*LOG_DIR.*0770' "$POSTINST" "log directory is root:openstock and group-writable"
reject_grep 'systemctl[[:space:]]+enable|systemctl[[:space:]]+start.*openstock-daily-pipeline' "$POSTINST" "postinst does not enable or start the daily timer"

require_grep '^Group=openstock$' "$SERVICE" "daily service uses the openstock primary group"
require_grep '^UMask=0007$' "$SERVICE" "daily service creates group-readable/writable state"
require_grep 'flock -n -E 75' "$SERVICE" "daily service preserves the one-writer lock contract"
require_grep 'openstock-provisioner.service' "$BUILD_SCRIPT" "builder bundles the provisioner service"
require_grep 'flock -n /run/openstock-provisioner.lock' "$REPO_ROOT/packaging/systemd/openstock-provisioner.service" "provisioner retains the queue recovery lock"

for helper in \
  openstock-verify \
  openstock-mvp1-start \
  openstock-backup-warehouse \
  openstock-restore-warehouse
 do
  require_grep "$helper" "$BUILD_SCRIPT" "builder bundles $helper"
done
require_grep 'usr/share/doc/vnalpha/OPERATOR.md' "$BUILD_SCRIPT" "builder bundles the operator guide"

require_grep '^VNALPHA_LLM_API_KEY=$' "$ENV_FILE" "LLM credentials remain empty by default"

if [[ -n "$DEB_FILE" ]]; then
  printf '\n=== Built package payload ===\n'
  if [[ ! -f "$DEB_FILE" ]]; then
    fail "Debian package exists: $DEB_FILE"
  elif ! command -v dpkg-deb >/dev/null 2>&1; then
    printf '[SKIP] dpkg-deb unavailable; payload inspection skipped\n'
  else
    if dpkg-deb --info "$DEB_FILE" >/dev/null 2>&1; then
      ok "dpkg-deb --info succeeds"
    else
      fail "dpkg-deb --info succeeds"
    fi

    DEB_CONTENTS="$(dpkg -c "$DEB_FILE")"
    for entry in \
      ./usr/bin/vnalpha \
      ./usr/bin/vnalpha-poc \
      ./usr/bin/openstock-verify \
      ./usr/bin/openstock-mvp1-start \
      ./usr/bin/openstock-backup-warehouse \
      ./usr/bin/openstock-restore-warehouse \
      ./etc/vnalpha/vnalpha.env \
      ./usr/lib/systemd/system/openstock-daily-pipeline.service \
      ./usr/lib/systemd/system/openstock-daily-pipeline.timer \
      ./usr/lib/systemd/system/openstock-provisioner.service \
      ./usr/share/doc/vnalpha/OPERATOR.md \
      ./opt/vnalpha/RELEASE
    do
      if grep -F "$entry" <<<"$DEB_CONTENTS" >/dev/null; then
        ok ".deb contains $entry"
      else
        fail ".deb contains $entry"
      fi
    done

    if grep -F './var/lib/openstock/warehouse' <<<"$DEB_CONTENTS" >/dev/null; then
      fail ".deb does not package live warehouse state"
    else
      ok ".deb does not package live warehouse state"
    fi

    DEB_ROOT="$(mktemp -d /tmp/vnalpha-install-contract.XXXXXX)"
    trap 'rm -rf "${DEB_ROOT:-}" "${RUNTIME_ROOT:-}" "${RUNTIME_LOG_ROOT:-}"' EXIT
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

    if [[ "$(stat -c '%a' "$DEB_ROOT/etc/vnalpha/vnalpha.env")" == "640" ]]; then
      ok ".deb scopes vnalpha.env to mode 0640"
    else
      fail ".deb scopes vnalpha.env to mode 0640"
    fi
    if grep -Eq '^version=[0-9A-Za-z.+~-]+$' "$DEB_ROOT/opt/vnalpha/RELEASE" && \
       grep -Eq '^commit=[0-9a-f]{40}$' "$DEB_ROOT/opt/vnalpha/RELEASE" && \
       grep -Eq '^tree_state=(clean|dirty)$' "$DEB_ROOT/opt/vnalpha/RELEASE"; then
      ok ".deb embeds valid release identity"
    else
      fail ".deb embeds valid release identity"
    fi

    VNALPHA_WHEEL="$(find "$DEB_ROOT/opt/vnalpha/wheels" -maxdepth 1 -name 'vnalpha-*.whl' -print -quit)"
    if [[ -n "$VNALPHA_WHEEL" ]]; then
      ok ".deb bundles the vnalpha application wheel"
    else
      fail ".deb bundles the vnalpha application wheel"
    fi
    if find "$DEB_ROOT/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*.whl' -print -quit | grep -q .; then
      ok ".deb bundles runtime dependency wheels"
    else
      fail ".deb bundles runtime dependency wheels"
    fi
    if find "$DEB_ROOT/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp310-*.whl' -print -quit | grep -q . && \
       find "$DEB_ROOT/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp311-*.whl' -print -quit | grep -q . && \
       find "$DEB_ROOT/opt/vnalpha/wheels" -maxdepth 1 -name 'duckdb-*-cp312-*.whl' -print -quit | grep -q .; then
      ok ".deb dependency wheels cover CPython 3.10-3.12"
    else
      fail ".deb dependency wheels cover CPython 3.10-3.12"
    fi

    if [[ -n "$VNALPHA_WHEEL" ]] && \
       python3 -c 'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 13)))'; then
      RUNTIME_ROOT="$(mktemp -d /tmp/vnalpha-install-runtime.XXXXXX)"
      RUNTIME_LOG_ROOT="$(mktemp -d /tmp/vnalpha-install-logs.XXXXXX)"
      python3 -m venv "$RUNTIME_ROOT/venv"
      if "$RUNTIME_ROOT/venv/bin/pip" install \
        --quiet \
        --disable-pip-version-check \
        --no-index \
        --find-links "$DEB_ROOT/opt/vnalpha/wheels" \
        vnalpha; then
        ok ".deb wheelhouse installs without a package index"
        for command in \
          '--help' \
          'maintain enqueue --help' \
          'maintain status --help' \
          'tui --help'
        do
          if VNALPHA_LOG_ROOT="$RUNTIME_LOG_ROOT" \
             VNALPHA_LOG_PATH="$RUNTIME_LOG_ROOT/vnalpha.log" \
             "$RUNTIME_ROOT/venv/bin/vnalpha" $command >/dev/null 2>&1; then
            ok "installed CLI supports: vnalpha $command"
          else
            fail "installed CLI supports: vnalpha $command"
          fi
        done
      else
        fail ".deb wheelhouse installs without a package index"
      fi
      rm -rf "$RUNTIME_ROOT" "$RUNTIME_LOG_ROOT"
      RUNTIME_ROOT=""
      RUNTIME_LOG_ROOT=""
    else
      printf '[SKIP] runtime smoke requires a bundled wheel and CPython 3.10-3.12\n'
    fi

    rm -rf "$DEB_ROOT"
    DEB_ROOT=""
    trap - EXIT
  fi
fi

printf '\nPassed: %d  Failed: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
