# Specification: Deep Symbol Analysis Engine

## ADDED Requirements

### Requirement: Deep symbol analysis command

OpenStock SHALL provide a command that returns a consolidated deep analysis object for a symbol.

#### Scenario: User analyzes a symbol

- **WHEN** the user runs `/analyze FPT`
- **THEN** the system returns trend, momentum, relative strength, volume, volatility, setup quality, levels, scenario summary, caveats, missing data, lineage, and confidence

### Requirement: Explicit level map

Deep analysis SHALL include explicit support and resistance levels when sufficient data exists.

#### Scenario: Levels can be derived

- **WHEN** recent OHLCV supports level extraction
- **THEN** the output includes level values, level type, strength, and derivation metadata

### Requirement: Setup quality decomposition

Deep analysis SHALL decompose setup quality rather than only reusing composite candidate score.

#### Scenario: Setup analysis is created

- **WHEN** a symbol has feature and score data
- **THEN** setup quality includes component evidence and caveats

### Requirement: Research-only scenario summary

Scenario output SHALL be conditional and non-execution-oriented.

#### Scenario: Confirmation condition exists

- **WHEN** analysis includes a confirmation condition
- **THEN** it is framed as a monitoring condition, not an instruction to trade

### Requirement: Missing data disclosure

Deep analysis SHALL disclose missing or stale data.

#### Scenario: Sector context is unavailable

- **WHEN** sector strength data is missing
- **THEN** the output states the missing context and does not fabricate it

### Requirement: Deep analysis readiness gate

OpenStock SHALL deterministically establish the required persisted inputs before
executing deep symbol analysis and SHALL surface the resulting readiness state.

#### Scenario: Required market and sector context is absent

- **GIVEN** a deep analysis for `FPT` requests market-regime and sector-strength context
- **AND** either persisted snapshot is missing or stale for the resolved as-of date
- **WHEN** `/analyze FPT --with-regime --with-sector` or the equivalent assistant plan runs
- **THEN** deterministic application code SHALL build or refresh the missing supported snapshots before `analysis.deep_symbol` executes
- **AND** SHALL return per-artifact actions, freshness, lineage, and resolved as-of date

#### Scenario: Required readiness fails

- **GIVEN** a required deep-analysis artifact cannot be provisioned
- **WHEN** readiness completes
- **THEN** `analysis.deep_symbol` SHALL NOT execute against the incomplete required input set
- **AND** the result SHALL identify the failed artifact and an explicit manual remediation command

#### Scenario: Optional context remains unavailable

- **GIVEN** a deep analysis does not request optional context or it remains unavailable after a bounded attempt
- **WHEN** the analysis is returned
- **THEN** readiness SHALL mark the context `NOT_REQUESTED` or `PARTIAL`
- **AND** the analysis SHALL disclose it without presenting it as current

### Requirement: Deep readiness observability

OpenStock SHALL audit each deep-analysis readiness decision with structured,
correlated events.

#### Scenario: Deep readiness completes

- **WHEN** deep-analysis readiness reaches ready, partial, or failed status
- **THEN** the audit trail SHALL contain start, per-artifact decision/action, and terminal events with symbol, requested date, resolved as-of date, artifact type, and correlation ID
- **AND** the command or TUI SHALL render a Data Readiness panel from the deterministic result
