## ADDED Requirements

### Requirement: Explicit data provisioning commands

OpenStock SHALL provide bounded CLI and TUI commands through which a user can
explicitly download raw data or build each supported derived data type.

#### Scenario: User downloads raw symbol data

- **WHEN** the user runs `vnalpha data download symbols`, `vnalpha data download ohlcv FPT`, or `vnalpha data download index VNINDEX`
- **THEN** the command SHALL invoke the existing deterministic ingestion service with validated dates and provider options
- **AND** SHALL render inserted/skipped counts, source, effective date range, warnings, and correlation ID.

#### Scenario: User builds derived research data

- **WHEN** the user runs `vnalpha data build canonical FPT`, `features FPT --date DATE`, `score FPT --date DATE`, `market-regime --date DATE`, or `sector-strength --date DATE`
- **THEN** the command SHALL invoke the matching existing deterministic builder
- **AND** SHALL render artifact status, effective as-of date, freshness, lineage, warnings, and manual follow-up where incomplete.

#### Scenario: User uses the TUI command surface

- **WHEN** the user enters the matching `/data download` or `/data build` command in the TUI
- **THEN** it SHALL use the same command service and validation as the CLI
- **AND** SHALL display the deterministic result in the output stream.

#### Scenario: User provides an invalid command

- **WHEN** a data command has an unsupported data type, invalid date, missing symbol, or conflicting argument
- **THEN** the command SHALL fail before provider or warehouse mutation
- **AND** SHALL display the accepted syntax and a non-zero CLI exit status where applicable.

### Requirement: Data provisioning command boundary

Explicit data commands SHALL preserve the research-only and bounded-tool policy.

#### Scenario: A data command runs

- **WHEN** any explicit data command executes
- **THEN** it SHALL only access approved vnstock ingestion and deterministic warehouse builders
- **AND** SHALL not expose SQL, shell, filesystem, broker, account, portfolio, or trading-execution capability
- **AND** SHALL emit correlated structured audit events.
