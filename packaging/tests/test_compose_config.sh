#!/usr/bin/env bash
# test_compose_config.sh — validates docker compose config and CI-safe verify mode
# Covers tasks: 9.3 (CI verify exits 0), 9.5 (compose config), 9.7 (vnalpha tui --help)
# Usage: bash packaging/tests/test_compose_config.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo /home/beou/IdeaProjects/openstock)"

PASS=0
FAIL=0

# --- Test 9.5: docker compose config (base services) ---
if command -v docker &>/dev/null; then
  if docker compose config --quiet 2>/dev/null; then
    echo "[OK] docker compose config (base services)"
    ((PASS++)) || true
  else
    echo "[FAIL] docker compose config returned non-zero"
    ((FAIL++)) || true
  fi

  if docker compose --profile job config --quiet 2>/dev/null; then
    echo "[OK] docker compose --profile job config (vnalpha-worker)"
    ((PASS++)) || true
  else
    echo "[FAIL] docker compose --profile job config returned non-zero"
    ((FAIL++)) || true
  fi
else
  echo "[SKIP] docker not available — skipping compose config checks"
fi

# --- Test 9.3: CI-safe verify mode exits 0 ---
if bash packaging/scripts/openstock-verify --ci; then
  echo "[OK] openstock-verify --ci exits 0"
  ((PASS++)) || true
else
  echo "[FAIL] openstock-verify --ci returned non-zero"
  ((FAIL++)) || true
fi

# --- Test 9.7: vnalpha tui --help (if vnalpha installed) ---
if command -v vnalpha &>/dev/null; then
  if vnalpha tui --help &>/dev/null 2>&1; then
    echo "[OK] vnalpha tui --help"
    ((PASS++)) || true
  else
    echo "[FAIL] vnalpha tui --help returned non-zero"
    ((FAIL++)) || true
  fi
else
  echo "[SKIP] vnalpha not installed (Debian package not deployed)"
fi

# --- summary ---
echo ""
echo "Results: $PASS OK, $FAIL FAIL"
[[ $FAIL -eq 0 ]]
