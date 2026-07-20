#!/usr/bin/env bash
# Runs inside a disposable Debian 12 container as root.

set -euo pipefail

GOOD_DEB=/tmp/vnalpha-good.deb
WORK=/tmp/vnalpha-acceptance
WAREHOUSE=/var/lib/openstock/warehouse
KNOWLEDGE=/var/lib/openstock/knowledge
LOG_ROOT=/var/log/openstock

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

pass() {
  printf '[PASS] %s\n' "$*"
}

repack() {
  local source_deb=$1
  local output_deb=$2
  local version_suffix=$3
  local remove_pattern=${4:-}
  local stage
  stage=$(mktemp -d /tmp/vnalpha-repack.XXXXXX)
  dpkg-deb -R "$source_deb" "$stage"
  local current_version
  current_version=$(sed -n 's/^Version: //p' "$stage/DEBIAN/control")
  sed -i "s/^Version:.*/Version: ${current_version}+${version_suffix}/" \
    "$stage/DEBIAN/control"
  if [[ -n "$remove_pattern" ]]; then
    find "$stage/opt/vnalpha/wheels" -maxdepth 1 -type f \
      -name "$remove_pattern" -delete
  fi
  dpkg-deb --root-owner-group --build "$stage" "$output_deb" >/dev/null
  rm -rf "$stage"
}

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  ca-certificates python3 python3-venv util-linux passwd >/dev/null

# Fresh install: apt resolves only OS dependencies; postinst must use bundled
# Python wheels with --no-index.
apt-get install -y -qq "$GOOD_DEB" >/tmp/fresh-install.log
/opt/vnalpha/venv/bin/vnalpha --help >/dev/null
pass 'fresh install created a working offline vnalpha venv'

getent group openstock >/dev/null || fail 'openstock group missing'
for path in "$WAREHOUSE" "$KNOWLEDGE" "$LOG_ROOT"; do
  [[ $(stat -c '%U:%G' "$path") == root:openstock ]] || \
    fail "$path ownership is not root:openstock"
  mode=$(stat -c '%a' "$path")
  [[ "$mode" == 770 ]] || fail "$path mode is $mode, expected 770"
done
pass 'shared state paths use the root:openstock 0770 contract'

useradd --create-home --groups openstock operator
su -s /bin/sh operator -c \
  "touch '$WAREHOUSE/operator-write' '$KNOWLEDGE/operator-write' '$LOG_ROOT/operator-write'"
pass 'an openstock group member can write warehouse, knowledge and log state'

[[ ! -e /etc/systemd/system/timers.target.wants/openstock-daily-pipeline.timer ]] || \
  fail 'daily timer was enabled automatically'
pass 'daily timer remains disabled after installation'

printf 'preserve-me\n' >"$WAREHOUSE/acceptance-state-marker"
old_cli_hash=$(sha256sum /opt/vnalpha/venv/bin/vnalpha | awk '{print $1}')

# A normal package upgrade must replace the venv while preserving research state.
repack "$GOOD_DEB" /tmp/vnalpha-upgrade.deb acceptance1
apt-get install -y -qq /tmp/vnalpha-upgrade.deb >/tmp/normal-upgrade.log
/opt/vnalpha/venv/bin/vnalpha --help >/dev/null
grep -qx 'preserve-me' "$WAREHOUSE/acceptance-state-marker" || \
  fail 'normal upgrade changed warehouse state'
pass 'normal upgrade leaves a working CLI and preserves research state'

working_cli_hash=$(sha256sum /opt/vnalpha/venv/bin/vnalpha | awk '{print $1}')
[[ -n "$working_cli_hash" ]] || fail 'could not hash working upgraded CLI'

# A higher-version package with an intentionally incomplete wheel bundle must
# fail before replacing the active venv. Removing typer guarantees the new empty
# venv cannot resolve a required dependency from the offline wheelhouse.
repack /tmp/vnalpha-upgrade.deb /tmp/vnalpha-broken.deb acceptance2 'typer-*.whl'
set +e
dpkg -i /tmp/vnalpha-broken.deb >/tmp/broken-upgrade.log 2>&1
broken_rc=$?
set -e
[[ $broken_rc -ne 0 ]] || fail 'incomplete wheel bundle unexpectedly installed'

/opt/vnalpha/venv/bin/vnalpha --help >/dev/null || \
  fail 'previous venv is unusable after failed upgrade'
after_failure_hash=$(sha256sum /opt/vnalpha/venv/bin/vnalpha | awk '{print $1}')
[[ "$after_failure_hash" == "$working_cli_hash" ]] || \
  fail 'failed upgrade changed the active vnalpha CLI'
grep -qx 'preserve-me' "$WAREHOUSE/acceptance-state-marker" || \
  fail 'failed upgrade changed warehouse state'
pass 'incomplete wheel upgrade fails closed and preserves the prior venv/state'

# Confirm the original fresh venv was a real installed binary as a sanity check.
[[ -n "$old_cli_hash" ]]
printf '\nAll Debian fresh-install and upgrade acceptance checks passed.\n'
