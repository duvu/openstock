# daily-core-maintenance Specification

## Purpose
Define deterministic daily research-data maintenance, truthful outcomes,
idempotent and mutation-safe execution, disabled-by-default package scheduling,
canonical roadmap governance and exact-candidate clean-host acceptance.

## Requirements
### Requirement: Deterministic daily maintenance
The system SHALL provide one bounded daily maintenance operation that resolves
one effective Vietnam market session and correlation identity, then executes
symbol snapshot, incremental OHLCV, benchmark, gap repair, canonicalization,
features, scoring, market/group context and selective memory stages in declared
dependency order.

#### Scenario: Successful session run
- **WHEN** required providers and validated inputs succeed for a market session
- **THEN** the operation returns `SUCCESS` with versioned stage counts, lineage and correlation evidence

#### Scenario: Partial symbol failure
- **WHEN** one bounded symbol fails with typed provider diagnostics and another succeeds
- **THEN** the successful symbol continues through eligible downstream stages and the operation returns `PARTIAL` without exposing raw provider content

### Requirement: Mutation-safe date and repeat semantics
The operation MUST avoid persistent mutation for dry-run and explicit
non-session requests, reuse current validated artifacts, and create no duplicate
raw ingestion, claims or memory document generations for an equivalent repeat.

#### Scenario: Explicit non-session date
- **WHEN** the requested date is not a versioned Vietnam trading session
- **THEN** the operation returns `NOOP`, opens no persistent writer path and performs no provisioning

#### Scenario: Equivalent repeated run
- **WHEN** the same session is run again with current source and derived evidence
- **THEN** current stages are skipped or idempotently upserted and no duplicate raw or memory generation is created

### Requirement: Truthful machine-readable outcomes
The command SHALL emit a versioned JSON result containing the requested date,
effective session, status, stage outcomes, counts, successful/failed symbols,
typed diagnostics references, remediation and correlation identity. `FAILED`
MUST exit 1, `PARTIAL` MUST exit 3 and `SUCCESS`/`NOOP` MUST exit 0.

#### Scenario: Packaged partial run
- **WHEN** the packaged command completes useful work but one required stage or symbol remains partial
- **THEN** stdout contains one parseable `PARTIAL` result and the process exits 3

### Requirement: Disabled safe scheduling
The Debian package SHALL install a weekday timer using an explicit
Asia/Ho_Chi_Minh schedule and a oneshot service protected by a stable writer
lock. Installation and upgrade MUST NOT enable or start the timer.

#### Scenario: Fresh package install
- **WHEN** the package is installed on a host with systemd
- **THEN** both units are loadable, the timer is disabled, and no daily job starts automatically

#### Scenario: Concurrent invocation
- **WHEN** the stable writer lock is already held
- **THEN** a second service invocation exits 75 without deleting the lock inode or starting maintenance

### Requirement: Canonical roadmap and historical documentation
Current repository and component documentation SHALL link the exact #238 URL as
the live source for priority, dependencies and closure evidence. Older roadmap
and vision documents MUST be marked historical and non-authoritative.

#### Scenario: Superseded pointer reintroduced
- **WHEN** a current roadmap document references #90 or #209 even alongside #238
- **THEN** repository consistency validation fails

### Requirement: Exact-candidate release acceptance
The core loop MUST NOT be declared complete until a clean prepared-host run
records the exact commit and package identity and exercises install, preflight,
data provisioning, maintenance, CLI/TUI/assistant consumption, repeated
execution, provider-failure isolation, timer state and the research-only
boundary.

#### Scenario: Evidence from another commit
- **WHEN** validation evidence was generated from a package or commit other than the closure candidate
- **THEN** the evidence is diagnostic only and completion remains blocked

#### Scenario: Clean-host acceptance succeeds
- **WHEN** all required paths pass on the exact candidate and the sanitized report contains no secrets
- **THEN** the report may be attached to #245 and used to close the dependency chain
