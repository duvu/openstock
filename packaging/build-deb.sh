#!/usr/bin/env bash
# build-deb.sh — Build the vnalpha Debian package
#
# Usage:
#   ./packaging/build-deb.sh [--version VERSION] [--output-dir DIR]
#
# Options:
#   --version VERSION   Override package version (default: read from vnalpha/pyproject.toml)
#   --output-dir DIR    Directory to write the .deb file (default: packaging/dist/)
#   --offline           Build an application-wheel-only structural fixture
#   --help              Show this help message
#
# What this script does:
#   1. Reads the version from vnalpha/pyproject.toml (or uses --version).
#   2. Copies the package tree from packaging/deb/ into a staging directory.
#   3. Pre-downloads Python wheels for vnalpha and its dependencies into
#      staging/opt/vnalpha/wheels/ for offline installation by postinst.
#   4. Sets correct file permissions on launchers and DEBIAN scripts.
#   5. Calls dpkg-deb --build to produce vnalpha_VERSION_amd64.deb.
#   6. Runs dpkg-deb --info and dpkg -c to verify the resulting .deb.
#
# Prerequisites:
#   - dpkg-deb (part of dpkg, available on Debian/Ubuntu)
#   - python3 and python3-pip (to download wheels)
#   - The vnalpha source tree at ./vnalpha/ relative to the repo root
#
# Normal output is standalone: postinst installs the bundled wheels offline so
# no network access is needed on the target host. The --offline structural
# fixture is intentionally not installable on a clean host.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${REPO_ROOT}/packaging"
DEB_TREE="${PACKAGING_DIR}/deb"
OUTPUT_DIR="${PACKAGING_DIR}/dist"
VNALPHA_SRC="${REPO_ROOT}/vnalpha"
SKIP_WHEELS=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --offline)
      SKIP_WHEELS=true
      shift
      ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "build-deb.sh: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------

if [[ -z "${VERSION}" ]]; then
  # Extract version from pyproject.toml: version = "X.Y.Z"
  VERSION="$(grep -E '^version\s*=' "${VNALPHA_SRC}/pyproject.toml" \
    | head -1 \
    | sed -E 's/^version\s*=\s*"([^"]+)".*/\1/')"
fi

if [[ -z "${VERSION}" ]]; then
  echo "build-deb.sh: ERROR — could not determine version from pyproject.toml" >&2
  exit 1
fi

echo "build-deb.sh: Building vnalpha version ${VERSION}"

# ---------------------------------------------------------------------------
# Staging area
# ---------------------------------------------------------------------------

STAGE_DIR="$(mktemp -d /tmp/vnalpha-deb-XXXXXX)"
trap 'rm -rf "${STAGE_DIR}"' EXIT

echo "build-deb.sh: Staging in ${STAGE_DIR}"

# Copy the package tree
cp -r "${DEB_TREE}/." "${STAGE_DIR}/"

# ---------------------------------------------------------------------------
# Update version in control file
# ---------------------------------------------------------------------------

sed -i "s/^Version:.*/Version: ${VERSION}/" "${STAGE_DIR}/DEBIAN/control"

# ---------------------------------------------------------------------------
# Calculate installed size (approximate, in KB)
# ---------------------------------------------------------------------------

# We set a placeholder in the control file; dpkg-deb will override with
# the actual size. Update it to something realistic to avoid a warning.
PAYLOAD_KB=1
if [[ "${SKIP_WHEELS}" == false ]]; then
  PAYLOAD_KB=60000  # ~60 MB estimate for venv with all deps
fi
sed -i "s/^Installed-Size:.*/Installed-Size: ${PAYLOAD_KB}/" \
  "${STAGE_DIR}/DEBIAN/control"

# ---------------------------------------------------------------------------
# Pre-download wheels (bundled offline install)
# ---------------------------------------------------------------------------

WHEELS_DIR="${STAGE_DIR}/opt/vnalpha/wheels"
mkdir -p "${WHEELS_DIR}"

# Build the local project wheel independently because pip download of a local
# project resolves dependencies but does not place the project wheel in the destination.
python3 -m pip wheel \
  --quiet \
  --no-deps \
  --no-build-isolation \
  --wheel-dir "${WHEELS_DIR}" \
  "${VNALPHA_SRC}"

if [[ "${SKIP_WHEELS}" == false ]]; then
  echo "build-deb.sh: Downloading wheels for offline install ..."
  # Download the vnalpha package and all its runtime deps as wheels
  python3 -m pip download \
    --quiet \
    --dest "${WHEELS_DIR}" \
    --find-links "${WHEELS_DIR}" \
    "${VNALPHA_SRC}"

  WHEEL_COUNT="$(find "${WHEELS_DIR}" -name "*.whl" | wc -l)"
  echo "build-deb.sh: Downloaded ${WHEEL_COUNT} wheels."
else
  echo "build-deb.sh: --offline: skipping wheel download."
fi

# ---------------------------------------------------------------------------
# Set file permissions
# ---------------------------------------------------------------------------

# DEBIAN scripts must be executable
chmod 0755 "${STAGE_DIR}/DEBIAN/postinst"
chmod 0755 "${STAGE_DIR}/DEBIAN/prerm"
chmod 0755 "${STAGE_DIR}/DEBIAN/postrm"

# Launchers must be executable
chmod 0755 "${STAGE_DIR}/usr/bin/vnalpha"
chmod 0755 "${STAGE_DIR}/usr/bin/vnalpha-poc"

# Config file: readable by all, not executable
chmod 0644 "${STAGE_DIR}/etc/vnalpha/vnalpha.env"

# ---------------------------------------------------------------------------
# Build .deb
# ---------------------------------------------------------------------------

mkdir -p "${OUTPUT_DIR}"
DEB_FILE="${OUTPUT_DIR}/vnalpha_${VERSION}_amd64.deb"

echo "build-deb.sh: Running dpkg-deb --build ..."
dpkg-deb --root-owner-group --build "${STAGE_DIR}" "${DEB_FILE}"

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

echo ""
echo "build-deb.sh: === Package info ==="
dpkg-deb --info "${DEB_FILE}"

echo ""
echo "build-deb.sh: === Package contents ==="
dpkg -c "${DEB_FILE}"

echo ""
echo "build-deb.sh: SUCCESS — ${DEB_FILE}"
echo ""
echo "Install with:"
echo "  sudo apt install -y '${DEB_FILE}'"
echo "  # or: sudo dpkg -i '${DEB_FILE}' && sudo apt -f install"
echo ""
echo "Verify:"
echo "  dpkg -s vnalpha"
echo "  vnalpha --help"
echo "  vnalpha-poc --help"
