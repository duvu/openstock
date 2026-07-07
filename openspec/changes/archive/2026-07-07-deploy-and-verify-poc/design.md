# Design: Deploy and Verify POC

## Deployment model

The POC deployment has two different runtime modes:

```text
Long-running Docker data platform:
  - vnstock-service

Short-lived Docker jobs:
  - vnalpha-worker init/sync/build/score/outcome commands

Host-native terminal app:
  - vnalpha Debian package
  - user runs `vnalpha tui` directly from terminal/SSH/tmux
```

The TUI must not be deployed as a background Docker daemon because Textual requires an interactive terminal/TTY.

## Target filesystem layout

```text
/opt/openstock/
  docker-compose.yml
  .env.example

/var/lib/openstock/
  warehouse/
    warehouse.duckdb
    backups/
  vnstock-config/

/etc/openstock/
  openstock.env

/etc/systemd/system/
  openstock-data-platform.service
  openstock-daily-pipeline.service        # optional
  openstock-daily-pipeline.timer          # optional

/opt/vnalpha/
  venv/

/etc/vnalpha/
  vnalpha.env

/usr/bin/
  vnalpha
  vnalpha-poc
  openstock-verify
  openstock-backup-warehouse
  openstock-restore-warehouse             # optional guarded command
```

## Configuration

### `/etc/openstock/openstock.env`

```bash
OPENSTOCK_HOME=/opt/openstock
OPENSTOCK_DATA_DIR=/var/lib/openstock
OPENSTOCK_WAREHOUSE_DIR=/var/lib/openstock/warehouse
OPENSTOCK_WAREHOUSE_PATH=/var/lib/openstock/warehouse/warehouse.duckdb
VNSTOCK_SERVICE_BIND=127.0.0.1
VNSTOCK_SERVICE_PORT=6900
OPENSTOCK_DEMO_DATE=2026-07-06
```

### `/etc/vnalpha/vnalpha.env`

```bash
VNSTOCK_SERVICE_URL=http://127.0.0.1:6900
VNALPHA_WAREHOUSE_PATH=/var/lib/openstock/warehouse/warehouse.duckdb
VNALPHA_LOG_LEVEL=INFO

# Optional internal LLM gateway
VNALPHA_LLM_ENDPOINT=http://127.0.0.1:4000/v1/chat/completions
VNALPHA_LLM_MODEL=gpt-4o-mini
VNALPHA_LLM_API_KEY=
VNALPHA_LLM_STORE_RAW=false

VNALPHA_DEMO_DATE=2026-07-06
```

## Docker Compose design

The Compose file must contain:

```text
vnstock-service
  - long-running container
  - localhost-only published port
  - healthcheck
  - read-only credential/config mount

vnalpha-worker
  - job container
  - profile: job
  - same vnalpha code/runtime as Debian package
  - shared warehouse bind mount
  - VNSTOCK_SERVICE_URL=http://vnstock-service:6900
```

`vnalpha-worker` must not run by default when `docker compose up -d` is executed without the `job` profile.

## systemd design

### `openstock-data-platform.service`

Responsible only for long-running data platform services.

```ini
[Unit]
Description=OpenStock data platform
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/openstock
EnvironmentFile=-/etc/openstock/openstock.env
ExecStartPre=/usr/bin/install -d -m 0755 /var/lib/openstock/warehouse
ExecStartPre=/usr/bin/install -d -m 0755 /var/lib/openstock/vnstock-config
ExecStart=/usr/bin/docker compose up -d vnstock-service
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

### Daily pipeline timer

Optional timer units may run the data pipeline after market close or during an operator-approved window.

The timer must run worker jobs, not the TUI.

## Debian package design

The `vnalpha` Debian package should vendor a Python virtual environment under `/opt/vnalpha/venv` to avoid system Python dependency drift.

It should install:

```text
/usr/bin/vnalpha
/usr/bin/vnalpha-poc
/etc/vnalpha/vnalpha.env
/opt/vnalpha/venv
```

### `/usr/bin/vnalpha`

```bash
#!/usr/bin/env bash
set -a
[ -f /etc/vnalpha/vnalpha.env ] && . /etc/vnalpha/vnalpha.env
set +a

exec /opt/vnalpha/venv/bin/vnalpha "$@"
```

### `/usr/bin/vnalpha-poc`

```bash
#!/usr/bin/env bash
set -euo pipefail
set -a
[ -f /etc/vnalpha/vnalpha.env ] && . /etc/vnalpha/vnalpha.env
set +a

DEMO_DATE="${VNALPHA_DEMO_DATE:-today}"
exec /opt/vnalpha/venv/bin/vnalpha tui --date "$DEMO_DATE"
```

## Verification command design

Add an operator command:

```bash
openstock-verify
```

The command should perform checks in order and return non-zero on failure.

Recommended checks:

```text
1. host prerequisites
   - docker available
   - docker compose available
   - current user can run docker or service is already active

2. data platform status
   - systemctl is-active openstock-data-platform
   - docker compose ps vnstock-service
   - vnstock-service health endpoint returns status ok

3. safety boundary
   - forbidden endpoints return 404 for /v1/order, /v1/account, /v1/portfolio, /v1/trading

4. warehouse status
   - warehouse directory exists
   - warehouse file exists or can be initialized
   - `vnalpha init` succeeds through vnalpha-worker or host vnalpha

5. pipeline smoke test
   - sync symbols succeeds
   - sync small symbol set OHLCV succeeds
   - sync VNINDEX benchmark succeeds
   - build canonical succeeds
   - build features for demo date succeeds
   - score for demo date succeeds
   - watchlist for demo date returns rows or clear no-data message

6. terminal app status
   - `vnalpha --help` succeeds
   - `vnalpha watchlist --date <demo-date>` succeeds
   - `vnalpha tui --help` or import check succeeds without launching interactive TUI in CI mode

7. optional assistant status
   - if LLM endpoint/key are configured, `vnalpha ask --no-execute` or equivalent plan-preview command succeeds
```

Verification output should be structured and readable:

```text
[OK] docker compose available
[OK] vnstock-service healthz
[OK] forbidden endpoint /v1/order returns 404
[OK] warehouse initialized
[OK] pipeline score produced 12 watchlist rows
[WARN] assistant check skipped: VNALPHA_LLM_API_KEY not configured
```

## Backup design

Before schema-changing migrations or package upgrades, create a timestamped copy:

```bash
/var/lib/openstock/warehouse/backups/warehouse-YYYYMMDD-HHMMSS.duckdb
```

Backup script:

```bash
openstock-backup-warehouse
```

Rules:

```text
- refuse backup if a writer job is currently running, unless --force is provided
- create backup directory if missing
- copy the DuckDB file atomically where possible
- print backup path
```

## Rollback design

Rollback levels:

```text
Level 1: rollback vnalpha Debian package
  - apt install previous .deb

Level 2: rollback Docker data platform images
  - docker compose pull/tag previous image
  - docker compose up -d vnstock-service

Level 3: rollback warehouse file
  - stop writer jobs
  - stop data platform if required
  - restore from selected backup
  - run openstock-verify
```

Warehouse restore must be explicit and guarded.

## Safety design

The deployment must preserve research-only boundaries:

```text
- vnstock-service must not expose broker/order/account/portfolio/margin/trading endpoints
- vnalpha-worker must only execute data/research pipeline commands
- vnalpha TUI must not include broker execution commands
- LLM assistant must remain constrained to research/explanation workflows
```

## Acceptance test strategy

The deploy/verify implementation is accepted when:

```text
- a fresh host can install and start the data platform
- `openstock-verify` passes core checks
- warehouse backup and restore procedure is documented or scripted
- a demo operator can run `vnalpha tui` directly from terminal
- deployment does not require running the TUI inside a Docker daemon
```
