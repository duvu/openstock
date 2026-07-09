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
