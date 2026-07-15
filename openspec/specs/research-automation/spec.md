# research-automation Specification

## Purpose
TBD - created by archiving change prod-c-research-automation. Update Purpose after archive.
## Requirements
### Requirement: System shall model research automation artifacts

The system SHALL represent experiments, features, hypotheses, pattern scans, offline event studies, and outputs as reproducible research artifacts.

#### Scenario: Research experiment is created

- **WHEN** the user creates an indicator experiment
- **THEN** the system persists the experiment definition
- **AND** stores input dataset references
- **AND** links generated code or deterministic tool references
- **AND** assigns lineage, quality status, and correlation ID

### Requirement: Composer shall expose research automation commands

The default composer path SHALL support research automation commands.

#### Scenario: Indicator experiment is requested

- **WHEN** the user submits `/experiment indicator <description>`
- **THEN** the system creates a research experiment plan
- **AND** runs the calculation through sandbox or approved deterministic tools
- **AND** persists validated artifacts
- **AND** renders a summary inline

#### Scenario: Offline event study is requested

- **WHEN** the user submits `/experiment event-study <allowlisted-condition>`
- **THEN** the system treats the request as an offline research event study
- **AND** does not connect to broker, account, portfolio, margin, or trading execution systems
- **AND** renders metrics with caveats

#### Scenario: Feature is created

- **WHEN** the user submits `/feature create <definition>`
- **THEN** the system persists the feature definition
- **AND** records dataset references and calculation lineage

#### Scenario: Feature is validated

- **WHEN** the user submits `/feature validate <feature-id-or-name>`
- **THEN** the system validates output schema, symbol coverage, date coverage, and data quality
- **AND** renders validation status inline

#### Scenario: Hypothesis is tested

- **WHEN** the user submits `/hypothesis test <hypothesis-text>`
- **THEN** the system creates a structured hypothesis test artifact
- **AND** includes sample construction, period coverage, metrics, and caveats

#### Scenario: Pattern is scanned

- **WHEN** the user submits `/pattern scan <pattern-description>`
- **THEN** the system scans approved historical research data
- **AND** persists candidate artifacts with quality and lineage metadata

### Requirement: Assistant shall plan research automation deterministically

Natural-language research automation requests SHALL produce structured plans that use approved research tools and/or sandbox jobs.

#### Scenario: Natural-language request needs generated compute

- **WHEN** the user asks for a new indicator, pattern, feature, hypothesis, or event-study calculation
- **THEN** the assistant builds a plan with dataset resolution, computation, validation, artifact persistence, and synthesis steps
- **AND** requests approval before generated code execution

### Requirement: Research outputs shall include caveats

Research automation answers SHALL present evidence with caveats rather than trading recommendations.

#### Scenario: Research metrics are rendered

- **WHEN** a research automation result is summarized
- **THEN** the answer includes sample size
- **AND** includes period coverage
- **AND** includes data quality caveats
- **AND** includes lookahead/survivorship bias caveats where relevant
- **AND** avoids personalized buy/sell recommendations

### Requirement: Offline event studies shall not imply live execution

Backtest-like functionality SHALL be constrained to offline research event studies.

#### Scenario: User asks to deploy or execute an event-study result as trades

- **WHEN** the user request implies live execution, broker routing, account state, portfolio management, margin, transfer, allocation, or order placement
- **THEN** the system refuses or reports unsupported behavior
- **AND** preserves the read-only research boundary

### Requirement: Research automation shall be observable

Research automation lifecycle events SHALL be persisted and correlated with sandbox or tool execution.

#### Scenario: Experiment finishes

- **WHEN** an experiment reaches a terminal state
- **THEN** the system emits success or failure lifecycle events
- **AND** links output artifacts, logs, generated code, and validation evidence by correlation ID
