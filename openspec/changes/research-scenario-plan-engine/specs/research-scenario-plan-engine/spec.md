# Specification: Research Scenario Plan Engine

## ADDED Requirements

### Requirement: Research scenario plan command

OpenStock SHALL provide a research-only scenario planning command.

#### Scenario: User requests a research plan

- **WHEN** the user runs `/research-plan FPT`
- **THEN** the system returns current setup, key levels, confirmation conditions, invalidation conditions, scenario tree, checklist, confidence, and caveats

### Requirement: Scenario tree

Scenario plans SHALL include multiple conditional branches.

#### Scenario: Plan is generated

- **WHEN** enough data exists
- **THEN** the plan includes base case, confirmation case, failed confirmation case, and low-quality drift case

### Requirement: Policy wording validation

Scenario plans SHALL pass research-only wording validation.

#### Scenario: Plan contains execution wording

- **WHEN** output includes buy, sell, order, enter, exit, allocate, broker, account, portfolio, or margin wording as instruction
- **THEN** validation fails before rendering

### Requirement: Caveated level-based estimate

Risk/reward estimates, if present, SHALL be rough research context only.

#### Scenario: Estimate is included

- **WHEN** a rough level-based estimate is returned
- **THEN** output states that it is not an execution instruction and depends on future confirmation
