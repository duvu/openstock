#!/usr/bin/env bash
# test_shellcheck.sh — runs shellcheck on all packaging shell scripts
# Usage: bash packaging/tests/test_shellcheck.sh
# Run from repo root: bash packaging/tests/test_shellcheck.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo /home/beou/IdeaProjects/openstock)"

PASS=0
FAIL=0

if ! command -v shellcheck &>/dev/null; then
  echo "[SKIP] shellcheck not installed — install with: apt-get install shellcheck"
  exit 0
fi

# Find and check all .sh files and scripts without extension
for f in packaging/scripts/* packaging/build-deb.sh packaging/test/*.sh packaging/tests/*.sh; do
  [[ -f "$f" ]] || continue
  if shellcheck "$f"; then
    echo "[OK] $f"
    ((PASS++)) || true
  else
    echo "[FAIL] $f"
    ((FAIL++)) || true
  fi
done

echo "shellcheck: $PASS OK, $FAIL FAIL"
[[ $FAIL -eq 0 ]]
