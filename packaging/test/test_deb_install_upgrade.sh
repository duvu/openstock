#!/usr/bin/env bash
# Exact Debian 12 fresh-install, upgrade and incomplete-wheel rollback acceptance.
# Usage: packaging/test/test_deb_install_upgrade.sh path/to/vnalpha_VERSION_amd64.deb

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
DEB_FILE=${1:-}
INNER_SCRIPT="$REPO_ROOT/packaging/test/deb_install_upgrade_inner.sh"

if [[ -z "$DEB_FILE" || ! -f "$DEB_FILE" ]]; then
  echo "Usage: $0 path/to/vnalpha_VERSION_amd64.deb" >&2
  exit 2
fi
if [[ ! -f "$INNER_SCRIPT" ]]; then
  echo "Missing inner acceptance script: $INNER_SCRIPT" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for exact Debian install acceptance." >&2
  exit 2
fi

DEB_ABS=$(cd "$(dirname "$DEB_FILE")" && pwd)/$(basename "$DEB_FILE")
INNER_ABS=$(cd "$(dirname "$INNER_SCRIPT")" && pwd)/$(basename "$INNER_SCRIPT")

echo "Running exact Debian 12 install/upgrade acceptance for: $DEB_ABS"
docker run --rm \
  --name openstock-vnalpha-deb-acceptance \
  --volume "$DEB_ABS:/tmp/vnalpha-good.deb:ro" \
  --volume "$INNER_ABS:/tmp/deb_install_upgrade_inner.sh:ro" \
  debian:12-slim \
  bash /tmp/deb_install_upgrade_inner.sh
