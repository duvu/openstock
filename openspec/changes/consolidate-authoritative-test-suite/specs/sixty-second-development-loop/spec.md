## ADDED Requirements

### Requirement: Development SHALL run one bounded authoritative contract
The normal local edit-test loop SHALL use `make test-loop TEST=<nodeid>` and
shall terminate the selected test at 60 seconds. It SHALL fail fast and SHALL
not expand into aggregate, package, evaluation, R0 or R4 validation.

#### Scenario: A selected contract finishes inside the limit
- **WHEN** a developer runs `make test-loop` with one valid test node
- **THEN** only that node's owning project command executes
- **AND** the command returns its result within 60 seconds.

#### Scenario: A selected contract exceeds the limit
- **WHEN** the bounded command reaches 60 seconds
- **THEN** it fails non-zero
- **AND** the contract is recorded as test-architecture debt rather than
  silently expanded into a broad validation lane.

### Requirement: Documentation-only work SHALL not run runtime suites
Docs and OpenSpec-only changes SHALL require no runtime test during the inner
loop. Strict OpenSpec validation is reserved for a frozen spec candidate.

#### Scenario: Only OpenSpec files change
- **WHEN** a developer updates only the change artifacts
- **THEN** no runtime suite is selected for the inner loop.
