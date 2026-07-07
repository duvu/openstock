# Specification: POC Deployment Verification

## ADDED Requirements

### Requirement: The system shall provide a Docker-managed data platform

The POC SHALL provide a Docker Compose based data platform containing `vnstock-service` and `vnalpha-worker`.

`vnstock-service` SHALL be a long-running service.

`vnalpha-worker` SHALL be a short-lived job container and SHALL NOT start by default with the long-running data platform.

#### Scenario: Data platform starts only long-running services

- **GIVEN** a fresh deployed host
- **WHEN** the operator starts the data platform
- **THEN** `vnstock-service` SHALL start as a Docker container
- **AND** `vnalpha-worker` SHALL NOT run unless the job profile or explicit run command is used.

#### Scenario: Data service is localhost-only by default

- **GIVEN** the data platform is started with default configuration
- **WHEN** the operator inspects the published ports
- **THEN** `vnstock-service` SHALL be bound to `127.0.0.1:6900`
- **AND** it SHALL NOT bind to a public interface by default.

---

### Requirement: vnstock-service shall expose health checks and preserve data-only safety boundaries

`vnstock-service` SHALL expose a health endpoint.

It SHALL NOT expose broker, order, account, portfolio, margin, transfer, or trading endpoints.

#### Scenario: Health endpoint returns ok

- **GIVEN** `vnstock-service` is running
- **WHEN** the operator calls `GET /healthz`
- **THEN** the response SHALL indicate service status `ok`.

#### Scenario: Forbidden endpoints remain unavailable

- **GIVEN** `vnstock-service` is running
- **WHEN** the operator calls `/v1/order`, `/v1/account`, `/v1/portfolio`, or `/v1/trading`
- **THEN** each endpoint SHALL return `404` or an equivalent not-found response
- **AND** no credential, account, order, or portfolio data SHALL be returned.

---

### Requirement: The system shall store the DuckDB warehouse on a stable host path

The POC SHALL use DuckDB as the analytical warehouse.

The canonical path SHALL be:

```text
/var/lib/openstock/warehouse/warehouse.duckdb
```

Docker jobs and the terminal app SHALL access the same warehouse path through environment configuration.

#### Scenario: Worker and terminal app share the same warehouse

- **GIVEN** `vnalpha-worker` writes the warehouse at `/warehouse/warehouse.duckdb` inside the container
- **AND** the host bind mount maps `/var/lib/openstock/warehouse` to `/warehouse`
- **WHEN** the user runs `vnalpha watchlist` from the host terminal
- **THEN** host `vnalpha` SHALL read `/var/lib/openstock/warehouse/warehouse.duckdb`
- **AND** it SHALL see the data produced by `vnalpha-worker`.

---

### Requirement: vnalpha-worker shall execute data pipeline jobs

`vnalpha-worker` SHALL support the POC data pipeline commands:

```text
init
sync symbols
sync ohlcv
sync index
build canonical
build features
score
watchlist
```

#### Scenario: Initial warehouse setup succeeds

- **GIVEN** the data platform is running
- **WHEN** the operator runs `vnalpha-worker init`
- **THEN** schema migrations SHALL complete
- **AND** the DuckDB warehouse SHALL exist at the configured path.

#### Scenario: Demo pipeline produces a watchlist or clear no-data message

- **GIVEN** the warehouse is initialized
- **WHEN** the operator runs the demo pipeline for a configured demo date
- **THEN** symbol sync SHALL complete
- **AND** OHLCV sync SHALL complete for the demo universe or return explicit skipped/error counts
- **AND** benchmark sync SHALL complete
- **AND** canonical build SHALL complete
- **AND** feature build SHALL complete
- **AND** scoring SHALL complete
- **AND** watchlist query SHALL either return rows or a clear no-data message.

---

### Requirement: The terminal workspace shall be installed as a Debian package

The POC SHALL package `vnalpha` as a Debian package for host-native terminal use.

The package SHALL install launchers:

```text
/usr/bin/vnalpha
/usr/bin/vnalpha-poc
```

The package SHALL load environment configuration from:

```text
/etc/vnalpha/vnalpha.env
```

#### Scenario: vnalpha command is available after package install

- **GIVEN** `vnalpha.deb` is installed
- **WHEN** the user runs `vnalpha --help`
- **THEN** the command SHALL execute successfully
- **AND** show CLI help.

#### Scenario: TUI starts from terminal

- **GIVEN** `vnalpha.deb` is installed
- **AND** the warehouse path is configured
- **WHEN** the user runs `vnalpha tui --date <demo-date>` from an interactive terminal
- **THEN** the Textual TUI SHALL start without import or configuration errors.

---

### Requirement: The TUI shall not be deployed as a background Docker daemon

The POC SHALL NOT run `vnalpha tui` as a long-running Docker daemon.

Interactive TUI usage SHALL be host-native through the Debian package or explicit interactive terminal execution.

#### Scenario: Data platform startup does not run TUI

- **GIVEN** `openstock-data-platform` is started
- **WHEN** the operator lists running containers
- **THEN** no background `vnalpha tui` container SHALL be running.

---

### Requirement: The system shall provide systemd control for the data platform

The POC SHALL provide a systemd unit for starting/stopping Docker-managed long-running data services.

The unit SHALL create required host directories before startup.

#### Scenario: systemd starts the data platform

- **GIVEN** Docker is installed
- **AND** `/opt/openstock/docker-compose.yml` exists
- **WHEN** the operator runs `systemctl start openstock-data-platform`
- **THEN** required directories SHALL exist
- **AND** `vnstock-service` SHALL start
- **AND** the unit SHALL report active or successful state.

---

### Requirement: The system shall provide post-deploy verification

The POC SHALL provide an `openstock-verify` command.

The command SHALL run required checks and return non-zero when required checks fail.

#### Scenario: Verification passes after successful deployment

- **GIVEN** a successfully deployed POC host
- **WHEN** the operator runs `openstock-verify`
- **THEN** the command SHALL verify Docker availability
- **AND** verify data platform status
- **AND** verify `vnstock-service` health
- **AND** verify forbidden endpoints
- **AND** verify warehouse path and schema
- **AND** verify `vnalpha --help`
- **AND** verify watchlist command behavior
- **AND** print `[OK]` for passed checks.

#### Scenario: Verification warns when optional assistant is not configured

- **GIVEN** LLM environment variables are not configured
- **WHEN** the operator runs `openstock-verify`
- **THEN** assistant verification SHALL be skipped or marked `[WARN]`
- **AND** the command SHALL NOT fail solely because optional LLM configuration is absent.

#### Scenario: Verification fails when data service is unavailable

- **GIVEN** `vnstock-service` is not running
- **WHEN** the operator runs `openstock-verify`
- **THEN** the command SHALL print `[FAIL]` for data service health
- **AND** return a non-zero exit code.

---

### Requirement: The system shall provide warehouse backup before risky operations

The POC SHALL provide a warehouse backup command.

The command SHALL create timestamped backups under:

```text
/var/lib/openstock/warehouse/backups
```

#### Scenario: Backup creates timestamped DuckDB copy

- **GIVEN** a warehouse exists
- **WHEN** the operator runs `openstock-backup-warehouse`
- **THEN** a timestamped `.duckdb` copy SHALL be created under the backup directory
- **AND** the script SHALL print the created backup path.

#### Scenario: Backup avoids concurrent writer risk

- **GIVEN** a writer job is currently running or a writer lock exists
- **WHEN** the operator runs `openstock-backup-warehouse` without `--force`
- **THEN** the command SHALL refuse or warn and exit non-zero
- **AND** it SHALL NOT create an unsafe backup.

---

### Requirement: The system shall document rollback procedures

The POC SHALL document rollback for:

```text
vnalpha Debian package
Docker images/data platform
DuckDB warehouse file
```

#### Scenario: Rollback requires verification after restore

- **GIVEN** the operator restores a warehouse backup
- **WHEN** restore completes
- **THEN** the operator documentation SHALL require running `openstock-verify`
- **AND** the restored system SHALL pass required checks before demo use.

---

### Requirement: Scheduled pipeline jobs shall not create concurrent writers

If scheduled pipeline jobs are implemented, they SHALL prevent concurrent writer jobs against the DuckDB warehouse.

#### Scenario: Daily pipeline refuses second writer

- **GIVEN** a pipeline writer job is running
- **WHEN** the daily pipeline is triggered again
- **THEN** the second job SHALL not start writing
- **AND** it SHALL report a lock or concurrency warning.

---

### Requirement: Deployment shall remain research-only

Deployment and verification SHALL preserve the research-only safety boundary.

No deployment unit SHALL expose or enable broker order placement, account access, portfolio mutation, transfer, margin, or automated trading features.

#### Scenario: Research-only boundary is verified after deploy

- **GIVEN** the system is deployed
- **WHEN** `openstock-verify` runs safety checks
- **THEN** forbidden endpoint checks SHALL pass
- **AND** no deploy script SHALL configure broker execution endpoints
- **AND** no TUI command SHALL advertise order/account/portfolio execution.
