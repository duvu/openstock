# Capability: chat data provisioning contract

## ADDED Requirements

### Requirement: One shared current-symbol provisioning operation

Natural-language chat and slash commands SHALL provision bounded current-symbol
analysis inputs through one typed application operation,
`ensure_current_symbol_ready`, which delegates to the existing fail-closed
readiness and data-availability services. No duplicate provisioning logic SHALL
exist in TUI or controller code.

#### Scenario: Empty warehouse analysis provisions before analysis
- **GIVEN** an empty warehouse
- **WHEN** a user asks `Phân tích FPT`
- **THEN** the plan contains an explicit `data.ensure_current_symbol` step before
  the analysis step, and provisioning runs before analysis succeeds.

#### Scenario: Slash and natural language share the operation
- **WHEN** `/analyze FPT` and the equivalent natural-language request run
- **THEN** both call `ensure_current_symbol_ready` and produce equivalent
  persisted evidence.

### Requirement: Fresh data reuse and bounded refresh

Fresh persisted data SHALL be reused without unnecessary provider requests. An
explicit refresh SHALL perform bounded incremental work and disclose each action.

#### Scenario: Fresh reuse
- **GIVEN** fresh persisted data satisfying the freshness policy
- **WHEN** the operation runs without refresh
- **THEN** the outcome is `REUSED` and no provider download is required.

#### Scenario: Explicit refresh
- **GIVEN** an explicit refresh intent
- **WHEN** the operation runs with `refresh=True`
- **THEN** it performs bounded incremental provisioning and reports the actions
  taken (`sync_ohlcv`, `build_canonical`, `build_features`, `score_symbol`).

### Requirement: Explicit, correlated, fail-closed trace

Every provisioning action SHALL appear in the tool/audit trace under one
correlation chain. A failed or partial provisioning turn SHALL NOT promote
incomplete analysis or corrupt existing valid data.

#### Scenario: Provisioning appears on trace
- **WHEN** the assistant executes a provisioning step
- **THEN** a `tool_trace` row is recorded for `data.ensure_current_symbol`.

#### Scenario: Fail-closed on non-ready provisioning
- **GIVEN** provisioning that does not reach a ready state
- **WHEN** the plan also contains an analysis step
- **THEN** the analysis step does not execute and a typed remediation error is
  returned.

### Requirement: Read-only research boundary preserved

The operation SHALL remain bounded to the current symbol and its benchmark. It
SHALL NOT perform arbitrary or unrestricted data fetching, and the unrestricted
`data.fetch` tool SHALL remain command-only and never eligible for autonomous
assistant plans.

#### Scenario: Unrestricted fetch stays non-autonomous
- **WHEN** eligibility is evaluated
- **THEN** `data.ensure_current_symbol` is assistant- and autonomous-eligible
  while `data.fetch` is not.
