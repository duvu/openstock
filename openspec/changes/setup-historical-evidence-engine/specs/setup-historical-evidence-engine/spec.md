# Specification: Setup Historical Evidence Engine

## ADDED Requirements

### Requirement: Setup evidence command

OpenStock SHALL expose setup-specific historical evidence through a command.

#### Scenario: User requests setup evidence

- **WHEN** the user runs `/setup-evidence ACCUMULATION_BASE --horizon 10`
- **THEN** the system returns sample definition, sample size, forward return distribution, FAE/AAE stats, outcome rate, caveats, and lineage

### Requirement: Historical evidence caveats

Evidence outputs SHALL disclose limitations.

#### Scenario: Sample size is small

- **WHEN** sample size is below the configured threshold
- **THEN** the output includes a small-sample caveat

### Requirement: Regime split

Evidence SHALL support regime split when regime data exists.

#### Scenario: Regime snapshots are available

- **WHEN** setup evidence is calculated
- **THEN** output includes outcome differences by regime bucket where sample size permits

### Requirement: No predictive certainty

Historical evidence SHALL not be presented as a guaranteed forecast.

#### Scenario: A setup has positive historical outcomes

- **WHEN** the assistant summarizes evidence
- **THEN** it states historical evidence only and avoids certainty or execution wording
