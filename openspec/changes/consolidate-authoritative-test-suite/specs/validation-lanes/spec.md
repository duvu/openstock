## ADDED Requirements

### Requirement: Local validation SHALL use bounded, domain and final lanes
The repository SHALL provide a 60-second one-contract development loop, local
affected-domain authoritative runners, and one complete final-candidate runner.
Package acceptance is manual and selected only when package, installation,
dependency-layout, service-unit or release inputs change.

#### Scenario: A normal source change is evaluated locally

- **WHEN** a developer changes one `vnalpha` contract
- **THEN** the owning 60-second test runs during the edit loop
- **AND** its affected local domain runs before the final candidate.

#### Scenario: Documentation-only work is evaluated

- **WHEN** only documentation or OpenSpec artifacts change
- **THEN** no runtime suite is required during the edit loop.

#### Scenario: Package inputs change

- **WHEN** package, installation, dependency-layout, service-unit or release
  inputs change
- **THEN** the relevant manual package acceptance is selected.

### Requirement: Aggregate execution SHALL collect each authoritative node once
An aggregate local lane SHALL resolve the authoritative inventory to one stable
pytest invocation. Obsolete R0, R4 and Phase wrappers SHALL not run before or
after that aggregate.

#### Scenario: Full aggregate validation is planned

- **WHEN** the aggregate execution plan is inspected
- **THEN** every manifest node appears exactly once
- **AND** no R0, R4 or Phase wrapper contributes a second collection.

#### Scenario: A duplicate node enters the inventory

- **WHEN** the runner resolves an inventory with a repeated node
- **THEN** manifest validation fails before pytest executes.

### Requirement: CI routing SHALL remain out of scope
Issue #348 SHALL NOT add, require or use GitHub Actions jobs, path-aware
routing, required gates or hosted workflow evidence. It MAY remove the
#348-owned routing artifacts solely to restore the pre-#349 generic workflow.

#### Scenario: The active change is completed

- **WHEN** final local evidence is recorded
- **THEN** no hosted CI result is a prerequisite for completion.
