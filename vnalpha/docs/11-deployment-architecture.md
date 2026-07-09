# Deployment Architecture

## Summary

`vnalpha` should be deployed as a terminal-first research workspace, while the data platform remains Docker-managed.

The deployment architecture is intentionally split into three layers:

```text
Docker data platform
  - vnstock-service
  - vnalpha-worker batch jobs
  - optional scheduler

Persistent warehouse
  - DuckDB file stored on a host bind mount

Terminal workspace
  - vnalpha Debian package
  - direct terminal/TUI usage similar to OpenCode
```

This keeps the data platform reproducible and service-oriented while keeping the user-facing TUI native to the terminal.

## Deployment goals

- Run `vnalpha tui` directly from a user terminal, SSH session, or `tmux`, similar to OpenCode.
- Keep `vnstock-service` as a Docker service because it is the data platform layer.
- Keep DuckDB for the POC because it is lightweight, zero-server, analytical, and well-suited to local-first research workflows.
- Manage data ingestion/build/score jobs through Docker worker containers.
- Store the warehouse in a stable host path so both Docker jobs and the terminal app can access the same DuckDB file.
- Avoid running the TUI as a background Docker daemon.
- Preserve the research-only safety boundary: no broker orders, no account access, no portfolio mutation, no automated trading.

## High-level architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ User Terminal / SSH / tmux                                    │
│                                                              │
│   $ vnalpha tui --date 2026-07-06                             │
│                                                              │
│ vnalpha.deb                                                   │
│ - CLI/TUI                                                     │
│ - command layer                                               │
│ - assistant layer                                             │
│ - reads DuckDB warehouse                                      │
└───────────────────────────┬──────────────────────────────────┘
                            │ reads local/shared file
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ DuckDB Warehouse                                              │
│                                                              │
│ /var/lib/openstock/warehouse/warehouse.duckdb                 │
│                                                              │
│ - market_ohlcv_raw                                            │
│ - canonical_ohlcv                                             │
│ - feature_snapshot                                            │
│ - candidate_score                                             │
│ - daily_watchlist                                             │
│ - outcome tables                                              │
│ - assistant/tool trace tables                                 │
└───────────────────────────▲──────────────────────────────────┘
                            │ writes/sync/build/score
                            │
┌───────────────────────────┴──────────────────────────────────┐
│ Docker Data Platform                                          │
│                                                              │
│ docker compose                                                │
│ - vnstock-service                                             │
│ - vnalpha-worker                                              │
│ - optional scheduler                                          │
│                                                              │
│ vnstock-service: http://127.0.0.1:6900                        │
│ vnalpha-worker: batch job writing DuckDB                      │
└──────────────────────────────────────────────────────────────┘
```

## Component responsibilities

### `vnstock-service`

Deployment form: Docker service.

Responsibilities:

```text
- provider access
- market data normalization
- provider fallback and health
- data quality checks
- data-only HTTP API
```

Default exposure:

```text
http://127.0.0.1:6900
```

The service must remain data-only. Broker, order, account, portfolio, margin, transfer, and trading endpoints are out of scope.

### `vnalpha-worker`

Deployment form: Docker job container.

Responsibilities:

```text
- initialize warehouse schema
- sync symbol master
- sync equity OHLCV
- sync benchmark/index OHLCV
- build canonical OHLCV
- build features
- score candidate watchlist
- optionally evaluate outcomes
```

The worker writes to the shared DuckDB file through a bind mount.

### DuckDB warehouse

Deployment form: host file managed as persistent storage.

Canonical path:

```text
/var/lib/openstock/warehouse/warehouse.duckdb
```

DuckDB is not deployed as a database server. It is an embedded analytical warehouse file used by `vnalpha-worker` and `vnalpha`.

For the POC, this is the preferred storage model because it is simple, local-first, analytical, and low-operations.

### `vnalpha` terminal app

Deployment form: Debian package.

Responsibilities:

```text
- expose the `vnalpha` CLI command
- launch the Textual TUI with `vnalpha tui`
- inspect watchlists and evidence
- run read-only command workflows
- run assistant prompts through the configured LLM gateway
- read from the shared DuckDB warehouse
```

The TUI should be launched directly from the user's terminal, SSH session, or `tmux`, not as a background Docker daemon.

### Optional LLM gateway

Deployment form: external or internal OpenAI-compatible endpoint.

Configuration should be provided through `/etc/vnalpha/vnalpha.env`:

```bash
VNALPHA_LLM_ENDPOINT=http://127.0.0.1:4000/v1/chat/completions
VNALPHA_LLM_MODEL=oc-gpt-5.4-mini
VNALPHA_LLM_API_KEY=
VNALPHA_LLM_STORE_RAW=false
```

For internal deployments, the endpoint should point to the organization's LLM gateway rather than a public default endpoint.

## Deployment units

### Data platform unit

The data platform is Docker-managed.

Recommended package/config layout:

```text
/opt/openstock/docker-compose.yml
/etc/openstock/openstock.env
/var/lib/openstock/warehouse/warehouse.duckdb
/var/lib/openstock/vnstock-config/
/etc/systemd/system/openstock-data-platform.service
```

It manages:

```text
- vnstock-service
- vnalpha-worker image
- shared DuckDB bind mount
- optional scheduler/timer
```

### Terminal app unit

`vnalpha` should be installed through a Debian package.

Recommended layout:

```text
/opt/vnalpha/venv/
/usr/bin/vnalpha
/usr/bin/vnalpha-poc
/etc/vnalpha/vnalpha.env
```

The package should not start the TUI automatically. The user starts it explicitly:

```bash
vnalpha tui --date 2026-07-06
```

or through a convenience launcher:

```bash
vnalpha-poc
```

## Docker Compose reference

```yaml
services:
  vnstock-service:
    build: ./vnstock
    image: vnstock-service:latest
    container_name: vnstock-service
    ports:
      - "127.0.0.1:6900:6900"
    volumes:
      - /var/lib/openstock/vnstock-config:/home/vnstock/.config/vnstock:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD",
          "python3",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6900/healthz')",
        ]
      interval: 30s
      timeout: 5s
      retries: 3

  vnalpha-worker:
    build:
      context: .
      dockerfile: vnalpha/Dockerfile
    image: vnalpha-worker:latest
    environment:
      VNSTOCK_SERVICE_URL: http://vnstock-service:6900
      VNALPHA_WAREHOUSE_PATH: /warehouse/warehouse.duckdb
      VNALPHA_LOG_LEVEL: INFO
    volumes:
      - /var/lib/openstock/warehouse:/warehouse
    depends_on:
      - vnstock-service
    profiles:
      - job
    entrypoint: ["vnalpha"]
```

## `vnalpha` Debian package config

`/etc/vnalpha/vnalpha.env`:

```bash
VNSTOCK_SERVICE_URL=http://127.0.0.1:6900
VNALPHA_WAREHOUSE_PATH=/var/lib/openstock/warehouse/warehouse.duckdb
VNALPHA_LOG_LEVEL=INFO

# Optional internal LLM gateway
VNALPHA_LLM_ENDPOINT=http://127.0.0.1:4000/v1/chat/completions
VNALPHA_LLM_MODEL=oc-gpt-5.4-mini
VNALPHA_LLM_API_KEY=
VNALPHA_LLM_STORE_RAW=false

# Optional demo date
VNALPHA_DEMO_DATE=2026-07-06
```

`/usr/bin/vnalpha`:

```bash
#!/usr/bin/env bash
set -a
[ -f /etc/vnalpha/vnalpha.env ] && . /etc/vnalpha/vnalpha.env
set +a

exec /opt/vnalpha/venv/bin/vnalpha "$@"
```

`/usr/bin/vnalpha-poc`:

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a
[ -f /etc/vnalpha/vnalpha.env ] && . /etc/vnalpha/vnalpha.env
set +a

DEMO_DATE="${VNALPHA_DEMO_DATE:-today}"

exec /opt/vnalpha/venv/bin/vnalpha tui --date "$DEMO_DATE"
```

## Runtime flow

### 1. Start data platform

```bash
sudo mkdir -p /var/lib/openstock/warehouse
sudo mkdir -p /var/lib/openstock/vnstock-config

cd /opt/openstock
docker compose up -d vnstock-service

curl http://127.0.0.1:6900/healthz
```

### 2. Initialize the warehouse

```bash
docker compose --profile job run --rm vnalpha-worker init
```

### 3. Run the data pipeline

```bash
docker compose --profile job run --rm vnalpha-worker sync symbols

docker compose --profile job run --rm vnalpha-worker sync ohlcv \
  --universe VN30 \
  --start 2024-01-01

docker compose --profile job run --rm vnalpha-worker sync index \
  --symbol VNINDEX \
  --start 2024-01-01

docker compose --profile job run --rm vnalpha-worker build canonical

docker compose --profile job run --rm vnalpha-worker build features \
  --date 2026-07-06

docker compose --profile job run --rm vnalpha-worker score \
  --date 2026-07-06
```

### 4. Open TUI from terminal

```bash
vnalpha tui --date 2026-07-06
```

## systemd wrapper for the data platform

The data platform can be controlled with systemd while still using Docker Compose internally.

```ini
[Unit]
Description=OpenStock data platform
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/openstock
ExecStart=/usr/bin/docker compose up -d vnstock-service
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl enable --now openstock-data-platform
```

For scheduled pipelines, add separate timer units:

```text
openstock-daily-pipeline.service
openstock-daily-pipeline.timer
```

The daily pipeline should run the `vnalpha-worker` job commands, not the interactive TUI.

## Concurrency rules for DuckDB

DuckDB is an embedded database file. The POC should follow simple operational rules:

```text
1. Pipeline jobs write the warehouse.
2. TUI primarily reads the warehouse.
3. Do not run multiple writers at the same time.
4. For demos, finish the pipeline before opening the TUI.
5. If a scheduler is enabled, avoid running heavy jobs during live demo sessions.
```

If the system later requires many concurrent writers, central access control, SQL over network, or multiple user-facing apps, the warehouse layer should be revisited. Candidate upgrades include PostgreSQL/TimescaleDB or ClickHouse. For the current POC, DuckDB remains the correct default.

## Packaging roadmap

### Phase 1: POC packaging

```text
- Add Dockerfile for vnalpha-worker.
- Add Docker Compose profile for job execution.
- Add `vnalpha.deb` packaging scripts.
- Add `/usr/bin/vnalpha` launcher.
- Add `/usr/bin/vnalpha-poc` launcher.
- Add systemd wrapper for `openstock-data-platform`.
```

### Phase 2: Operator hardening

```text
- Add healthcheck command for data platform readiness.
- Add backup script for `/var/lib/openstock/warehouse`.
- Add restore procedure.
- Add daily pipeline timer.
- Add log rotation.
- Add POC smoke-test script.
```

### Phase 3: Team deployment hardening

```text
- Add optional internal network exposure for vnstock-service.
- Add auth/reverse proxy if vnstock-service is shared across users.
- Add warehouse access policy.
- Add read-only TUI mode while pipeline writer is running.
- Add migration/backup guard before schema changes.
```

## Final decision

The selected deployment architecture is:

```text
Data Platform:
  Docker Compose
  - vnstock-service
  - vnalpha-worker
  - shared DuckDB bind mount
  - optional scheduler

Terminal Workspace:
  Debian package
  - vnalpha CLI/TUI
  - one-command launcher
  - reads DuckDB warehouse

Storage:
  DuckDB file
  /var/lib/openstock/warehouse/warehouse.duckdb
```

In short:

```text
Docker manages the data platform and batch jobs.
Debian package manages the terminal user experience.
DuckDB is the persisted analytical warehouse file shared by both sides.
```
