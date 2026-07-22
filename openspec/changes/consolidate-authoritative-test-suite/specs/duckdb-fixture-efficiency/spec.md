## ADDED Requirements

### Requirement: Migrated DuckDB setup SHALL be reusable and isolated
Compatible tests SHALL copy one migrated template warehouse per test worker to an isolated per-test path. Tests SHALL NOT share mutable DuckDB connections or database files.

#### Scenario: Two compatible tests request a migrated warehouse
- **WHEN** each test mutates its fixture
- **THEN** both start from the same migrated schema template at different paths
- **AND** neither test observes the other's rows.

#### Scenario: Parallel workers request fixtures
- **WHEN** tests run with multiple workers
- **THEN** each worker owns its template and every test owns its mutable copy.

### Requirement: Migration semantics SHALL retain dedicated coverage
Fresh migration, migration idempotency, supported upgrade and rollback contracts SHALL use dedicated empty or versioned warehouse inputs and SHALL NOT be replaced by the migrated template fixture.

#### Scenario: Fresh migration is tested
- **WHEN** the migration test runs
- **THEN** it begins from an unmigrated database and verifies the canonical schema contract.

#### Scenario: Upgrade rollback is tested
- **WHEN** a supported prior schema fails during upgrade
- **THEN** the dedicated test proves rollback without using a pre-migrated template.

### Requirement: Schema expectations SHALL have one canonical manifest
Repeated hard-coded schema table counts and lists SHALL be replaced by one canonical manifest owned by dedicated schema/migration tests. Consumers SHALL compare against that manifest rather than independent copies.

#### Scenario: A schema table is added
- **WHEN** the canonical schema changes
- **THEN** one manifest update drives schema expectations and stale duplicate lists fail review or consistency.

### Requirement: Transaction reuse SHALL respect lifecycle contracts
Transaction rollback reuse SHALL be limited to tests that do not verify commit, crash, reopen, locking, multiprocessing or file lifecycle behavior. Those lifecycle tests SHALL retain isolated file-backed databases.

#### Scenario: A rollback-compatible repository test runs
- **WHEN** its contract observes only transaction-local mutations
- **THEN** rollback isolation may reuse compatible setup.

#### Scenario: A writer exclusion test runs
- **WHEN** its contract depends on process and file-lock behavior
- **THEN** it uses a dedicated file-backed database and is never converted to shared transaction reuse.

### Requirement: Sequential local execution SHALL remain authoritative
The change SHALL retain a simple sequential local command. Parallel and hosted
execution policy is outside issue #348.

#### Scenario: A final local candidate is evaluated
- **WHEN** a developer runs the complete authoritative suite
- **THEN** the sequential manifest runner is available as the authoritative command.
