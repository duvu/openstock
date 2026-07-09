# closed-loop-repair Specification Delta

## ADDED Requirements

### Requirement: System shall support closed-loop research repair lifecycle

The system SHALL support a closed-loop lifecycle for failed sandbox jobs and research automation artifacts.

#### Scenario: Research job fails

- **WHEN** a sandbox job or research automation job fails
- **THEN** the system can observe the failure
- **AND** package a repair bundle
- **AND** generate an AI repair proposal
- **AND** validate a repaired artifact
- **AND** promote or reject the artifact based on validation evidence

### Requirement: Repair bundles shall contain complete diagnostic context

Repair bundles SHALL include enough information to diagnose and reproduce the failure without exposing secrets or unsafe data.

#### Scenario: Repair bundle is prepared

- **WHEN** the user submits `/repair prepare --latest`
- **THEN** the system creates a repair bundle for the latest failed job/session
- **AND** includes failed job/session ID
- **AND** includes user request and plan summary
- **AND** includes generated code
- **AND** includes guard result, stdout/stderr, error trace, input dataset references, artifact state, validation result, environment summary, redaction status, and correlation ID

### Requirement: AI repair proposal shall be scope-limited

AI repair proposals SHALL be limited to research artifacts and sandbox research code.

#### Scenario: Repair proposal includes trading execution behavior

- **WHEN** an AI repair proposal includes broker, order, account, portfolio, margin, transfer, allocation, or trading execution behavior
- **THEN** the system rejects the proposal
- **AND** logs the rejection
- **AND** preserves the read-only research boundary

### Requirement: Repair loop shall be bounded

Auto-repair SHALL have a maximum number of attempts and terminal failure state.

#### Scenario: Repair attempts are exhausted

- **WHEN** repair attempts reach the configured maximum
- **THEN** the repair loop stops
- **AND** the repair status becomes failed
- **AND** all attempts remain persisted for review

### Requirement: Validation gate shall control research artifact promotion

Research artifacts SHALL pass validation before promotion.

#### Scenario: Artifact validates successfully

- **WHEN** `/validate run <artifact-id>` passes static guard, sandbox execution, output schema, artifact manifest, lineage, quality status, caveats, and read-only boundary checks
- **THEN** the artifact becomes eligible for research promotion

#### Scenario: Artifact validation fails

- **WHEN** any required validation check fails
- **THEN** the artifact is not eligible for promotion
- **AND** the validation failure is persisted

### Requirement: Deploy commands shall mean research artifact promotion only

`/deploy` commands SHALL operate only on research artifact promotion, verification, rollback, and deploy logs.

#### Scenario: Research artifact is promoted

- **WHEN** the user submits `/deploy promote <candidate> --deployment-id <id>`
- **AND** the candidate has passing validation evidence
- **THEN** the system marks the research artifact as promoted
- **AND** persists a deploy log
- **AND** does not touch broker, order, account, portfolio, margin, transfer, allocation, or trading execution systems

#### Scenario: Research artifact is rolled back

- **WHEN** the user submits `/deploy rollback <deployment-id>`
- **THEN** the system reverts the research artifact promotion state
- **AND** persists rollback evidence

### Requirement: Closed-loop lifecycle shall be observable

Repair, validation, promotion, and rollback SHALL emit correlated lifecycle events.

#### Scenario: Closed-loop action occurs

- **WHEN** repair, validation, promotion, rollback, or rejection occurs
- **THEN** the system emits a lifecycle event with correlation ID
- **AND** persists evidence into logs/artifacts
- **AND** preserves redaction-by-default
