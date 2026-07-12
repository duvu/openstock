#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$ROOT/packaging/scripts/openstock-repo-hygiene"
TMP_ROOT="$(mktemp -d /tmp/openstock-repo-hygiene.XXXXXX)"
trap 'rm -rf "$TMP_ROOT"' EXIT

git_init() {
  git -C "$1" init -q
  git -C "$1" config user.email test@example.invalid
  git -C "$1" config user.name "OpenStock Test"
  printf 'ok\n' > "$1/README.md"
  git -C "$1" add README.md
  git -C "$1" commit -qm baseline
}

git_init "$TMP_ROOT"

if ! bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null; then
  echo "clean fixture should pass hygiene verification" >&2
  exit 1
fi

mkdir -p "$TMP_ROOT/.vnalpha/workspaces"
printf 'runtime\n' > "$TMP_ROOT/.vnalpha/workspaces/index.json"
git -C "$TMP_ROOT" add .vnalpha/workspaces/index.json
git -C "$TMP_ROOT" commit -qm denied-runtime

if bash "$SCRIPT" --root "$TMP_ROOT" >"$TMP_ROOT/denied.out" 2>&1; then
  echo "tracked runtime path should fail hygiene verification" >&2
  exit 1
fi

if ! grep -q '.vnalpha/workspaces/index.json' "$TMP_ROOT/denied.out"; then
  echo "hygiene failure should name the denied tracked path" >&2
  cat "$TMP_ROOT/denied.out" >&2
  exit 1
fi

GITLINK_ROOT="$TMP_ROOT/gitlink"
mkdir -p "$GITLINK_ROOT"
git_init "$GITLINK_ROOT"
mkdir "$GITLINK_ROOT/submodule"
git -C "$GITLINK_ROOT/submodule" init -q
git -C "$GITLINK_ROOT/submodule" config user.email test@example.invalid
git -C "$GITLINK_ROOT/submodule" config user.name "OpenStock Test"
printf 'module\n' > "$GITLINK_ROOT/submodule/module.txt"
git -C "$GITLINK_ROOT/submodule" add module.txt
git -C "$GITLINK_ROOT/submodule" commit -qm module
git -C "$GITLINK_ROOT" add submodule 2>/dev/null
git -C "$GITLINK_ROOT" commit -qm gitlink

if bash "$SCRIPT" --root "$GITLINK_ROOT" >"$GITLINK_ROOT/gitlink.out" 2>&1; then
  echo "unapproved gitlink should fail hygiene verification" >&2
  exit 1
fi

if ! grep -q 'submodule' "$GITLINK_ROOT/gitlink.out"; then
  echo "gitlink failure should name the unapproved path" >&2
  cat "$GITLINK_ROOT/gitlink.out" >&2
  exit 1
fi

mkdir -p "$GITLINK_ROOT/packaging/config"
printf 'submodule\n' > "$GITLINK_ROOT/packaging/config/approved-submodules.txt"
if ! bash "$SCRIPT" --root "$GITLINK_ROOT" >/dev/null; then
  echo "an explicitly allowlisted gitlink should pass hygiene verification" >&2
  exit 1
fi

echo "repo hygiene contract tests passed"
