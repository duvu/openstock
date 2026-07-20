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
#   3. Bundles supported operator helpers and the operator guide.
#   4. Pre-downloads Python wheels for vnalpha and its dependencies into
#      staging/opt/vnalpha/wheels/ for offline installation by postinst.
#   5. Sets correct file permissions on launchers and DEBIAN scripts.
#   6. Calls dpkg-deb --build to produce vnalpha_VERSION_amd64.deb.
#   7. Runs package structure checks on the resulting .deb.
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${REPO_ROOT}/packaging"
DEB_TREE="${PACKAGING_DIR}/deb"
OUTPUT_DIR="${PACKAGING_DIR}/dist"
VNALPHA_SRC="${REPO_ROOT}/vnalpha"
SKIP_WHEELS=false
OPERATOR_SCRIPTS=(
  openstock-verify
  openstock-mvp1-start
  openstock-backup-warehouse
  openstock-restore-warehouse
)

VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      [[ $# -ge 2 ]] || { echo "build-deb.sh: --version requires a value" >&2; exit 1; }
      VERSION="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { echo "build-deb.sh: --output-dir requires a value" >&2; exit 1; }
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

if [[ -z "${VERSION}" ]]; then
  VERSION="$(grep -E '^version\s*=' "${VNALPHA_SRC}/pyproject.toml" \
    | head -1 \
    | sed -E 's/^version\s*=\s*"([^"]+)".*/\1/')"
fi

if [[ -z "${VERSION}" ]]; then
  echo "build-deb.sh: ERROR — could not determine version from pyproject.toml" >&2
  exit 1
fi
if [[ ! "${VERSION}" =~ ^[0-9A-Za-z.+~-]+$ ]]; then
  echo "build-deb.sh: ERROR — invalid package version: ${VERSION}" >&2
  exit 1
fi

echo "build-deb.sh: Building vnalpha version ${VERSION}"

STAGE_DIR="$(mktemp -d /tmp/vnalpha-deb-XXXXXX)"
trap 'rm -rf "${STAGE_DIR}"' EXIT

echo "build-deb.sh: Staging in ${STAGE_DIR}"
cp -r "${DEB_TREE}/." "${STAGE_DIR}/"

mkdir -p "${STAGE_DIR}/usr/bin" "${STAGE_DIR}/usr/share/doc/vnalpha"
for helper in "${OPERATOR_SCRIPTS[@]}"; do
  helper_source="${PACKAGING_DIR}/scripts/${helper}"
  if [[ ! -f "${helper_source}" ]]; then
    echo "build-deb.sh: ERROR — missing operator helper: ${helper_source}" >&2
    exit 1
  fi
  bash -n "${helper_source}"
  install -m 0755 "${helper_source}" "${STAGE_DIR}/usr/bin/${helper}"
done
install -m 0644 "${PACKAGING_DIR}/docs/OPERATOR.md" \
  "${STAGE_DIR}/usr/share/doc/vnalpha/OPERATOR.md"

GIT_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || true)"
if [[ ! "${GIT_COMMIT}" =~ ^[0-9a-f]{40}$ ]]; then
  GIT_COMMIT="0000000000000000000000000000000000000000"
fi
TREE_STATE="clean"
UNTRACKED_IN_SCOPE="$(git -C "${REPO_ROOT}" ls-files --others --exclude-standard 2>/dev/null | grep -v '^ya-router/' || true)"
if ! git -C "${REPO_ROOT}" diff --quiet --ignore-submodules -- 2>/dev/null || \
   ! git -C "${REPO_ROOT}" diff --cached --quiet --ignore-submodules -- 2>/dev/null || \
   [[ -n "${UNTRACKED_IN_SCOPE}" ]]; then
  TREE_STATE="dirty"
fi
mkdir -p "${STAGE_DIR}/opt/vnalpha"
printf 'version=%s\ncommit=%s\ntree_state=%s\n' \
  "${VERSION}" "${GIT_COMMIT}" "${TREE_STATE}" \
  >"${STAGE_DIR}/opt/vnalpha/RELEASE"

sed -i "s/^Version:.*/Version: ${VERSION}/" "${STAGE_DIR}/DEBIAN/control"
PAYLOAD_KB=1
if [[ "${SKIP_WHEELS}" == false ]]; then
  PAYLOAD_KB=60000
fi
sed -i "s/^Installed-Size:.*/Installed-Size: ${PAYLOAD_KB}/" \
  "${STAGE_DIR}/DEBIAN/control"

WHEELS_DIR="${STAGE_DIR}/opt/vnalpha/wheels"
mkdir -p "${WHEELS_DIR}"
TARGET_PYTHON_VERSIONS=("310" "311" "312")
TARGET_WHEEL_PLATFORMS=(
  "manylinux_2_28_x86_64"
  "manylinux_2_27_x86_64"
  "manylinux_2_26_x86_64"
  "manylinux_2_24_x86_64"
  "manylinux_2_17_x86_64"
  "manylinux2014_x86_64"
)

python3 -m pip wheel \
  --quiet \
  --no-deps \
  --no-build-isolation \
  --wheel-dir "${WHEELS_DIR}" \
  "${VNALPHA_SRC}"

if [[ "${SKIP_WHEELS}" == false ]]; then
  echo "build-deb.sh: Downloading CPython 3.10-3.12 wheels ..."
  VNALPHA_WHEEL="$(find "${WHEELS_DIR}" -maxdepth 1 -name 'vnalpha-*.whl' -print -quit)"
  [[ -n "${VNALPHA_WHEEL}" ]] || {
    echo "build-deb.sh: ERROR — local vnalpha wheel was not created" >&2
    exit 1
  }
  TARGET_WHEELS_DIR="${STAGE_DIR}/target-wheels"
  mkdir -p "${TARGET_WHEELS_DIR}"
  PLATFORM_ARGS=()
  for platform in "${TARGET_WHEEL_PLATFORMS[@]}"; do
    PLATFORM_ARGS+=(--platform "${platform}")
  done
  for target_python in "${TARGET_PYTHON_VERSIONS[@]}"; do
    python3 -m pip download \
      --quiet \
      --only-binary=:all: \
      --dest "${TARGET_WHEELS_DIR}" \
      "${PLATFORM_ARGS[@]}" \
      --python-version "${target_python}" \
      --implementation cp \
      --abi "cp${target_python}" \
      "${VNALPHA_WHEEL}"
  done

  rm -rf "${WHEELS_DIR}"
  mv "${TARGET_WHEELS_DIR}" "${WHEELS_DIR}"

  WHEEL_COUNT="$(find "${WHEELS_DIR}" -name '*.whl' | wc -l)"
  echo "build-deb.sh: Downloaded ${WHEEL_COUNT} wheels."
else
  echo "build-deb.sh: --offline: skipping dependency wheel download."
fi

chmod 0755 "${STAGE_DIR}/DEBIAN/postinst"
chmod 0755 "${STAGE_DIR}/DEBIAN/prerm"
chmod 0755 "${STAGE_DIR}/DEBIAN/postrm"
chmod 0755 "${STAGE_DIR}/usr/bin/vnalpha"
chmod 0755 "${STAGE_DIR}/usr/bin/vnalpha-poc"
for helper in "${OPERATOR_SCRIPTS[@]}"; do
  chmod 0755 "${STAGE_DIR}/usr/bin/${helper}"
done
chmod 0640 "${STAGE_DIR}/etc/vnalpha/vnalpha.env"
chmod 0644 "${STAGE_DIR}/opt/vnalpha/RELEASE"
chmod 0644 "${STAGE_DIR}/usr/lib/systemd/system/openstock-daily-pipeline.service"
chmod 0644 "${STAGE_DIR}/usr/lib/systemd/system/openstock-daily-pipeline.timer"

mkdir -p "${OUTPUT_DIR}"
DEB_FILE="${OUTPUT_DIR}/vnalpha_${VERSION}_amd64.deb"

echo "build-deb.sh: Running dpkg-deb --build ..."
dpkg-deb --root-owner-group --build "${STAGE_DIR}" "${DEB_FILE}"

echo ""
echo "build-deb.sh: === Package info ==="
dpkg-deb --info "${DEB_FILE}"

echo ""
echo "build-deb.sh: === Package contents ==="
dpkg -c "${DEB_FILE}"

for entry in \
  ./usr/bin/vnalpha \
  ./usr/bin/openstock-verify \
  ./usr/bin/openstock-mvp1-start \
  ./usr/bin/openstock-backup-warehouse \
  ./usr/bin/openstock-restore-warehouse \
  ./usr/share/doc/vnalpha/OPERATOR.md \
  ./opt/vnalpha/RELEASE
do
  if ! dpkg -c "${DEB_FILE}" | awk '{print $NF}' | grep -Fx "${entry}" >/dev/null; then
    echo "build-deb.sh: ERROR — built package is missing ${entry}" >&2
    exit 1
  fi
done

echo ""
echo "build-deb.sh: SUCCESS — ${DEB_FILE}"
echo ""
echo "Install with:"
echo "  sudo apt install -y '${DEB_FILE}'"
echo "  # or: sudo dpkg -i '${DEB_FILE}' && sudo apt -f install"
echo ""
echo "After install:"
echo "  sudo usermod -aG openstock <operator>  # then start a new login session"
echo "  vnalpha init"
echo "  openstock-verify --mvp1"
echo ""
echo "The daily timer is installed but remains disabled until explicitly enabled:"
echo "  sudo systemctl enable --now openstock-daily-pipeline.timer"
