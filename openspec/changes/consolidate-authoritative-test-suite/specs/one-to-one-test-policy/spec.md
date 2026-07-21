## ADDED Requirements

### Requirement: Coverage SHALL be budgeted per public contract
Each public contract or materially distinct externally observable state transition SHALL retain one representative happy-path test and one highest-value edge, invalid-input or failure-path test by default. The budget SHALL NOT be multiplied for helpers, branches, literal values or adapters that implement the same contract.

#### Scenario: A contract has ordinary and failure behavior
- **WHEN** the test inventory is validated
- **THEN** the contract has exactly one canonical H owner and one canonical +1 owner
- **AND** those cases prove the important result and minimum lineage or state effects.

#### Scenario: Equivalent literal inputs exist
- **WHEN** multiple values exercise the same contract and result class
- **THEN** they are represented by one parameterized canonical case rather than separate contract owners.

### Requirement: Additional tests SHALL name an approved risk exception
A retained test beyond H+1 SHALL identify one materially different approved risk class and the contract it protects. Approved classes SHALL be limited to point-in-time/no-lookahead, corporate-action adjustment/invalidation, provider provenance conflict, transaction/crash/recovery, queue lease/idempotency/writer exclusion, security/fail-closed, migration upgrade/rollback, package state preservation, policy promotion/rejection/rollback and cross-version compatibility.

#### Scenario: A third case protects crash recovery
- **WHEN** the inventory classifies the case as an approved transaction/crash/recovery exception
- **THEN** consistency accepts it independently of the contract's H and +1 cases.

#### Scenario: A third equivalent happy path has no risk evidence
- **WHEN** the inventory contains the extra case without an approved category
- **THEN** consistency fails with the contract and file requiring consolidation.

### Requirement: Every test file SHALL have one canonical owner
Every `vnalpha/tests/test_*.py` file SHALL belong to exactly one domain suite, except for one explicit shared-smoke or migration allowlist owner. Domain ownership SHALL distinguish `vnalpha-data`, `vnalpha-research` and `vnalpha-application`; repository routing SHALL also recognize `vnstock-contracts` and `packaging` lanes.

#### Scenario: A new test file is unassigned
- **WHEN** repository consistency evaluates the suite manifest
- **THEN** it fails and identifies the unassigned path.

#### Scenario: A test file is assigned twice
- **WHEN** two domain entries own the same path
- **THEN** consistency fails before tests execute.

### Requirement: Consolidation SHALL preserve replacement evidence
A duplicate, superseded or implementation-detail test SHALL be removed only when retained coverage is identified as the same contract's H, +1 or approved risk exception. A new test for an existing contract SHALL reuse, replace or parameterize current coverage before increasing the count.

#### Scenario: Duplicate adapter happy paths exist
- **WHEN** CLI, TUI and assistant wrappers call the same application contract
- **THEN** domain behavior remains at the application boundary and each surface retains only bounded adapter or parity coverage.

#### Scenario: A financial boundary has no replacement
- **WHEN** a proposed deletion would remove the only PIT, lineage, transaction, recovery or package scenario
- **THEN** the deletion is rejected.
