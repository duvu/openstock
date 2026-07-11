# Specification: R0-R4 Gap Closure to >90%

## ADDED Requirements

### Requirement: Completion evidence matrix shall gate R0-R4 closure

The repository SHALL include an evidence matrix that records phase completion estimates and links each estimate to code, tests, scripts, logs, or documentation.

#### Scenario: Matrix records evidence for every phase

- **GIVEN** R0-R4 are being evaluated for completion
- **WHEN** `vnalpha/docs/13-r0-r4-completion-matrix.md` is reviewed
- **THEN** it SHALL include rows for R0, R1, R2, R3, and R4
- **AND** each row SHALL include completion percentage, remaining blockers, implementation evidence, test evidence, runtime evidence, documentation evidence, and deferred work.

#### Scenario: Phase cannot exceed 90% with an open blocker

- **GIVEN** a phase still has a blocker marked open
- **WHEN** the completion matrix is updated
- **THEN** that phase SHALL NOT be recorded above 90%.

---

### Requirement: R0 verification shall prove deterministic pipeline confidence

The repository SHALL provide a repeatable R0 verification target that validates the deterministic pipeline through tests and, where feasible, CLI-level smoke checks.

#### Scenario: R0 verification target passes

- **GIVEN** development dependencies are installed
- **WHEN** `make verify-r0` runs
- **THEN** it SHALL run the offline pipeline E2E tests
- **AND** feature metadata regression tests
- **AND** migration upgrade tests
- **AND** CLI boundary tests
- **AND** return non-zero if any required R0 check fails.

#### Scenario: Feature status is explicit when benchmark is missing

- **GIVEN** symbol OHLCV exists but VNINDEX benchmark data does not exist
- **WHEN** feature snapshots are built
- **THEN** relative-strength fields SHALL not be presented as valid
- **AND** `feature_data_status` SHALL be `MISSING_BENCHMARK`.

#### Scenario: Feature status is stale when latest bar is older than target date

- **GIVEN** symbol OHLCV exists up to a date earlier than the requested target date
- **WHEN** feature snapshots are built
- **THEN** `as_of_bar_date` SHALL record the actual bar date used
- **AND** `feature_data_status` SHALL be `STALE_DATE`.

#### Scenario: Feature status is exact when target bar exists

- **GIVEN** symbol OHLCV includes a bar for the requested target date
- **AND** benchmark data is available
- **WHEN** feature snapshots are built
- **THEN** `as_of_bar_date` SHALL equal the target date
- **AND** `feature_data_status` SHALL be `EXACT_DATE`.

#### Scenario: Existing warehouse upgrades safely

- **GIVEN** an older DuckDB warehouse missing newer metadata columns or R4/R6 tables
- **WHEN** migrations run
- **THEN** missing columns/tables SHALL be added idempotently
- **AND** existing market, canonical, feature, score, watchlist, note, assistant, outcome, and chat data SHALL not be dropped.

---

### Requirement: R1 documentation shall match executable behavior

Architecture and runbook documentation SHALL match actual repository paths, commands, scripts, service units, config paths, and validation gates.

#### Scenario: Operator can map docs to repo files

- **GIVEN** the operator reads the deployment architecture and runbook
- **WHEN** they follow file references and commands
- **THEN** every referenced script, service, package path, Makefile target, and config path SHALL either exist or be explicitly marked as planned/deferred.

#### Scenario: R5+ work is not mixed into R0-R4 completion

- **GIVEN** the documentation describes future local runtime/server behavior
- **WHEN** R0-R4 completion is evaluated
- **THEN** R5+ behavior SHALL be clearly marked deferred
- **AND** SHALL NOT be required for R0-R4 >90% completion.

---

### Requirement: R2 pipeline runner shall execute the correct full pipeline under one lock

The deployed daily pipeline SHALL be executed through a wrapper that holds a writer lock for the entire multi-step pipeline.

#### Scenario: Pipeline wrapper runs commands in correct order

- **GIVEN** `openstock-run-pipeline` is invoked
- **WHEN** it runs the default daily pipeline
- **THEN** it SHALL run symbols sync
- **AND** equity OHLCV sync for VN30
- **AND** benchmark sync using `sync index --symbol VNINDEX`
- **AND** canonical build
- **AND** feature build
- **AND** scoring
- **AND** watchlist display or verification.

#### Scenario: Writer lock spans full pipeline

- **GIVEN** one pipeline run has acquired the pipeline lock
- **WHEN** a second pipeline run starts
- **THEN** the second run SHALL fail fast or wait according to documented behavior
- **AND** SHALL NOT overlap writes to the same warehouse.

#### Scenario: systemd pipeline calls wrapper once

- **GIVEN** `openstock-daily-pipeline.service` is installed
- **WHEN** the service starts
- **THEN** it SHALL call the pipeline wrapper once
- **AND** SHALL NOT split the pipeline across multiple independent `ExecStart=` commands.

---

### Requirement: R2 verification shall include CI-safe static deployment checks

`openstock-verify --ci` SHALL perform meaningful static checks without requiring live market data or a running provider service.

#### Scenario: CI verification checks deploy scripts and compose config

- **GIVEN** Docker or shell tooling is available in CI
- **WHEN** `openstock-verify --ci` runs
- **THEN** it SHALL validate shell script syntax
- **AND** validate Docker Compose configuration when Docker Compose is available
- **AND** statically check localhost-only service binding
- **AND** statically check `vnalpha-worker` profile gating
- **AND** statically check warehouse mount/env configuration.

#### Scenario: CI verification checks package and service inventory

- **GIVEN** package and systemd files are present
- **WHEN** `openstock-verify --ci` runs
- **THEN** it SHALL verify package metadata or package source paths exist
- **AND** verify launchers are defined or installed
- **AND** verify systemd units are parseable when `systemd-analyze` is available
- **AND** verify no background TUI service is configured.

#### Scenario: Live verification remains stricter

- **GIVEN** the system is deployed on a host
- **WHEN** `openstock-verify` runs without `--ci`
- **THEN** it SHALL check running service health
- **AND** check restricted HTTP paths return not found
- **AND** check warehouse path/schema
- **AND** check host `vnalpha` availability
- **AND** check TUI entrypoint/import behavior
- **AND** return non-zero for required failures.

---

### Requirement: R2 package proof shall be explicit

The repository SHALL provide commands or documented steps to build and verify the host-native `vnalpha` package.

#### Scenario: Package build is verifiable

- **GIVEN** packaging dependencies are installed
- **WHEN** `make build-vnalpha-deb` runs
- **THEN** a package artifact SHALL be produced
- **OR** the task SHALL fail with actionable output.

#### Scenario: Package install surface is verified

- **GIVEN** a built or installed package
- **WHEN** `make verify-vnalpha-deb` runs
- **THEN** it SHALL verify launcher availability for `vnalpha`
- **AND** launcher availability for `vnalpha-poc`
- **AND** env template availability
- **AND** `vnalpha --help` behavior where supported.

---

### Requirement: R3 TUI pilot tests shall prove workspace behavior

The TUI SHALL have integration-level evidence that the terminal workspace mounts, switches screens, and keeps ChatPanel persistent.

#### Scenario: App mounts and screens switch

- **GIVEN** Textual test support is available
- **WHEN** TUI pilot tests run
- **THEN** the app SHALL mount
- **AND** home screen SHALL be initial
- **AND** actions SHALL switch to watchlist, commands, assistant, rejected, quality, and outcomes screens.

#### Scenario: ChatPanel persists across navigation

- **GIVEN** the TUI app is mounted
- **WHEN** the user switches among main workspace screens
- **THEN** ChatPanel SHALL remain mounted
- **AND** chat input SHALL remain focusable.

#### Scenario: Empty warehouse does not crash TUI

- **GIVEN** an empty or freshly initialized warehouse
- **WHEN** watchlist, detail, quality, rejected, outcomes, and chat surfaces are opened
- **THEN** each surface SHALL show an explicit empty/unavailable state
- **AND** SHALL NOT crash.

---

### Requirement: R4 ChatPanel shall delegate orchestration to ChatController

ChatPanel SHALL be a Textual view adapter. ChatController SHALL own command routing, natural-language handling, local chat commands, plan state, trace handling, and persistence.

#### Scenario: User input goes through ChatController

- **GIVEN** ChatPanel is mounted
- **WHEN** the user submits any input
- **THEN** ChatPanel SHALL call `ChatController.handle_turn(raw)`
- **AND** SHALL NOT call a ChatPanel-local command registry or assistant runner.

#### Scenario: Plan actions go through ChatController

- **GIVEN** a pending plan exists
- **WHEN** the user approves or cancels from the app or ChatPanel
- **THEN** the action SHALL call `ChatController.approve_pending_plan()` or `ChatController.cancel_pending_plan()`
- **AND** the pending plan state SHALL be owned by ChatController.

#### Scenario: Legacy ChatPanel dispatch paths are not used

- **GIVEN** ChatPanel code is reviewed
- **WHEN** command or assistant dispatch is inspected
- **THEN** ChatPanel SHALL NOT own a separate parser, registry dispatch, or assistant construction path for production input handling.

---

### Requirement: R4 chat transcript shall be audit-preserving

Every chat turn SHALL be persisted in `chat_message` when a chat session is active.

#### Scenario: Natural-language turn is persisted

- **GIVEN** an active chat session
- **WHEN** the user asks a question and the assistant responds or refuses
- **THEN** the user prompt SHALL be persisted
- **AND** the assistant response or refusal SHALL be persisted
- **AND** assistant session linkage SHALL be stored where available.

#### Scenario: Slash command turn is persisted

- **GIVEN** an active chat session
- **WHEN** the user runs a slash command through ChatPanel
- **THEN** the command input SHALL be persisted
- **AND** the command result SHALL be persisted
- **AND** research session linkage SHALL be stored where available.

#### Scenario: Local chat command turn is persisted

- **GIVEN** an active chat session
- **WHEN** the user runs `/new`, `/clear`, `/context`, `/plan`, `/trace`, or `/help`
- **THEN** the input and output SHALL be persisted except where `/new` intentionally starts a new session.

#### Scenario: Clear preserves transcript by default

- **GIVEN** a chat session has persisted messages
- **WHEN** the user runs `/clear`
- **THEN** the visible UI log MAY be cleared
- **BUT** persisted transcript rows SHALL remain available for audit.

#### Scenario: Destructive clear requires explicit flag

- **GIVEN** a chat session has persisted messages
- **WHEN** the user runs a destructive clear command
- **THEN** the command SHALL require an explicit destructive flag
- **AND** the help text SHALL clearly distinguish it from normal `/clear`.

---

### Requirement: R4 planned tool permissions shall be evaluated before pending storage

ChatController SHALL evaluate every planned tool before auto-run, pending-plan storage, or approval.

#### Scenario: Safe read-only plan can auto-run

- **GIVEN** execution mode is auto safe-read
- **AND** every planned tool is safe read-only
- **WHEN** the user asks a supported research question
- **THEN** the plan MAY run immediately
- **AND** trace/persistence SHALL still occur.

#### Scenario: Approval-required plan becomes pending only when allowed

- **GIVEN** a planned tool requires explicit approval and is not permanently restricted
- **WHEN** execution mode supports approval
- **THEN** the plan MAY be stored as pending
- **AND** the preview SHALL be persisted.

#### Scenario: Restricted planned tool is refused before pending

- **GIVEN** a planned tool is classified as permanently restricted
- **WHEN** ChatController evaluates the plan
- **THEN** the plan SHALL be refused
- **AND** SHALL NOT be stored as pending
- **AND** SHALL NOT be approvable.

---

### Requirement: R4 trace timeline shall be persisted and queryable

Trace events emitted during chat-driven tool use SHALL be persisted and queryable from the current chat session.

#### Scenario: Trace event persists during tool run

- **GIVEN** an active chat session
- **WHEN** a traced tool starts, succeeds, or fails
- **THEN** a trace message SHALL be persisted with tool name, status, duration when available, and trace id when available.

#### Scenario: `/trace` reads persisted trace events

- **GIVEN** persisted trace events exist for a chat session
- **WHEN** the user runs `/trace`
- **THEN** ChatController SHALL return those events in chronological order.

#### Scenario: `/trace` handles no events

- **GIVEN** no trace events exist for a chat session
- **WHEN** the user runs `/trace`
- **THEN** ChatController SHALL return a useful no-events message.

---

### Requirement: Final validation shall prove R0-R4 above 90%

The change SHALL include final validation evidence before R0-R4 are marked above 90%.

#### Scenario: Validation report records commands

- **GIVEN** implementation is complete
- **WHEN** `vnalpha/docs/14-r0-r4-validation-report.md` is reviewed
- **THEN** it SHALL include command output summaries for test, lint, R0 verify, R2 CI verify, compose config, deploy verify, package verify, TUI smoke, and chat smoke
- **AND** any command not run SHALL be marked `NOT RUN` with reason.

#### Scenario: Completion matrix shows all phases above 90%

- **GIVEN** validation evidence is complete
- **WHEN** the completion matrix is updated
- **THEN** R0, R1, R2, R3, and R4 SHALL each be recorded at 90% or higher
- **AND** no phase SHALL have an unresolved blocker.
