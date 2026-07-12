#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$ROOT/packaging/scripts/openstock-secret-scan"
TMP_ROOT="$(mktemp -d /tmp/openstock-secret-scan.XXXXXX)"
trap 'rm -rf "$TMP_ROOT"' EXIT

git -C "$TMP_ROOT" init -q
git -C "$TMP_ROOT" config user.email test@example.invalid
git -C "$TMP_ROOT" config user.name "OpenStock Test"
printf 'safe\n' > "$TMP_ROOT/README.md"
git -C "$TMP_ROOT" add README.md
git -C "$TMP_ROOT" commit -qm baseline

if ! bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null; then
  echo "safe fixture should pass secret scan" >&2
  exit 1
fi

printf 'API_KEY=live-secret-123456\n' >> "$TMP_ROOT/README.md"
git -C "$TMP_ROOT" add README.md
git -C "$TMP_ROOT" commit -qm secret

if bash "$SCRIPT" --root "$TMP_ROOT" >"$TMP_ROOT/scan.out" 2>&1; then
  echo "seeded secret should fail secret scan" >&2
  exit 1
fi

if ! grep -q 'README.md' "$TMP_ROOT/scan.out"; then
  echo "secret scan should name the matching file" >&2
  cat "$TMP_ROOT/scan.out" >&2
  exit 1
fi

echo "repo secret scan contract tests passed"
