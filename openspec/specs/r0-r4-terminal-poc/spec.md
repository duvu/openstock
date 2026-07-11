# r0-r4-terminal-poc Specification

## Purpose
TBD - created by archiving change complete-r0-r4-terminal-poc. Update Purpose after archive.
## Requirements
### Requirement: R0 baseline shall produce deterministic daily research artifacts

The system SHALL provide a deterministic, executable research pipeline that can initialize the warehouse, ingest or load market data, build canonical OHLCV, build features, score candidates, and generate a daily watchlist.

The pipeline SHALL be testable without live provider or internet access.

#### Scenario: Fixture-backed pipeline completes without network access

- **GIVEN** an isolated DuckDB warehouse
- **AND** fixture symbols, OHLCV rows, and VNINDEX benchmark rows are loaded
- **WHEN** migrations, canonical build, feature build, scoring, and watchlist generation run
- **THEN** `feature_snapshot` SHALL contain rows for eligible symbols
- **AND** `candidate_score` SHALL contain persisted score rows
- **AND** `daily_watchlist` SHALL contain eligible candidates or a clear no-data result
- **AND** the test SHALL NOT call live provider services.

#### Scenario: Service-backed pipeline exposes explicit operational behavior

- **GIVEN** `vnstock-service` is running locally
- **WHEN** the operator runs the demo pipeline commands
- **THEN** every step SHALL either complete successfully or return explicit skipped/error counts
- **AND** no step SHALL silently succeed while producing no usable artifact.

---

### Requirement: R0 command contract shall be stable and documented

The CLI and Makefile command contract SHALL be aligned for the POC pipeline.

Supported commands SHALL include:

```text
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start <date>
vnalpha sync ohlcv --symbols FPT,VNM --start <date>
vnalpha sync index --symbol VNINDEX --start <date>
vnalpha build canonical
vnalpha build features --date <date>
vnalpha score --date <date>
vnalpha watchlist --date <date>
vnalpha tui --date <date>
```

#### Scenario: Explicit symbols override named universe

- **GIVEN** both explicit symbols and a named universe are provided
- **WHEN** `vnalpha sync ohlcv` resolves the symbol list
- **THEN** explicit `--symbols` SHALL take precedence over `--universe`.

#### Scenario: Unknown universe fails closed

- **GIVEN** an unknown universe name
- **WHEN** the user runs `vnalpha sync ohlcv --universe <unknown>`
- **THEN** the command SHALL exit non-zero
- **AND** print an actionable error message.

---

### Requirement: R0 warehouse migrations shall be idempotent and upgrade-safe

Warehouse migrations SHALL create all R0-R4 tables on a fresh DuckDB file and upgrade existing DuckDB files safely.

#### Scenario: Fresh warehouse initializes

- **GIVEN** no existing DuckDB warehouse
- **WHEN** `vnalpha init` runs
- **THEN** all required R0-R4 tables SHALL exist.

#### Scenario: Existing warehouse upgrades without destructive reset

- **GIVEN** an existing DuckDB warehouse missing newer R0-R4 columns
- **WHEN** migrations run
- **THEN** missing columns SHALL be added where possible
- **AND** existing market, feature, score, watchlist, outcome, assistant, and chat data SHALL NOT be dropped.

---

### Requirement: R0 canonical data and feature artifacts shall preserve quality and lineage

Canonical OHLCV, feature snapshots, candidate scores, and watchlists SHALL preserve enough quality and lineage metadata for audit and review.

#### Scenario: Canonical OHLCV deduplicates rows

- **GIVEN** duplicate raw OHLCV rows for the same symbol, time, and interval
- **WHEN** canonical OHLCV is built
- **THEN** the canonical table SHALL contain one selected row for that symbol, time, and interval
- **AND** selected provider and quality status SHALL be traceable.

#### Scenario: Feature status records actual data date

- **GIVEN** the requested feature date differs from the latest available bar date
- **WHEN** feature snapshots are built
- **THEN** `as_of_bar_date` SHALL record the actual bar date used
- **AND** `feature_data_status` SHALL indicate `STALE_DATE`.

#### Scenario: Missing benchmark is explicit

- **GIVEN** VNINDEX benchmark data is missing
- **WHEN** feature snapshots are built
- **THEN** relative-strength fields SHALL be null or unavailable
- **AND** `feature_data_status` SHALL indicate `MISSING_BENCHMARK`
- **AND** the system SHALL NOT silently present relative strength as valid.

---

### Requirement: R0 scoring shall enforce canonical ontology

Persisted `candidate_score` and `daily_watchlist` rows SHALL use canonical candidate classes and setup types.

Canonical candidate classes SHALL be:

```text
STRONG_CANDIDATE
WATCH_CANDIDATE
WEAK_CANDIDATE
IGNORE
```

Canonical setup types SHALL be:

```text
ACCUMULATION_BASE
BREAKOUT_ATTEMPT
MOMENTUM_CONTINUATION
PULLBACK_TO_TREND
MEAN_REVERSION
UNCLASSIFIED
```

#### Scenario: Non-canonical candidate class is rejected

- **GIVEN** a scoring result contains a legacy or unknown candidate class
- **WHEN** the system attempts to persist `candidate_score`
- **THEN** persistence SHALL fail closed
- **AND** the invalid value SHALL NOT be written.

#### Scenario: Watchlist excludes ignore candidates

- **GIVEN** candidate scores exist for a date
- **WHEN** the daily watchlist is generated
- **THEN** rows with `candidate_class = IGNORE` SHALL NOT appear in `daily_watchlist`.

---

### Requirement: R1 architecture documentation shall match implemented behavior

Deployment architecture documentation SHALL describe actual implemented files, commands, paths, and boundaries, or clearly mark unimplemented items as planned.

#### Scenario: Operator can follow documented runtime flow

- **GIVEN** a fresh operator reads the deployment documentation
- **WHEN** they follow the documented command sequence
- **THEN** the commands SHALL correspond to actual files and scripts in the repository
- **AND** missing/future features SHALL be explicitly labelled as not yet implemented.

#### Scenario: Research-only boundary is documented

- **GIVEN** deployment documentation is reviewed
- **THEN** it SHALL state that OpenStock is research-only
- **AND** it SHALL state that broker login, account APIs, order placement, portfolio mutation, margin, transfer, auto-trading, and LLM-only prediction are out of scope.

---

### Requirement: R2 data platform shall be Docker-managed and localhost-first

The POC SHALL provide a Docker Compose data platform containing a long-running `vnstock-service` and a short-lived `vnalpha-worker` job container.

`vnstock-service` SHALL bind to localhost by default.

`vnalpha-worker` SHALL not run by default with long-running services.

#### Scenario: Data platform starts without worker job

- **GIVEN** the operator runs `docker compose up -d`
- **THEN** `vnstock-service` SHALL start
- **AND** `vnalpha-worker` SHALL NOT run unless explicitly invoked through its job profile or run command.

#### Scenario: Data service remains localhost-only

- **GIVEN** default Docker Compose configuration
- **WHEN** the operator inspects published ports
- **THEN** `vnstock-service` SHALL be bound to `127.0.0.1:6900`
- **AND** it SHALL NOT bind to a public interface by default.

---

### Requirement: R2 worker shall execute the POC pipeline against the shared warehouse

`vnalpha-worker` SHALL execute pipeline jobs and write to the shared DuckDB warehouse.

#### Scenario: Worker initializes shared warehouse

- **GIVEN** `/var/lib/openstock/warehouse` is mounted into the worker
- **WHEN** the operator runs `docker compose --profile job run --rm vnalpha-worker init`
- **THEN** warehouse schema SHALL initialize at `/warehouse/warehouse.duckdb` inside the worker
- **AND** the host SHALL see the DuckDB file at `/var/lib/openstock/warehouse/warehouse.duckdb`.

#### Scenario: Worker can run smoke pipeline

- **GIVEN** the data service is healthy
- **WHEN** the worker runs the demo pipeline
- **THEN** it SHALL complete init, sync/load, build, score, and watchlist checks
- **OR** return explicit actionable failure output.

---

### Requirement: R2 terminal app shall be host-native and packageable

The POC SHALL package `vnalpha` for host-native terminal use.

The package SHALL provide:

```text
/opt/vnalpha/venv
/usr/bin/vnalpha
/usr/bin/vnalpha-poc
/etc/vnalpha/vnalpha.env
```

#### Scenario: Package exposes vnalpha command

- **GIVEN** `vnalpha.deb` is installed
- **WHEN** the user runs `vnalpha --help`
- **THEN** the command SHALL run successfully.

#### Scenario: TUI starts from host terminal

- **GIVEN** `vnalpha.deb` is installed
- **WHEN** the user runs `vnalpha tui --date <demo-date>` from a terminal, SSH session, or tmux
- **THEN** the TUI SHALL start without import or configuration errors.

#### Scenario: TUI is not deployed as a daemon

- **GIVEN** the data platform is started
- **WHEN** the operator lists running Docker containers
- **THEN** no background `vnalpha tui` daemon container SHALL exist.

---

### Requirement: R2 shall provide post-deploy verification

The POC SHALL provide `openstock-verify` as the authoritative readiness check.

The command SHALL return non-zero when required checks fail.

#### Scenario: Verification passes on ready host

- **GIVEN** the data platform is deployed and running
- **WHEN** the operator runs `openstock-verify`
- **THEN** it SHALL check Docker availability
- **AND** Docker Compose availability
- **AND** data platform status when systemd is available
- **AND** `vnstock-service` health
- **AND** forbidden endpoint behavior
- **AND** warehouse path/schema
- **AND** `vnalpha --help`
- **AND** watchlist command behavior
- **AND** TUI import/entrypoint behavior
- **AND** print `[OK]` for required passed checks.

#### Scenario: Verification supports CI-safe mode

- **GIVEN** CI cannot access live provider data
- **WHEN** `openstock-verify --ci` runs
- **THEN** it SHALL avoid live provider calls
- **AND** still verify syntax, scripts, local command availability, schema initialization, and safety checks where feasible.

#### Scenario: Optional assistant config is absent

- **GIVEN** LLM endpoint or API key is not configured
- **WHEN** `openstock-verify` runs
- **THEN** assistant verification SHALL be skipped or marked `[WARN]`
- **AND** required verification SHALL NOT fail solely because optional LLM config is absent.

---

### Requirement: R2 shall provide backup and rollback controls

The POC SHALL provide a warehouse backup command and documented rollback procedures.

#### Scenario: Backup creates timestamped copy

- **GIVEN** a DuckDB warehouse exists
- **WHEN** `openstock-backup-warehouse` runs
- **THEN** a timestamped backup SHALL be created under `/var/lib/openstock/warehouse/backups`
- **AND** the script SHALL print the backup path.

#### Scenario: Backup avoids concurrent writer risk

- **GIVEN** a writer lock exists
- **WHEN** `openstock-backup-warehouse` runs without explicit force
- **THEN** it SHALL refuse unsafe backup or exit non-zero with a warning
- **AND** it SHALL NOT create a misleading unsafe backup.

#### Scenario: Restore requires verification

- **GIVEN** an operator restores a warehouse backup
- **WHEN** restore completes
- **THEN** the runbook SHALL require `openstock-verify`
- **AND** the system SHALL pass required verification before demo use.

---

### Requirement: R3 terminal workspace shall provide one primary analyst entrypoint

`vnalpha tui` SHALL be the primary terminal workspace for the POC.

The TUI SHALL provide watchlist, detail, quality, rejected data, outcomes/calibration, command/help, and persistent chat surfaces.

#### Scenario: TUI opens watchlist workspace

- **GIVEN** a configured warehouse
- **WHEN** the user runs `vnalpha tui --date <demo-date>`
- **THEN** the TUI SHALL open successfully
- **AND** expose the watchlist workspace or a clear empty-state if no watchlist exists.

#### Scenario: User can inspect symbol detail

- **GIVEN** a watchlist row exists
- **WHEN** the user selects or opens a symbol
- **THEN** the detail screen SHALL show score breakdown, evidence, risk flags, lineage, and quality status.

#### Scenario: TUI handles empty data states

- **GIVEN** the warehouse is empty or missing specific artifacts
- **WHEN** the user opens watchlist, detail, quality, rejected, or outcomes screens
- **THEN** the TUI SHALL show explicit empty-state messages
- **AND** SHALL NOT crash.

---

### Requirement: R3 TUI navigation and smoke tests shall be reliable

The TUI SHALL include keyboard navigation and CI-safe construction tests.

#### Scenario: Major screens are importable and constructible

- **GIVEN** test dependencies are installed
- **WHEN** TUI smoke tests run
- **THEN** app construction, major screen imports, and major navigation actions SHALL pass without launching an uncontrolled interactive session.

#### Scenario: TUI remains terminal-native

- **GIVEN** a user accesses the host via terminal, SSH, or tmux
- **WHEN** they run `vnalpha tui`
- **THEN** the TUI SHALL run as a host-native terminal app
- **AND** SHALL NOT require browser, web dashboard, or Docker interactive execution.

---

### Requirement: R4 ChatPanel shall persist transcript and context

The persistent ChatPanel SHALL create or resume a `chat_session` and persist user turns, assistant turns, command turns, plans, and trace links.

#### Scenario: User and assistant turns are persisted

- **GIVEN** a TUI chat session is active
- **WHEN** the user asks a research question and the assistant responds
- **THEN** the user prompt SHALL be persisted as `chat_message`
- **AND** the assistant response or refusal SHALL be persisted as `chat_message`
- **AND** assistant execution SHALL be linked to `assistant_session` where applicable.

#### Scenario: Slash command turn is persisted

- **GIVEN** a TUI chat session is active
- **WHEN** the user runs a slash command from ChatPanel
- **THEN** the command input and result SHALL be persisted or linked through `research_session`
- **AND** traceable tool execution metadata SHALL be retained where applicable.

#### Scenario: Context command shows deterministic state

- **GIVEN** the user has interacted with watchlist, detail, or commands
- **WHEN** the user runs `/context`
- **THEN** ChatPanel SHALL show deterministic context such as target date, selected symbol, last command, last compared symbols, last plan, and recent traces.

---

### Requirement: R4 ChatPanel shall use unified command execution

ChatPanel SHALL not maintain a separate command path that bypasses shared parsing, permission, tracing, or persistence.

#### Scenario: ChatPanel slash command uses shared executor

- **GIVEN** the user enters `/explain FPT` in ChatPanel
- **WHEN** the command executes
- **THEN** it SHALL use the shared parser and command execution service
- **AND** it SHALL produce the same result semantics as CLI/TUI command execution
- **AND** it SHALL create traceable records.

#### Scenario: Unknown command fails closed

- **GIVEN** the user enters an unsupported slash command
- **WHEN** ChatPanel parses it
- **THEN** it SHALL return a clear unknown-command message
- **AND** SHALL NOT dispatch arbitrary tools or shell commands.

---

### Requirement: R4 ChatPanel shall support plan preview, approval, cancellation, and trace review

Pipeline or admin actions initiated from chat SHALL require explicit plan approval.

Read-only research actions MAY execute without approval.

#### Scenario: Pipeline action requires approval

- **GIVEN** the user requests a pipeline/write/admin action through chat
- **WHEN** the assistant builds an execution plan
- **THEN** ChatPanel SHALL render a plan preview
- **AND** execution SHALL NOT start until the user approves.

#### Scenario: User cancels pending plan

- **GIVEN** a pending plan exists
- **WHEN** the user cancels the plan or runs `/plan cancel` if implemented
- **THEN** the pending plan SHALL be marked cancelled
- **AND** no write/admin action SHALL execute.

#### Scenario: Trace command shows recent trace timeline

- **GIVEN** commands or assistant tool calls have run
- **WHEN** the user runs `/trace`
- **THEN** ChatPanel SHALL show recent tool events and statuses
- **AND** failed steps SHALL include actionable error summaries.

---

### Requirement: R4 ChatPanel shall enforce research-only hard-deny policy

ChatPanel and assistant workflows SHALL enforce hard-deny rules for trading, account access, portfolio mutation, margin, transfer, automated execution, arbitrary shell, raw SQL from prompt, trace hiding, safety bypass, and fabricated data.

#### Scenario: Trading request is refused

- **GIVEN** the user asks ChatPanel or assistant to place an order, buy, sell, trade, access an account, mutate a portfolio, use margin, or transfer funds
- **WHEN** policy checks run
- **THEN** the request SHALL be refused
- **AND** no tool or command SHALL execute the prohibited action.

#### Scenario: Shell or raw SQL request is refused

- **GIVEN** the user asks ChatPanel to run arbitrary shell commands or raw SQL from prompt
- **WHEN** policy checks run
- **THEN** the request SHALL be refused
- **AND** no arbitrary command execution SHALL occur.

#### Scenario: Trace hiding request is refused

- **GIVEN** the user asks to hide traces, bypass safety, or fabricate data
- **WHEN** policy checks run
- **THEN** the request SHALL be refused
- **AND** trace and audit behavior SHALL remain enabled.

---

### Requirement: R0-R4 completion shall be validated by tests and smoke checks

R0-R4 SHALL be marked complete only after required tests and smoke checks pass.

#### Scenario: Automated validation passes

- **GIVEN** the implementation is complete
- **WHEN** validation commands run
- **THEN** `make test-vnalpha` SHALL pass
- **AND** `docker compose config` SHALL pass
- **AND** `openstock-verify --ci` SHALL pass
- **AND** TUI and ChatPanel smoke tests SHALL pass.

#### Scenario: Manual deployment smoke passes

- **GIVEN** a fresh or clean host
- **WHEN** the operator follows the runbook
- **THEN** the data platform SHALL start
- **AND** package install SHALL expose `vnalpha`
- **AND** smoke pipeline SHALL produce usable artifacts or explicit no-data output
- **AND** `vnalpha tui` SHALL start
- **AND** `openstock-verify` SHALL pass required checks.

