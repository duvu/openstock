# Tasks: Deploy and Verify POC

## 1. Docker data platform

- [ ] 1.1 Add or update top-level Docker Compose configuration for `vnstock-service` and `vnalpha-worker`.
- [ ] 1.2 Ensure `vnstock-service` binds to `127.0.0.1:6900` by default.
- [ ] 1.3 Add healthcheck for `vnstock-service` using `/healthz`.
- [ ] 1.4 Add persistent config mount for `vnstock-service`.
- [ ] 1.5 Add `vnalpha-worker` service using `profiles: ["job"]`.
- [ ] 1.6 Mount `/var/lib/openstock/warehouse` into `vnalpha-worker` as `/warehouse`.
- [ ] 1.7 Set `VNSTOCK_SERVICE_URL=http://vnstock-service:6900` in `vnalpha-worker`.
- [ ] 1.8 Set `VNALPHA_WAREHOUSE_PATH=/warehouse/warehouse.duckdb` in `vnalpha-worker`.

## 2. vnalpha worker image

- [ ] 2.1 Add `vnalpha/Dockerfile` for worker/job runtime.
- [ ] 2.2 Install `vnalpha` and runtime dependencies in the worker image.
- [ ] 2.3 Use `entrypoint: ["vnalpha"]` for job commands.
- [ ] 2.4 Verify worker can run `init`, `sync`, `build`, `score`, `watchlist`, and optional `outcome` commands.

## 3. Debian package for terminal app

- [ ] 3.1 Add packaging script for `vnalpha.deb`.
- [ ] 3.2 Package a Python virtual environment under `/opt/vnalpha/venv`.
- [ ] 3.3 Add `/usr/bin/vnalpha` launcher.
- [ ] 3.4 Add `/usr/bin/vnalpha-poc` launcher.
- [ ] 3.5 Add `/etc/vnalpha/vnalpha.env` as a config file.
- [ ] 3.6 Ensure `vnalpha tui` starts from host terminal without Docker.
- [ ] 3.7 Ensure package upgrade does not delete the warehouse.

## 4. Systemd data platform wrapper

- [ ] 4.1 Add `openstock-data-platform.service`.
- [ ] 4.2 Ensure the service creates `/var/lib/openstock/warehouse` before startup.
- [ ] 4.3 Ensure the service creates `/var/lib/openstock/vnstock-config` before startup.
- [ ] 4.4 Ensure `ExecStart` runs `docker compose up -d vnstock-service`.
- [ ] 4.5 Ensure `ExecStop` runs `docker compose down`.
- [ ] 4.6 Document enable/start/status commands.

## 5. Optional daily pipeline scheduler

- [ ] 5.1 Add `openstock-daily-pipeline.service`.
- [ ] 5.2 Add `openstock-daily-pipeline.timer`.
- [ ] 5.3 Make the pipeline execute worker jobs, not the TUI.
- [ ] 5.4 Add a lock file or equivalent guard to prevent concurrent writers.
- [ ] 5.5 Document how to enable/disable the timer.

## 6. Post-deploy verification command

- [ ] 6.1 Add `openstock-verify` script.
- [ ] 6.2 Check Docker and Docker Compose availability.
- [ ] 6.3 Check `openstock-data-platform` systemd status when systemd is available.
- [ ] 6.4 Check `vnstock-service` container status.
- [ ] 6.5 Check `http://127.0.0.1:6900/healthz`.
- [ ] 6.6 Check forbidden endpoints return 404: `/v1/order`, `/v1/account`, `/v1/portfolio`, `/v1/trading`.
- [ ] 6.7 Check warehouse directory exists.
- [ ] 6.8 Initialize warehouse if explicitly requested or verify existing schema.
- [ ] 6.9 Run a small pipeline smoke test using a small demo universe.
- [ ] 6.10 Check `vnalpha --help`.
- [ ] 6.11 Check `vnalpha watchlist --date <demo-date>`.
- [ ] 6.12 Check TUI import/entrypoint without launching an interactive session in CI mode.
- [ ] 6.13 Optionally check assistant if LLM env is configured.
- [ ] 6.14 Return non-zero when a required check fails.
- [ ] 6.15 Print `[OK]`, `[WARN]`, and `[FAIL]` statuses.

## 7. Backup and rollback

- [ ] 7.1 Add `openstock-backup-warehouse` script.
- [ ] 7.2 Store backups under `/var/lib/openstock/warehouse/backups`.
- [ ] 7.3 Add timestamped backup names.
- [ ] 7.4 Add writer-job guard before backup.
- [ ] 7.5 Document rollback of `vnalpha.deb`.
- [ ] 7.6 Document rollback of Docker images.
- [ ] 7.7 Document guarded restore of DuckDB warehouse from backup.
- [ ] 7.8 Require `openstock-verify` after restore.

## 8. Operator documentation

- [ ] 8.1 Document first install.
- [ ] 8.2 Document start/stop/status commands.
- [ ] 8.3 Document initial data sync.
- [ ] 8.4 Document daily pipeline.
- [ ] 8.5 Document opening TUI from terminal/SSH/tmux.
- [ ] 8.6 Document verification output and troubleshooting.
- [ ] 8.7 Document backup and rollback.
- [ ] 8.8 Document research-only safety boundaries.

## 9. Tests and validation

- [ ] 9.1 Add shellcheck or equivalent validation for shell scripts if available.
- [ ] 9.2 Add unit tests for verification script helpers where feasible.
- [ ] 9.3 Add CI-safe verification mode that skips live network/data-provider calls.
- [ ] 9.4 Add manual smoke-test checklist for a fresh VM.
- [ ] 9.5 Validate `docker compose config`.
- [ ] 9.6 Validate Debian package installs and exposes `vnalpha` command.
- [ ] 9.7 Validate `vnalpha tui --help` or equivalent non-interactive entrypoint check.

## 10. Acceptance checklist

- [ ] 10.1 Fresh host can start `openstock-data-platform`.
- [ ] 10.2 `vnstock-service` health endpoint returns ok.
- [ ] 10.3 Forbidden endpoints remain unavailable.
- [ ] 10.4 Warehouse initializes at `/var/lib/openstock/warehouse/warehouse.duckdb`.
- [ ] 10.5 Worker pipeline can sync/build/score a small demo universe.
- [ ] 10.6 `vnalpha.deb` installs successfully.
- [ ] 10.7 User can run `vnalpha tui` directly from terminal.
- [ ] 10.8 `openstock-verify` passes required checks.
- [ ] 10.9 Backup script creates a restorable DuckDB copy.
- [ ] 10.10 Rollback procedure is documented.
