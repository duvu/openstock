# architecture-gap-refactor Specification

## Purpose
TBD - created by archiving change architecture-gap-refactor. Update Purpose after archive.
## Requirements
### Requirement: CLI shall be modular while preserving public entrypoint

The implementation SHALL split the current CLI into domain modules while keeping the existing `vnalpha` console script behavior.

#### Scenario: Public CLI entrypoint remains compatible

- **GIVEN** the package is installed
- **WHEN** `vnalpha` is invoked
- **THEN** it SHALL still resolve to a Typer app exposed by `vnalpha.cli:app` or a backward-compatible shim.

#### Scenario: Existing CLI commands remain registered

- **GIVEN** the CLI app is loaded
- **WHEN** commands are inspected
- **THEN** existing commands and groups for init, sync, build, score, watchlist, tui, and outcome SHALL remain available.

---

### Requirement: Tool and assistant policy shall have one source of truth

The implementation SHALL centralize tool permissions and assistant/tool allowlist policy.

#### Scenario: Every registered tool has policy

- **GIVEN** local tools are registered
- **WHEN** policy completeness tests run
- **THEN** every registered tool SHALL have one central policy entry.

#### Scenario: Assistant allowlist derives from policy

- **GIVEN** assistant planner and executor load their allowlists
- **WHEN** the allowlists are inspected
- **THEN** they SHALL derive from central policy rather than manually duplicating tool names.

#### Scenario: Mutating tools are marked explicitly

- **GIVEN** a tool mutates the warehouse
- **WHEN** its policy is inspected
- **THEN** `mutates_warehouse` SHALL be true or equivalent.

---

### Requirement: Assistant shall not autonomously call direct data fetch

The assistant SHALL NOT call `data.fetch` as an autonomous plan step.

#### Scenario: data.fetch is disallowed for autonomous assistant plan

- **GIVEN** central tool policy is loaded
- **WHEN** `data.fetch` policy is inspected
- **THEN** it SHALL be disallowed for assistant autonomous planning.

#### Scenario: Assistant executor rejects data.fetch

- **GIVEN** an assistant plan contains `data.fetch`
- **WHEN** executor validates the plan
- **THEN** execution SHALL be rejected.

#### Scenario: Analysis still auto-provisions data deterministically

- **GIVEN** `/explain SYMBOL` or assistant candidate analysis runs
- **WHEN** data is missing
- **THEN** deterministic data availability ensure logic SHALL remain the provisioning path.

---

### Requirement: TUI routing shall be split into focused components

The TUI router SHALL be refactored into smaller command, chat, status, lifecycle, and event components.

#### Scenario: Legacy router import remains valid

- **GIVEN** existing code imports `vnalpha.tui.input_router.TuiInputRouter`
- **WHEN** import runs
- **THEN** it SHALL still succeed.

#### Scenario: Command path is separated

- **GIVEN** a slash command is submitted
- **WHEN** route execution begins
- **THEN** command execution/rendering SHOULD be delegated to a command path component.

#### Scenario: Chat path is separated

- **GIVEN** natural-language input is submitted
- **WHEN** route execution begins
- **THEN** chat execution/rendering SHOULD be delegated to a chat path component.

#### Scenario: Status mapping is separated

- **GIVEN** route state changes
- **WHEN** status is updated
- **THEN** mapping from route/tool state to runtime status SHOULD live in a status adapter component.

---

### Requirement: Model routing boundary shall exist

The implementation SHALL add a model routing package and update LLM gateway contracts to accept routing metadata.

#### Scenario: Model routing package imports

- **GIVEN** the implementation is complete
- **WHEN** `vnalpha.model_routing` is imported
- **THEN** import SHALL succeed.

#### Scenario: Gateway accepts routing metadata

- **GIVEN** `LLMGatewayClient.chat` is called
- **WHEN** `stage`, `task_type`, `model_profile`, or `route_metadata` are provided
- **THEN** the method SHALL accept them without breaking existing calls.

#### Scenario: Existing model env remains supported

- **GIVEN** `VNALPHA_LLM_MODEL` is configured
- **WHEN** no explicit route profile is selected
- **THEN** gateway SHALL continue to use existing configured model behavior.

---

### Requirement: Workspace context boundary shall exist

The implementation SHALL add a workspace context package boundary for later lifecycle implementation.

#### Scenario: Workspace context package imports

- **GIVEN** the implementation is complete
- **WHEN** `vnalpha.workspace_context` is imported
- **THEN** import SHALL succeed.

#### Scenario: Workspace skeleton does not claim full lifecycle

- **GIVEN** workspace context package skeleton exists
- **WHEN** docs/tasks are reviewed
- **THEN** it SHALL NOT claim full compact/clean/new/resume lifecycle unless implemented and tested.

---

### Requirement: Data availability shall have service boundaries

Data availability SHALL be refactored toward check, plan, action, and service boundaries while preserving existing public API.

#### Scenario: ensure wrapper remains compatible

- **GIVEN** existing code imports `ensure_symbol_analysis_ready`
- **WHEN** import and call path are used
- **THEN** behavior SHALL remain backward-compatible.

#### Scenario: Planning can be tested separately

- **GIVEN** data availability checks return a known state
- **WHEN** plan generation runs
- **THEN** required actions SHOULD be derivable without executing sync/build/score side effects.

---

### Requirement: Command result semantics shall distinguish empty and partial outcomes

The implementation SHALL avoid reporting empty/no-data command outcomes as plain success.

#### Scenario: Explain with no score is not plain success

- **GIVEN** `/explain SYMBOL` finds no candidate score after provisioning
- **WHEN** command result is produced
- **THEN** status SHALL be `EMPTY_RESULT`, `PARTIAL`, or equivalent, not plain `SUCCESS`.

#### Scenario: Compare with no records is not plain success

- **GIVEN** `/compare A B` finds no candidate records
- **WHEN** command result is produced
- **THEN** status SHALL be `EMPTY_RESULT`, `PARTIAL`, or equivalent, not plain `SUCCESS`.

#### Scenario: Renderers handle all statuses

- **GIVEN** command result has SUCCESS, EMPTY_RESULT, PARTIAL, FAILED, or VALIDATION_ERROR
- **WHEN** textual renderer runs
- **THEN** it SHALL render a stable user-visible result.

---

### Requirement: Architecture docs and regression tests shall be added

The implementation SHALL document package boundaries and protect against known architecture regressions.

#### Scenario: Architecture docs exist

- **GIVEN** implementation is complete
- **WHEN** docs are inspected
- **THEN** architecture and package-boundary documentation SHALL exist.

#### Scenario: Policy regression tests exist

- **GIVEN** tests run
- **THEN** tests SHALL prove assistant/tool policy consistency and disallow autonomous `data.fetch`.

#### Scenario: TUI regression tests exist

- **GIVEN** tests run
- **THEN** tests SHALL prove default TUI still has one output, one composer, one input, and no dashboard regression.

#### Scenario: CLI compatibility tests exist

- **GIVEN** tests run
- **THEN** tests SHALL prove existing CLI commands remain registered.

