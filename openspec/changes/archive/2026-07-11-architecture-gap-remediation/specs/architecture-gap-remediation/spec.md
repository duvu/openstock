# Specification: Architecture gap remediation

## ADDED Requirements

### Requirement: CLI shall be split into modular command files

The CLI SHALL be reorganized so the root entrypoint remains compatible while command groups live in dedicated modules.

#### Scenario: Console script compatibility remains

- **GIVEN** the project script points to `vnalpha.cli:app`
- **WHEN** `from vnalpha.cli import app` is executed
- **THEN** the Typer root app SHALL import successfully.

#### Scenario: CLI modules exist

- **GIVEN** the remediation is implemented
- **WHEN** package files are inspected
- **THEN** `vnalpha/cli/app.py`, `common.py`, `sync.py`, `build.py`, `score.py`, `watchlist.py`, `tui.py`, and `outcome.py` SHALL exist.

#### Scenario: Existing command names remain available

- **GIVEN** the CLI app is loaded
- **WHEN** registered commands are inspected or invoked in tests
- **THEN** existing commands such as `sync`, `build`, `score`, `watchlist`, `tui`, and `outcome` SHALL remain available.

---

### Requirement: Tool and assistant policy shall have a single source of truth

The system SHALL centralize tool permissions, assistant allowlists, and mutating-tool metadata.

#### Scenario: Policy package exists

- **GIVEN** the remediation is implemented
- **WHEN** package files are inspected
- **THEN** `vnalpha/policy/` SHALL exist with permissions, tool policy, assistant policy, command policy, and safety policy modules.

#### Scenario: Planner and executor use same assistant allowlist

- **GIVEN** assistant planner and executor validate tool access
- **WHEN** their allowlists are resolved
- **THEN** both SHALL come from the central assistant policy source.

#### Scenario: Tool registry permissions come from policy

- **GIVEN** local tool registry is built
- **WHEN** tool permissions are inspected
- **THEN** permissions SHALL match the central tool policy entries.

---

### Requirement: Assistant shall not autonomously call data.fetch

The assistant SHALL NOT plan or execute `data.fetch` as an autonomous tool step.

#### Scenario: Assistant allowlist excludes data.fetch

- **GIVEN** the assistant tool allowlist is resolved
- **WHEN** it is inspected
- **THEN** `data.fetch` SHALL NOT be present.

#### Scenario: Planner cannot build fetch_data autonomous plan

- **GIVEN** the intent result maps to `fetch_data`
- **WHEN** planner builds a plan
- **THEN** it SHALL refuse or suggest an explicit manual command instead of emitting a `data.fetch` step.

#### Scenario: Executor rejects data.fetch assistant step

- **GIVEN** an assistant plan includes a `data.fetch` step
- **WHEN** executor validates the step
- **THEN** execution SHALL be rejected by assistant policy.

---

### Requirement: TUI routing shall be split into smaller components

TUI routing SHALL be decomposed into route decision, command path, chat path, status adapter, lifecycle hooks, and events modules.

#### Scenario: Routing modules exist

- **GIVEN** the remediation is implemented
- **WHEN** package files are inspected
- **THEN** `vnalpha/tui/routing/router.py`, `command_path.py`, `chat_path.py`, `status_adapter.py`, `lifecycle_hooks.py`, and `events.py` SHALL exist.

#### Scenario: Existing TuiInputRouter import remains compatible

- **GIVEN** existing code imports `vnalpha.tui.input_router.TuiInputRouter`
- **WHEN** import is executed
- **THEN** it SHALL still succeed.

#### Scenario: Router delegates command execution

- **GIVEN** user submits a slash command
- **WHEN** TUI routes the input
- **THEN** command execution SHALL be handled by the command path component, not embedded directly in the top-level router.

#### Scenario: Router delegates chat execution

- **GIVEN** user submits natural-language text
- **WHEN** TUI routes the input
- **THEN** chat execution SHALL be handled by the chat path component, not embedded directly in the top-level router.

---

### Requirement: Command results shall support EMPTY and PARTIAL semantics

Command result status semantics SHALL distinguish successful output, partial output, empty valid results, runtime failure, and validation error.

#### Scenario: Status values include EMPTY and PARTIAL

- **GIVEN** command result status values are inspected
- **THEN** `EMPTY` and `PARTIAL` SHALL be supported or equivalent semantics SHALL be documented and tested.

#### Scenario: Explain no-score is not plain success

- **GIVEN** `/explain SYMBOL` runs for a valid symbol/date with no candidate score after provisioning
- **WHEN** command result is returned
- **THEN** status SHALL be `EMPTY` or `PARTIAL`, not plain `SUCCESS`.

#### Scenario: Compare no-score is empty

- **GIVEN** `/compare SYMBOL1 SYMBOL2` finds no candidate scores
- **WHEN** command result is returned
- **THEN** status SHALL be `EMPTY`.

#### Scenario: Renderer supports empty result

- **GIVEN** a command returns `EMPTY`
- **WHEN** textual/rich renderer renders it
- **THEN** output SHALL be clear and non-error.

---

### Requirement: data_availability shall expose service/planner/action boundaries

The data availability subsystem SHALL keep the public ensure API compatible while separating checks, planning, actions, execution, and result assembly.

#### Scenario: Public ensure API remains compatible

- **GIVEN** callers import `ensure_symbol_analysis_ready`
- **WHEN** they call it with `conn`, `symbol`, and `target_date`
- **THEN** it SHALL return an `EnsureDataResult` compatible with existing callers.

#### Scenario: Planner exists

- **GIVEN** data availability package is inspected
- **THEN** a planner module SHALL exist to determine required actions from current state.

#### Scenario: Actions and executor exist

- **GIVEN** data availability package is inspected
- **THEN** actions and executor modules SHALL exist to execute planned provisioning actions.

#### Scenario: Ensure result remains panel-compatible

- **GIVEN** `EnsureDataResult` is returned
- **WHEN** `to_panel_dict()` is called
- **THEN** existing Data Readiness panel rendering SHALL remain compatible.

#### Scenario: Ensure result contains richer diagnostics

- **GIVEN** provisioning runs
- **WHEN** result is inspected
- **THEN** it SHOULD include richer diagnostics such as benchmark bars, freshness, lineage, provider, or action duration where available.

---

### Requirement: model_routing and workspace_context package boundaries shall exist

The codebase SHALL reserve clean package boundaries for upcoming model routing and workspace context features.

#### Scenario: model_routing package exists

- **GIVEN** package files are inspected
- **THEN** `vnalpha/model_routing/__init__.py` SHALL exist.

#### Scenario: workspace_context package exists

- **GIVEN** package files are inspected
- **THEN** `vnalpha/workspace_context/__init__.py` SHALL exist.

#### Scenario: TUI router does not embed workspace lifecycle implementation

- **GIVEN** workspace context package exists
- **WHEN** TUI routing code is inspected or tested
- **THEN** workspace lifecycle integration SHALL go through lifecycle hooks or adapters, not scattered direct implementation inside the router.

---

### Requirement: Architecture boundary tests shall exist

The implementation SHALL add tests that enforce package and policy boundaries.

#### Scenario: Boundary test file exists

- **GIVEN** tests are inspected
- **THEN** `tests/test_architecture_boundaries.py` or equivalent SHALL exist.

#### Scenario: Assistant policy test excludes data.fetch

- **GIVEN** architecture tests run
- **THEN** they SHALL prove assistant policy excludes `data.fetch`.

#### Scenario: Policy and registry alignment test passes

- **GIVEN** architecture tests run
- **THEN** they SHALL prove local tool registry entries align with central policy entries.

#### Scenario: CLI compatibility test passes

- **GIVEN** architecture tests run
- **THEN** they SHALL prove `from vnalpha.cli import app` works after CLI split.

---

### Requirement: TUI layout constraints shall remain valid

The remediation SHALL preserve the current TUI consistency constraints.

#### Scenario: One composer input remains

- **GIVEN** the TUI is mounted in tests
- **WHEN** Textual Input widgets are counted
- **THEN** exactly one Textual Input SHALL exist.

#### Scenario: One output stream remains

- **GIVEN** the TUI is mounted in tests
- **WHEN** output widgets are inspected
- **THEN** exactly one primary OutputStream SHALL exist.

#### Scenario: No dashboard regression

- **GIVEN** the default TUI is mounted
- **THEN** no ContentSwitcher or secondary ChatPanel SHALL be mounted in the default workflow.

---

### Requirement: Architecture documentation shall be updated

The repository SHALL document the post-remediation package boundaries and dependency rules.

#### Scenario: Architecture docs exist

- **GIVEN** the remediation is implemented
- **WHEN** docs are inspected
- **THEN** `vnalpha/docs/architecture.md` and `vnalpha/docs/package-boundaries.md` SHALL exist.

#### Scenario: Docs explain policy source of truth

- **GIVEN** package-boundary docs are reviewed
- **THEN** they SHALL explain that command/tool/assistant permissions are centralized in policy modules.

#### Scenario: Docs explain assistant data mutation boundary

- **GIVEN** docs are reviewed
- **THEN** they SHALL state that assistant autonomous plans cannot call `data.fetch`; data readiness is handled deterministically.

---

### Requirement: Validation commands shall pass

The implementation SHALL include validation evidence.

#### Scenario: Test and lint commands pass

- **GIVEN** implementation is complete
- **WHEN** validation is run
- **THEN** `make test-vnalpha`, `make lint-vnalpha`, `make verify-r4`, and `openstock-verify --ci` SHOULD pass or any exception SHALL be explicitly documented.
