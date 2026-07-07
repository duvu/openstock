# Operator Runbook — vnalpha

Operational procedures for running, monitoring, and recovering the vnalpha research workspace.

## Daily research pipeline

### Run the pipeline (live)

```bash
openstock-run-pipeline
```

Runs the full 7-step EOD pipeline under an flock lock:

1. `sync symbols` — refresh symbol list
2. `sync ohlcv` — ingest EOD price/volume for VN30
3. `sync index` — ingest VNINDEX EOD
4. `build canonical` — build the canonical OHLCV dataset
5. `build features` — compute technical/liquidity/RS features
6. `score` — score pattern detections
7. `watchlist` — update watchlist

### Dry-run (verify plan without executing)

```bash
openstock-run-pipeline --dry-run
```

### Run for a specific date

```bash
openstock-run-pipeline --date 2026-06-30
```

### Run with a CI fixture (offline mode)

```bash
openstock-run-pipeline --ci-fixture
```

## Backup

```bash
openstock-backup-warehouse
```

Creates a timestamped gzip archive of the DuckDB warehouse in `~/.vnalpha/backups/`.

## Static CI checks

```bash
openstock-verify --ci
```

Validates systemd unit files, package manifest completeness, and CLI entrypoints.
Exits 0 when all checks pass; exits 1 if any FAIL-level check fails.

## Verify R0 tests

```bash
make -C /path/to/openstock verify-r0
```

Runs the R0 acceptance test suite (phase 5 e2e, features, warehouse, CLI).

## Verify R2 CI checks

```bash
make -C /path/to/openstock verify-r2-ci
```

Runs packaging and systemd static checks.

## Package build and verify

```bash
make build-vnalpha-deb     # build the .deb package
make verify-vnalpha-deb    # verify the built package is installable
```

## Log locations

| Component | Log |
|---|---|
| Pipeline | `journalctl -u openstock-daily-pipeline` |
| vnalpha service | `journalctl -u vnalpha` |

## Recovery

### Re-run a failed pipeline step

```bash
docker compose run --rm vnalpha-worker <step> [flags]
```

Steps: `sync symbols`, `sync ohlcv`, `sync index`, `build canonical`, `build features`, `score`, `watchlist`.

### Reset the warehouse

```bash
rm ~/.vnalpha/warehouse.duckdb
openstock-run-pipeline  # rebuilds from scratch
```

### Restore from backup

```bash
cp ~/.vnalpha/backups/warehouse-<timestamp>.duckdb.gz /tmp/
gunzip /tmp/warehouse-<timestamp>.duckdb.gz
cp /tmp/warehouse-<timestamp>.duckdb ~/.vnalpha/warehouse.duckdb
```

## Monitoring

The systemd timer `openstock-daily-pipeline.timer` triggers the pipeline daily.
Check status:

```bash
systemctl status openstock-daily-pipeline.timer
systemctl status openstock-daily-pipeline.service
journalctl -u openstock-daily-pipeline --since today
```

## Fresh-host setup checklist

Use this checklist when deploying to a new machine or after a clean OS reinstall.

### Prerequisites

- Docker Engine installed and running
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Repository cloned: `git clone <repo> ~/IdeaProjects/openstock && cd ~/IdeaProjects/openstock`

### Step-by-step

```bash
# 1. Verify Docker Compose config parses cleanly
docker compose config

# 2. Start vnstock-service
docker compose up -d vnstock-service

# 3. Create the vnalpha virtualenv and install
cd vnalpha && uv venv .venv && cd ..
make install-vnalpha

# 4. Install packaging scripts
sudo cp packaging/scripts/openstock-* /usr/local/bin/
sudo chmod +x /usr/local/bin/openstock-*

# 5. Run static CI checks (does not require network or running services)
openstock-verify --ci

# 6. Run the pipeline for the first time (requires vnstock-service running)
openstock-run-pipeline

# 7. Verify workspace integrity after first run
openstock-verify

# 8. Take an initial backup
openstock-backup-warehouse
```

### Expected results

| Step | Expected output |
|------|----------------|
| `docker compose config` | Prints service config, exit 0 |
| `docker compose up -d vnstock-service` | Container starts, `docker ps` shows healthy |
| Worker `init` (first pipeline run) | DB created at `~/.vnalpha/warehouse.duckdb` |
| Pipeline wrapper | 7-step run completes, exit 0 |
| `openstock-verify` | `[OK]` for all checks |
| `openstock-backup-warehouse` | `.duckdb.gz` written to `~/.vnalpha/backups/` |

### Notes

- All `openstock-*` scripts are in `packaging/scripts/` — install to `/usr/local/bin/` for system-wide access.
- Package build (`make build-vnalpha-deb`) requires access to the internal Nexus repository (`nexus.x51.vn`); deferred on machines without network access to that host.

## Safety notes

- The system does **not** connect to any broker API.
- No orders are placed automatically.
- AI features are read-only research tools; they cannot execute trades.
- All tool calls in the chat workspace are gated by `safety.py` permission rules.
