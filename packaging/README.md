# vnalpha Debian Packaging

This directory contains the scaffolding to build `vnalpha.deb` — the host-native Debian package for running the vnalpha research CLI and interactive TUI directly from a host terminal without Docker.

## Directory layout

```
packaging/
├── build-deb.sh              ← Build script: produces vnalpha_VERSION_amd64.deb
├── README.md                 ← This file
├── deb/                      ← Package tree (mirrors target filesystem)
│   ├── DEBIAN/
│   │   ├── control           ← Package metadata (name, version, deps)
│   │   ├── conffiles         ← Files dpkg preserves on upgrade
│   │   ├── postinst          ← Creates /opt/vnalpha/venv, installs vnalpha
│   │   ├── prerm             ← Pre-removal (no-op — preserves warehouse)
│   │   └── postrm            ← Post-removal (purge cleans venv/config only)
│   ├── usr/bin/
│   │   ├── vnalpha           ← Host launcher (sources env, execs venv binary)
│   │   └── vnalpha-poc       ← POC demo launcher (opens TUI at DEMO_DATE)
│   └── etc/vnalpha/
│       └── vnalpha.env       ← Config template (conffile — dpkg preserves it)
└── test/
    └── test_packaging.sh     ← Structural and behavioural validation stubs
```

## Design decisions

### Vendored venv, not system pip

`postinst` builds a Python virtual environment at `/opt/vnalpha/venv` from
pre-downloaded wheels bundled inside the `.deb` by `build-deb.sh`. This means:

- **No network access required on the target host** after the `.deb` is copied.
- **No system Python packages are modified** — the venv is isolated.
- **Upgrade rebuilds the venv cleanly** — `postinst` removes and recreates it,
  ensuring no stale wheels linger across versions.

### Warehouse is never touched by the package

`/var/lib/openstock/warehouse/` is **not** part of the `.deb` payload. The
package only:

1. Creates the directory if it does not exist (`postinst`).
2. Explicitly refuses to remove it in `prerm` and `postrm`.

This means `apt remove vnalpha`, `apt purge vnalpha`, and package upgrades all
leave the user's DuckDB research data untouched.

### Config file is a dpkg conffile

`/etc/vnalpha/vnalpha.env` is listed in `DEBIAN/conffiles`. dpkg will prompt
the operator before overwriting it on upgrade if they have modified it locally.

### Launchers use `exec` for clean signal handling

Both `/usr/bin/vnalpha` and `/usr/bin/vnalpha-poc` use `exec venv/bin/vnalpha`
so the venv Python process replaces the shell process (same PID). This ensures:

- Signals (Ctrl-C, SIGTERM) go directly to the Python process.
- No extra shell process hangs around as a wrapper.
- `ps aux` shows the Python process, not a wrapper shell.

## Building the package

### Prerequisites

```bash
# On Debian/Ubuntu:
sudo apt install -y dpkg python3 python3-pip python3-venv
```

### Build

```bash
# From the repo root:
./packaging/build-deb.sh
# Output: packaging/dist/vnalpha_0.1.0_amd64.deb
```

Override the version:

```bash
./packaging/build-deb.sh --version 0.2.0
```

Build without downloading wheels (if wheels are already present):

```bash
./packaging/build-deb.sh --offline
```

### Inspect the .deb before installing

```bash
dpkg-deb --info packaging/dist/vnalpha_0.1.0_amd64.deb
dpkg -c packaging/dist/vnalpha_0.1.0_amd64.deb
```

## Installing

```bash
sudo apt install -y ./packaging/dist/vnalpha_0.1.0_amd64.deb
# or:
sudo dpkg -i ./packaging/dist/vnalpha_0.1.0_amd64.deb && sudo apt -f install
```

After installation:

```bash
vnalpha --help
vnalpha-poc --help
cat /etc/vnalpha/vnalpha.env
```

## Post-install configuration

Edit `/etc/vnalpha/vnalpha.env` to match your deployment:

```bash
sudo nano /etc/vnalpha/vnalpha.env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `VNSTOCK_SERVICE_URL` | `http://127.0.0.1:6900` | Local data API URL |
| `VNALPHA_WAREHOUSE_PATH` | `/var/lib/openstock/warehouse/warehouse.duckdb` | DuckDB file path |
| `VNALPHA_DEMO_DATE` | `2026-07-06` | Date for `vnalpha-poc` demo |
| `VNALPHA_LOG_LEVEL` | `INFO` | Log verbosity |
| `VNALPHA_LLM_*` | _(empty)_ | Optional LLM assistant config |

## First-run workflow

```bash
# 1. Initialize warehouse (creates schema)
vnalpha init

# 2. Sync data (requires vnstock-service running)
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha sync index --symbol VNINDEX --start 2024-01-01

# 3. Build features and score
vnalpha build canonical
vnalpha build features --date 2026-07-06
vnalpha score --date 2026-07-06

# 4. View watchlist
vnalpha watchlist --date 2026-07-06

# 5. Launch TUI (requires a TTY — terminal/SSH/tmux)
vnalpha tui --date 2026-07-06
# or shortcut:
vnalpha-poc
```

## Upgrade procedure

```bash
# Build new version
./packaging/build-deb.sh --version X.Y.Z

# Optionally backup warehouse first
openstock-backup-warehouse  # (if installed)

# Upgrade
sudo apt install -y ./packaging/dist/vnalpha_X.Y.Z_amd64.deb

# The warehouse at /var/lib/openstock/warehouse is NOT affected.
```

## Removal

```bash
# Remove package (preserves /etc/vnalpha/vnalpha.env and warehouse)
sudo apt remove vnalpha

# Purge package + config (STILL preserves warehouse)
sudo apt purge vnalpha
# Note: /var/lib/openstock/warehouse is NEVER removed, even on purge.
```

## Running validation

```bash
./packaging/test/test_packaging.sh [path/to/vnalpha.deb]
```

## Safety boundaries

This package is strictly research-only:

- `vnalpha` connects only to `127.0.0.1:6900` (configured in `vnalpha.env`).
- The CLI exposes no brokerage, order, account, portfolio, or trading commands.
- The TUI is for research observation only.
- The optional LLM assistant is constrained to research/explanation workflows.

See the openspec design doc for the full safety boundary specification:
`openspec/changes/deploy-and-verify-poc/design.md`
