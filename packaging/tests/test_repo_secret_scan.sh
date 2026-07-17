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

printf 'API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/staged.env"
git -C "$TMP_ROOT" add staged.env
rm "$TMP_ROOT/staged.env"
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  echo "index-only secret should fail secret scan" >&2
  exit 1
fi
git -C "$TMP_ROOT" restore --staged staged.env

printf 'API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/staged.env"
git -C "$TMP_ROOT" add staged.env
printf 'safe worktree content\n' > "$TMP_ROOT/staged.env"
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  echo "safe worktree must not mask a staged secret" >&2
  exit 1
fi
git -C "$TMP_ROOT" restore --staged staged.env
rm "$TMP_ROOT/staged.env"

printf 'API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/untracked.env"
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  echo "untracked secret should fail secret scan" >&2
  exit 1
fi
rm "$TMP_ROOT/untracked.env"

mkdir -p "$TMP_ROOT/ya-router"
printf 'API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/ya-router/tracked.env"
git -C "$TMP_ROOT" add ya-router/tracked.env
git -C "$TMP_ROOT" commit -qm tracked-ya-router-secret
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  echo "tracked ya-router secret should fail secret scan" >&2
  exit 1
fi
git -C "$TMP_ROOT" rm -q ya-router/tracked.env
git -C "$TMP_ROOT" commit -qm remove-tracked-ya-router-secret

mkdir "$TMP_ROOT/unreadable"
chmod 000 "$TMP_ROOT/unreadable"
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  chmod 700 "$TMP_ROOT/unreadable"
  echo "unreadable untracked directory should fail secret scan" >&2
  exit 1
fi
chmod 700 "$TMP_ROOT/unreadable"
rmdir "$TMP_ROOT/unreadable"

printf 'API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/unreadable.env"
chmod 000 "$TMP_ROOT/unreadable.env"
if bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null 2>&1; then
  chmod 600 "$TMP_ROOT/unreadable.env"
  echo "unreadable untracked file should fail secret scan" >&2
  exit 1
fi
chmod 600 "$TMP_ROOT/unreadable.env"
rm "$TMP_ROOT/unreadable.env"

printf 'API_KEY=%s123456\n' 'live-secret-' >> "$TMP_ROOT/README.md"
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

if grep -q 'live-secret-' "$TMP_ROOT/scan.out"; then
  echo "secret scan must redact matching credential values" >&2
  cat "$TMP_ROOT/scan.out" >&2
  exit 1
fi

NO_RG_BIN="$TMP_ROOT/no-rg-bin"
mkdir -p "$NO_RG_BIN"
for command_name in bash git tr grep awk mktemp rm; do
  ln -s "$(command -v "$command_name")" "$NO_RG_BIN/$command_name"
done

if PATH="$NO_RG_BIN" bash "$SCRIPT" --root "$TMP_ROOT" >"$TMP_ROOT/no-rg.out" 2>&1; then
  echo "seeded secret should fail when ripgrep is unavailable" >&2
  exit 1
fi

if ! grep -q 'README.md' "$TMP_ROOT/no-rg.out"; then
  echo "portable secret scan should name the matching file" >&2
  cat "$TMP_ROOT/no-rg.out" >&2
  exit 1
fi


BROKEN_RG_BIN="$TMP_ROOT/broken-rg-bin"
mkdir -p "$BROKEN_RG_BIN"
for command_name in bash git tr grep awk mktemp rm; do
  ln -s "$(command -v "$command_name")" "$BROKEN_RG_BIN/$command_name"
done
printf '#!/usr/bin/env bash\nexit 2\n' > "$BROKEN_RG_BIN/rg"
chmod +x "$BROKEN_RG_BIN/rg"

if PATH="$BROKEN_RG_BIN" bash "$SCRIPT" --root "$TMP_ROOT" >"$TMP_ROOT/broken-rg.out" 2>&1; then
  echo "secret scan must fail closed when its scanner errors" >&2
  exit 1
fi

if ! grep -q '\[ERROR\].*scanner failed' "$TMP_ROOT/broken-rg.out"; then
  echo "secret scan should report an operational scanner error" >&2
  cat "$TMP_ROOT/broken-rg.out" >&2
  exit 1
fi

printf 'safe\n' > "$TMP_ROOT/README.md"
printf '\000API_KEY=%s123456\n' 'live-secret-' > "$TMP_ROOT/binary.dat"
git -C "$TMP_ROOT" add binary.dat
git -C "$TMP_ROOT" add README.md
git -C "$TMP_ROOT" commit -qm binary

if ! bash "$SCRIPT" --root "$TMP_ROOT" >/dev/null; then
  echo "binary tracked files should be skipped before content scanning" >&2
  exit 1
fi

echo "repo secret scan contract tests passed"
