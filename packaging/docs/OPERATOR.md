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
sudo groupadd --system openstock 2>/dev/null || true
sudo chown root:openstock /etc/vnalpha/vnalpha.env
sudo chmod 0640 /etc/vnalpha/vnalpha.env
sudo usermod -aG openstock "$USER"
```

Edit both files to match your environment before enabling the service:

- `/etc/openstock/openstock.env` — warehouse paths, service bind address,
  demo date
- `/etc/vnalpha/vnalpha.env` — service URL, warehouse path, optional LLM
  gateway config

The vnalpha environment can contain the LLM credential and is intentionally
readable only by root and members of the `openstock` group. Start a new login
session after adding the operator to that group.

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
sudo install -m 0755 packaging/scripts/openstock-mvp1-start        /usr/bin/
sudo install -m 0755 packaging/scripts/openstock-backup-warehouse  /usr/bin/
sudo install -m 0755 packaging/scripts/openstock-restore-warehouse /usr/bin/
```

### Step 6: Run the post-install check

```bash
openstock-verify
```

All required checks should show `[OK]`. `[WARN]` lines are informational;
`[FAIL]` lines need attention before using the platform.

### Step 7: One-command MVP1 startup (chat vertical slice)

For the MVP1 chat vertical slice, one idempotent command validates persistent
paths, starts and health-checks `vnstock-service`, migrates the warehouse, runs
the read-only MVP1 preflight and launches the TUI:

```bash
openstock-mvp1-start                # start everything and open the TUI
openstock-mvp1-start --no-launch    # prepare, then print the exact launch command
openstock-verify --mvp1             # read-only MVP1 preflight only (safe to re-run)
```

`openstock-verify --mvp1` reports service health, warehouse path/disk,
read-only warehouse schema compatibility, active writer-lock state, knowledge
path, LLM route readiness (`vnalpha preflight`), backup/restore availability and
release metadata. Corrupt or incompatible warehouses are blockers. `--ci`
explicitly skips live warehouse inspection. Startup writes compose, migration
and preflight diagnostics below the reported run log directory; `--skip-preflight`
is the only verifier bypass and emits a visible warning.

Both commands load `/etc/openstock/openstock.env` and
`/etc/vnalpha/vnalpha.env`. Compose operations are anchored to
`OPENSTOCK_HOME` (normally `/opt/openstock`) rather than the caller's current
directory. FiinQuantX readiness requires the reviewed VCI reference source and
all four enabled, explicit-only Gate A capabilities under the FiinQuantX
provider object.

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

## 8.4 Provisioner and daily pipeline

The supported single-host deployment has exactly one durable provisioning
worker. It reads `/var/lib/openstock/queue/provisioning.sqlite3` and is separate
from the weekday producer timer. The Debian package installs both units but
does not enable either one.

### Enable the one provisioner

```bash
sudo systemctl enable --now openstock-provisioner.service
sudo systemctl status openstock-provisioner.service
sudo journalctl -u openstock-provisioner.service -n 100
```

Do not start an additional `vnalpha provision worker` process on this host.
Use `vnalpha jobs health` to inspect the local queue; it is non-destructive.

### Enable the weekday producer

The optional daily producer enqueues the deterministic maintenance goals on
Vietnam market weekdays at 17:30 Asia/Ho_Chi_Minh. The provisioner processes
those goals sequentially under the warehouse writer lock.

### Confirm the packaged units

```bash
systemctl cat openstock-daily-pipeline.service
systemctl cat openstock-daily-pipeline.timer
systemctl is-enabled openstock-daily-pipeline.timer
```

### Enable and start

```bash
sudo systemctl enable --now openstock-daily-pipeline.timer
```

### Check the schedule

```bash
systemctl list-timers --all openstock-daily-pipeline.timer
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

Each invocation emits one JSON result containing `schema_version`, status,
effective session, stage results, typed diagnostics references, and mutation
counts. `FAILED` exits 1, `PARTIAL` exits 3 (accepted by the service), and a
held writer lock exits 75 without overlapping the active writer. The stable
lock inode remains at `/run/openstock-pipeline.lock`; operators must not delete
it to recover from contention.

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
without a TTY. For scheduled data jobs, use the packaged daily maintenance
timer described in section 8.4.

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

Backups land in `/var/lib/openstock/warehouse/backups/` as a pair such as
`warehouse-20260707-143022.duckdb` and
`warehouse-20260707-143022.queue.sqlite3`. A queue-absence marker is stored
instead when no durable queue exists yet.

The script acquires both the warehouse writer lock and the provisioner lock
(`/run/openstock-pipeline.lock` and `/run/openstock-provisioner.lock`), so it
cannot copy a mismatched database/queue pair. Stop the provisioner before a
backup or restore. By default the command fails immediately while either lock
is held; pass `--wait SECONDS` to block for up to that many seconds:

```bash
sudo systemctl stop openstock-provisioner.service
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

`openstock-restore-warehouse` requires a paired queue snapshot or absence
marker, acquires both locks, verifies each source **before** touching live
state, and takes `pre-restore-*` snapshots of the current warehouse and queue.
It stages and verifies both restored files; a failure rolls both back to the
pre-restore state. Pass `--yes` to skip the interactive confirmation and
`--wait SECONDS` to wait for an active lock. Start the provisioner only after
`openstock-verify` passes.

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
