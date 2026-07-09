# Specification: Research Intelligence Data Model Foundation

## ADDED Requirements

### Requirement: Shared research-intelligence object model

OpenStock SHALL define shared object contracts for the research-intelligence layer.

#### Scenario: Required objects are defined

- **WHEN** implementation begins for research intelligence engines
- **THEN** shared contracts exist for market regime, sector strength, symbol levels, setup analysis, shortlist candidates, scenario plans, setup evidence, and answer audits

### Requirement: Research-only schema boundary

The schema SHALL remain inside the no-trading-execution boundary.

#### Scenario: Execution fields are attempted

- **WHEN** a model adds broker, order, account, portfolio, margin, transfer, allocation, or trading execution fields
- **THEN** validation or review SHALL reject the change

### Requirement: Lineage and quality fields

All persisted research-intelligence objects SHALL include lineage and quality metadata where applicable.

#### Scenario: Engine writes a setup analysis

- **WHEN** a setup analysis record is persisted
- **THEN** it includes symbol, as-of date, methodology version, lineage, quality status, confidence, caveats, and correlation ID

### Requirement: Reusable repository APIs

OpenStock SHALL expose repository APIs for future commands, assistant tools, TUI rendering, and evaluation.

#### Scenario: Deep analysis needs symbol levels

- **WHEN** deep analysis is generated
- **THEN** it can query symbol level snapshots through a bounded repository function rather than raw SQL in assistant code

### Requirement: Additive migrations

Warehouse changes SHALL be additive and idempotent.

#### Scenario: Migration runs twice

- **WHEN** research-intelligence migrations are executed repeatedly
- **THEN** the warehouse remains valid and existing commands continue to work

### Requirement: Research answer audit

Assistant outputs for research-intelligence workflows SHALL be auditable.

#### Scenario: Assistant returns a deep research answer

- **WHEN** the answer is synthesized
- **THEN** the system records intent, tool usage, artifact refs, dataset freshness, groundedness result, policy result, missing data, caveats, and correlation ID
