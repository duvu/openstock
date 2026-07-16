# Capability: MVP1 startup and preflight

## ADDED Requirements

### Requirement: One-command idempotent MVP1 startup

The platform SHALL provide one command that brings the MVP1 chat vertical slice
to a ready state on a single Linux host: validate/create persistent directories
with safe permissions, verify or start `vnstock-service` and wait for health,
migrate the warehouse without overwriting valid data, run the MVP1 preflight,
and launch the TUI or print the exact launch command. Running it repeatedly
SHALL be idempotent.

#### Scenario: Startup prepares and reports the launch command
- **GIVEN** a configured host
- **WHEN** `openstock-mvp1-start --no-launch` runs
- **THEN** it creates/validates the warehouse, knowledge and log directories,
  ensures the service is healthy, migrates the warehouse and prints the exact
  `vnalpha tui` launch command.

#### Scenario: Startup is idempotent
- **GIVEN** a host already started once
- **WHEN** startup runs again
- **THEN** it reuses existing directories and data and exits successfully
  without overwriting valid data or credentials.

#### Scenario: Missing dependencies produce specific remediation
- **GIVEN** neither a healthy service nor Docker Compose
- **WHEN** startup runs
- **THEN** it exits non-zero with a specific remediation message.

### Requirement: Read-only installed-host MVP1 preflight

`openstock-verify --mvp1` SHALL verify the MVP1 chat-slice dependencies —
service health, warehouse path/writability/free disk and migration readiness,
knowledge path readiness, LLM route state, backup/restore availability and
release metadata — using PASS/WARN/FAIL diagnostics and a non-zero exit code for
blockers. It SHALL be read-only and SHALL support `--ci` for offline use.

#### Scenario: CI preflight passes offline with no failures
- **WHEN** `openstock-verify --mvp1 --ci` runs
- **THEN** it exits 0 and emits no `[FAIL]` lines.

#### Scenario: Backup and restore commands are visible in preflight
- **WHEN** the MVP1 preflight runs
- **THEN** it reports the availability of the backup and restore commands.

#### Scenario: Degraded LLM is a warning, not a blocker
- **GIVEN** the LLM route is unavailable
- **WHEN** the MVP1 preflight runs
- **THEN** the LLM check is a `[WARN]` and deterministic commands remain usable.
