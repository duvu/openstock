# Operator Guide

This guide covers everything needed to run and maintain the OpenStock data
platform day-to-day. The platform has two components: a Docker-based data
service (`vnstock-service`) and a host-installed terminal research app
(`vnalpha`).

---

## 8.1 First install

### Prerequisites

| Requirement | Minimum version |
|---|---|
| Docker Engine | 24.x |
| Docker Compose plugin | V2 (`docker compose`, not `docker-compose`) |
| Python (host) | Not required — vnalpha ships its own venv |
| Debian/Ubuntu host | Tested on Ubuntu 22.04 LTS |

Install Docker following the official docs for your distro. Confirm both
commands work before proceeding:

```bash
docker --version
docker compose version
```

### Step 1: Place the compose file

```bash
sudo mkdir -p /opt/openstock
sudo cp packaging/docker-compose.yml /opt/openstock/docker-compose.yml
```

### Step 2: Install config files

```bash
sudo mkdir -p /etc/openstock /etc/vnalpha
sudo cp packaging/config/openstock.env /etc/openstock/openstock.env
sudo cp packaging/config/vnalpha.env   /etc/vnalpha/vnalpha.env
```

Edit both files to match your environment before enabling the service:

- `/etc/openstock/openstock.env` — warehouse paths, service bind address,
  demo date
- `/etc/vnalpha/vnalpha.env` — service URL, warehouse path, optional LLM
  gateway config

### Step 3: Install the systemd unit

```bash
sudo cp packaging/systemd/openstock-data-platform.service \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openstock-data-platform
```

The service creates `/var/lib/openstock/warehouse` on startup if it doesn't
exist, then starts the `vnstock-service` container.

Confirm it came up:

```bash
sudo systemctl status openstock-data-platform
```

### Step 4: Install the vnalpha Debian package

```bash
sudo dpkg -i vnalpha_*.deb
```

This installs:
- `/usr/bin/vnalpha` and `/usr/bin/vnalpha-poc` launchers
- `/opt/vnalpha/venv/` — self-contained Python venv
- `/etc/vnalpha/vnalpha.env` — config file (only on fresh install; not
  overwritten on upgrade)

### Step 5: Install helper scripts

```bash
sudo install -m 0755 packaging/scripts/openstock-verify           /usr/bin/
sudo install -m 0755 packaging/scripts/openstock-backup-warehouse  /usr/bin/
sudo install -m 0755 packaging/scripts/openstock-restore-warehouse /usr/bin/
```

### Step 6: Run the post-install check

```bash
openstock-verify
```

All required checks should show `[OK]`. `[WARN]` lines are informational;
`[FAIL]` lines need attention before using the platform.

---

## 8.2 Start, stop, and status

### Via systemd (recommended)

```bash
# Start
sudo systemctl start openstock-data-platform

# Stop
sudo systemctl stop openstock-data-platform

# Restart
sudo systemctl restart openstock-data-platform

# Status
sudo systemctl status openstock-data-platform

# Logs (last 50 lines)
sudo journalctl -u openstock-data-platform -n 50
```

### Via Docker Compose directly

These commands are useful for debugging when systemd isn't the right tool:

```bash
cd /opt/openstock

# Check running containers
docker compose ps

# Stream logs
docker compose logs -f vnstock-service

# Force restart the service container
docker compose restart vnstock-service

# Full teardown (all containers + networks)
docker compose down

# Pull latest image and start fresh
docker compose pull vnstock-service
docker compose up -d vnstock-service
```

---

## 8.3 Initial data sync

Before the TUI has anything to display, you need to populate the warehouse.
Run the worker jobs in order.

### Step 1: Initialize the warehouse schema

```bash
docker compose -f /opt/openstock/docker-compose.yml \
  run --rm vnalpha-worker init
```

Or use the verify script to initialize if it detects a missing warehouse:

```bash
openstock-verify --init
```

### Step 2: Sync the symbol universe

```bash
docker compose -f /opt/openstock/docker-compose.yml \
  run --rm vnalpha-worker sync symbols
```

### Step 3: Sync historical OHLCV data

```bash
docker compose -f /opt/openstock/docker-compose.yml \
  run --rm vnalpha-worker sync ohlcv
```

### Step 4: Build derived features

```bash
docker compose -f /opt/openstock/docker-compose.yml \
  run --rm vnalpha-worker build
```

### Step 5: Score stocks

```bash
docker compose -f /opt/openstock/docker-compose.yml \
  run --rm vnalpha-worker score
```

After these steps the warehouse is ready. The TUI will show data when you
open it.

---

## 8.4 Daily pipeline

The optional daily pipeline re-runs sync, build, and score on a schedule.

### Install the timer units

```bash
sudo cp packaging/systemd/openstock-daily-pipeline.service \
        /etc/systemd/system/
sudo cp packaging/systemd/openstock-daily-pipeline.timer   \
        /etc/systemd/system/
sudo systemctl daemon-reload
```

### Enable and start

```bash
sudo systemctl enable --now openstock-daily-pipeline.timer
```

### Check the schedule

```bash
systemctl list-timers openstock-daily-pipeline.timer
```

### Trigger a manual run

```bash
sudo systemctl start openstock-daily-pipeline.service
```

### Disable the timer

```bash
sudo systemctl disable --now openstock-daily-pipeline.timer
```

### Read recent pipeline logs

```bash
sudo journalctl -u openstock-daily-pipeline.service -n 100
```

The pipeline service uses a lock file to prevent concurrent writers. If a
job is already running when the timer fires, the new invocation exits
cleanly rather than overlapping.

---

## 8.5 Opening the TUI

### From a local terminal

```bash
vnalpha tui
```

For a specific date:

```bash
vnalpha tui --date 2026-07-01
```

### From an SSH session

The TUI uses the Textual framework, which requires a real TTY. A standard
SSH session provides one:

```bash
ssh user@yourserver vnalpha tui
```

Or connect interactively and run it from the shell prompt.

### Inside tmux or screen

Start a named session so you can detach and reattach:

```bash
tmux new-session -s research
vnalpha tui
# Detach with Ctrl-b d
# Reattach later:
tmux attach-session -t research
```

### Demo mode

`vnalpha-poc` opens the TUI for the configured demo date without any
arguments. It reads `VNALPHA_DEMO_DATE` from `/etc/vnalpha/vnalpha.env`:

```bash
vnalpha-poc
```

To override the date for one invocation:

```bash
vnalpha-poc --date 2026-06-15
```

### Not suitable for non-interactive use

Don't run `vnalpha tui` from cron, systemd service units, or any context
without a TTY. For scheduled data jobs, use the `vnalpha-worker` Docker
profile instead (see section 8.4).

---

## 8.6 Verification and troubleshooting

### Run the verifier

```bash
openstock-verify
```

In CI or environments without a live service:

```bash
openstock-verify --ci
```

### Output legend

| Status | Meaning |
|---|---|
| `[OK]` | Check passed |
| `[WARN]` | Non-critical issue, worth investigating |
| `[FAIL]` | Required check failed, platform is not healthy |
| `[SKIP]` | Check skipped (CI mode or prerequisite missing) |

The final line is either `Status: PASS` or `Status: FAIL (N required check(s) failed)`.

### Common issues

**`[FAIL] docker binary not found in PATH`**
Install Docker Engine. See `https://docs.docker.com/engine/install/`.

**`[WARN] openstock-data-platform systemd service status: inactive`**
The service is installed but not started:
```bash
sudo systemctl start openstock-data-platform
```

**`[FAIL] vnstock-service healthz returned HTTP 000`**
The container isn't running or is still starting up. Check:
```bash
sudo systemctl status openstock-data-platform
docker compose -f /opt/openstock/docker-compose.yml ps
docker compose -f /opt/openstock/docker-compose.yml logs vnstock-service
```

**`[FAIL] forbidden endpoint /v1/order returned HTTP 200`**
This is a safety-boundary breach. Stop the service immediately and check
which image version is running. See section 8.8.

**`[WARN] warehouse file not found`**
The warehouse hasn't been initialized. Run:
```bash
openstock-verify --init
```
or follow section 8.3.

**vnalpha TUI crashes on start**
Confirm the warehouse path in `/etc/vnalpha/vnalpha.env` matches the actual
file location, and that `vnstock-service` is reachable at the configured URL.

---

## 8.7 Backup and rollback

### Take a manual backup

```bash
sudo openstock-backup-warehouse
```

Backups land in `/var/lib/openstock/warehouse/backups/` with names like
`warehouse-20260707-143022.duckdb`.

The script acquires the **same exclusive `flock`** that pipeline writers use
(on `/run/openstock-pipeline.lock`), so it cannot copy the database while a
writer job is running. By default it fails immediately if a writer holds the
lock; pass `--wait SECONDS` to block for up to that many seconds:

```bash
sudo openstock-backup-warehouse --wait 300
```

The copy is written to a `.partial` file, verified by opening it read-only and
scanning every table, and only then published atomically under its final name.
`--force` skips **only** the verification step — it does **not** bypass the
writer lock:

```bash
sudo openstock-backup-warehouse --force
```

### List backups

```bash
ls -lht /var/lib/openstock/warehouse/backups/
```

### Restore a backup

```bash
# Restore the most recent backup:
sudo openstock-restore-warehouse --latest

# Or restore a specific file:
sudo openstock-restore-warehouse --backup \
  /var/lib/openstock/warehouse/backups/warehouse-20260707-143022.duckdb
```

`openstock-restore-warehouse` acquires the same writer lock, verifies the chosen
backup **before** touching the live warehouse, takes a `pre-restore-*.duckdb`
snapshot of the current warehouse, replaces the warehouse atomically, and
verifies the result. If the restored warehouse fails verification it is rolled
back to the pre-restore snapshot, so a failed restore always leaves a usable
warehouse in place. Pass `--yes` to skip the interactive confirmation and
`--wait SECONDS` to wait for an active writer lock.

### Rollback procedures

For full rollback instructions, see [ROLLBACK.md](./ROLLBACK.md). It covers:

- Level 1: Rollback the `vnalpha` Debian package to a previous `.deb`
- Level 2: Pin and restore a previous Docker image for `vnstock-service`
- Level 3: Restore the DuckDB warehouse from a timestamped backup

Always run `openstock-verify` after any rollback to confirm the platform is
healthy before re-enabling the daily pipeline.

---

## 8.8 Research-only safety boundaries

`vnstock-service` is a **read-only market data proxy**. It does not and
must not expose brokerage, trading, account, or order functionality.

### Forbidden endpoints

The following URL paths must return HTTP 404 on the running service. The
`openstock-verify` script checks all four on every run:

| Endpoint | Expected | Meaning |
|---|---|---|
| `/v1/order` | 404 | No order placement |
| `/v1/account` | 404 | No account access |
| `/v1/portfolio` | 404 | No portfolio data |
| `/v1/trading` | 404 | No trading operations |

If any of these returns a non-404 status, `openstock-verify` marks it as
`[FAIL]` and exits non-zero. Stop the platform and investigate immediately.

### What vnstock-service does

- Proxies market data requests from the vnalpha Python library
- Serves price history, symbol metadata, and screener data
- Binds to `127.0.0.1:6900` only (not exposed on a public interface by
  default)
- Exposes `/healthz` for liveness checking

### What vnstock-service does NOT do

- Place, modify, or cancel orders
- Read or write to any broker account
- Access portfolio positions or balances
- Execute trades of any kind

### What vnalpha does

- Reads data from `vnstock-service` and the local DuckDB warehouse
- Displays research screens in the terminal TUI
- Computes scores and watchlists for research purposes
- Does not implement brokerage or trading logic

The research scope is intentional. If you need brokerage connectivity, that
requires a separate, purpose-built integration that is outside the scope of
this platform.
