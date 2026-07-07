# Deploy and Verify POC

## Summary

Add an OpenSpec change for implementing the deployment and post-deployment verification workflow for the selected POC architecture.

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

This change defines the implementation work needed to deploy, verify, operate, and rollback the POC safely.

## Problem

The architecture decision has been documented, but the repository still needs an executable deployment and verification specification.

Without a deploy/verify spec, the POC can drift into manual, unrepeatable steps:

```text
- Docker Compose may be incomplete or inconsistent across machines.
- vnalpha-worker may not have a standard job interface.
- The Debian package may not install a reliable terminal launcher.
- DuckDB warehouse path/permissions may be inconsistent.
- There may be no smoke test proving the POC works after installation.
- There may be no rollback/backup procedure before schema-changing jobs.
- There may be no clear acceptance criteria for post-deploy readiness.
```

## Goals

- Provide a repeatable local/single-host POC deployment workflow.
- Deploy `vnstock-service` as a Docker-managed data service.
- Deploy `vnalpha-worker` as a Docker job image for data pipeline commands.
- Package `vnalpha` as a Debian terminal app for direct `vnalpha tui` usage.
- Use a stable DuckDB warehouse bind mount.
- Provide explicit post-deploy verification commands and expected outcomes.
- Provide smoke tests for data service, warehouse, pipeline, CLI, TUI entrypoint, and optional LLM assistant.
- Provide backup and rollback procedures for the DuckDB warehouse and package/container changes.
- Preserve the research-only safety boundary.

## Non-goals

```text
- No Kubernetes deployment in this change.
- No multi-user production architecture.
- No replacement of DuckDB with PostgreSQL, TimescaleDB, or ClickHouse.
- No broker/order/account/portfolio integration.
- No browser UI deployment.
- No automated trading.
- No public internet exposure for vnstock-service.
```

## Proposed deliverables

```text
1. Docker Compose configuration for the data platform.
2. Dockerfile for vnalpha-worker.
3. Debian packaging scripts for vnalpha terminal app.
4. systemd wrapper for OpenStock data platform.
5. Optional systemd timer/service for daily pipeline execution.
6. Smoke-test script for post-deploy verification.
7. Backup and rollback scripts or documented commands.
8. Operator documentation for deploy, verify, backup, rollback, and troubleshooting.
```

## Success criteria

The POC is deployable when a fresh machine can run:

```bash
sudo apt install ./vnalpha_*.deb
sudo install -m 0644 packaging/systemd/openstock-data-platform.service /etc/systemd/system/
sudo systemctl enable --now openstock-data-platform
openstock-verify
vnalpha tui --date <demo-date>
```

and the verification confirms:

```text
- Docker data platform is running.
- vnstock-service health endpoint returns status ok.
- DuckDB warehouse exists at the configured path.
- Warehouse schema migrations complete.
- Data pipeline can sync/build/score a small demo universe.
- Watchlist query returns expected rows or a clear no-data message.
- TUI entrypoint starts without import/config errors.
- Optional assistant check succeeds when LLM env is configured.
- Research-only forbidden endpoints remain unavailable.
```
