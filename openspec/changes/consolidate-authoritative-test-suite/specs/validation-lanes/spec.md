## ADDED Requirements

### Requirement: Validation SHALL use bounded, domain and release lanes
The repository SHALL provide an unconditional consistency/spec lane, the
60-second one-contract development loop, affected-domain authoritative lanes,
and full/package acceptance owned by final-candidate, release or explicitly
routed packaging work.

#### Scenario: A normal application pull request is evaluated

- **WHEN** routing identifies an ordinary `vnalpha/src/**` change
- **THEN** consistency and the compact affected-domain lane run
- **AND** Debian acceptance is deliberately skipped.

#### Scenario: A release is evaluated

- **WHEN** the release validation path runs
- **THEN** the complete authoritative inventory and package/operational
  acceptance execute in addition to consistency.

### Requirement: Aggregate execution SHALL collect each authoritative node once
An aggregate lane SHALL resolve the authoritative inventory to one stable
pytest invocation. Obsolete R0, R4 and Phase wrappers SHALL be removed rather
than run before or after the aggregate.

#### Scenario: Full aggregate validation is planned

- **WHEN** the aggregate execution plan is inspected
- **THEN** every manifest node appears exactly once
- **AND** no R0, R4 or Phase wrapper contributes a second collection.

#### Scenario: A duplicate node enters the inventory

- **WHEN** the runner resolves an inventory with a repeated node
- **THEN** repository consistency fails before pytest executes.

### Requirement: Required merge conclusions SHALL fail closed
The always-evaluated Required merge gate SHALL accept only `success` or a
deliberate `skipped` conclusion for each fixed dependency. Failure,
cancellation, timeout, action-required, neutral, startup failure, unknown or
missing conclusions SHALL fail the gate.

#### Scenario: Docs-only runtime jobs are deliberately skipped

- **WHEN** consistency succeeds and runtime/package jobs conclude `skipped`
  by routing policy
- **THEN** the Required merge gate succeeds.

#### Scenario: A required job is cancelled

- **WHEN** any dependency concludes `cancelled`
- **THEN** the Required merge gate fails.

### Requirement: Routing SHALL classify changed paths fail-closed
Routing SHALL classify normalized repository-relative paths as
`docs_openspec_only`, `vnalpha`, `vnstock`, `packaging`,
`shared_contract` or `test_or_workflow_infrastructure`. Unknown paths
shall fail rather than receive a docs-only disposition. Ordinary
`vnalpha/src/**` changes SHALL select compact domains and SHALL NOT select
Debian acceptance.

#### Scenario: Documentation-only work changes

- **WHEN** all changed paths are documentation or OpenSpec artifacts
- **THEN** routing selects consistency/spec and deliberately skips runtime
  lanes.

#### Scenario: Package inputs change

- **WHEN** packaging, installer, dependency-layout, service-unit or release
  inputs change
- **THEN** routing selects package acceptance in addition to applicable
  consistency and full validation.
