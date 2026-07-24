## ADDED Requirements

### Requirement: PostgreSQL SHALL become the only mutable production authority
After the controlled cutover, all mutable `vnalpha` production state SHALL reside in one PostgreSQL database and no production process SHALL mutate DuckDB or SQLite.

#### Scenario: A production service or worker starts after cutover
- **WHEN** the configured PostgreSQL database is unavailable, unauthorized or schema-incompatible
- **THEN** readiness fails with a typed actionable error
- **AND** the process does not fall back to `warehouse.duckdb`, `provisioning.sqlite3` or an in-memory database.

### Requirement: PostgreSQL deployment compatibility SHALL be explicit
The canonical target SHALL be PostgreSQL 18 and the minimum supported major during migration SHALL be PostgreSQL 16. Every deployment SHALL run a supported minor release and pass declared compatibility readiness.

#### Scenario: An unsupported server major is configured
- **WHEN** startup detects a PostgreSQL version outside the tested support matrix
- **THEN** schema/database readiness fails closed
- **AND** no migration or application work begins.

### Requirement: Storage ownership SHALL use one database and explicit schemas
The `openstock` database SHALL separate `market`, `research`, `operations` and `audit` objects. The `public` schema SHALL contain no application tables.

#### Scenario: A worker publishes a daily watchlist
- **WHEN** canonical and derived evidence is committed
- **THEN** market evidence is stored under `market`
- **AND** feature, score and watchlist state is stored under `research`
- **AND** job/finalization state is stored under `operations`
- **AND** immutable execution evidence is stored under `audit` where applicable.

### Requirement: Driver objects SHALL remain inside infrastructure
Application services and public DTOs SHALL NOT expose Psycopg, DuckDB or SQLite connections, cursors, driver exceptions or SQLSTATE values.

#### Scenario: PostgreSQL rejects a statement
- **WHEN** the driver reports authentication, permission, timeout, cancellation, constraint, serialization, deadlock or schema failure
- **THEN** infrastructure maps it to a typed application error
- **AND** the raw driver exception does not cross the repository/application boundary.

### Requirement: PostgreSQL sessions SHALL be bounded and explicit
Connections SHALL come from a bounded synchronous pool, transactions SHALL be explicit, and connection, pool, statement, lock and idle-in-transaction timeouts SHALL be configured by role.

#### Scenario: A provider call is required before persistence
- **WHEN** a worker must call `vnstock-service`
- **THEN** the provider call completes outside a PostgreSQL transaction
- **AND** the subsequent bounded write transaction opens only for database work.

#### Scenario: A retryable database conflict occurs
- **WHEN** a transaction fails with serialization failure or deadlock
- **AND** its transaction closure has no non-idempotent external side effect
- **THEN** the runtime may retry within the configured bounded attempt policy
- **AND** it does not retry unrelated failures.

### Requirement: Roles SHALL follow least privilege
Migration, service, worker, backup and operator capabilities SHALL use separate roles and grants. Application login roles SHALL NOT own application schemas or objects.

#### Scenario: The read/service role attempts an unapproved market mutation
- **WHEN** the service login executes DML outside its bounded queue/audit permissions
- **THEN** PostgreSQL rejects the operation
- **AND** the application reports a typed permission failure.

### Requirement: Type conversion SHALL preserve research semantics
Trading dates SHALL use `date`; observed instants SHALL use `timestamptz`; UUID-like internal IDs SHALL use `uuid`; structured validated evidence SHALL use `jsonb`; numeric types SHALL be selected by documented parity and precision rules.

#### Scenario: A timezone-naive intraday row is migrated
- **WHEN** the source timestamp has no timezone
- **THEN** the migration applies the dataset-specific declared timezone rule
- **AND** it does not rely on the PostgreSQL server session timezone implicitly.

### Requirement: TimescaleDB SHALL remain evidence-gated
Native PostgreSQL SHALL be the baseline. TimescaleDB SHALL NOT become required unless #398 proves a material repeatable benefit and #399 accepts its operational lifecycle.

#### Scenario: Native PostgreSQL meets the workload budgets
- **WHEN** unpartitioned or natively partitioned PostgreSQL satisfies accepted performance and operational budgets
- **THEN** TimescaleDB remains disabled or deferred.

### Requirement: Optional DuckDB SHALL be derived and read-only
Any DuckDB retained after cutover SHALL read only declared PostgreSQL snapshots or immutable exports and SHALL NOT participate in authoritative application behavior.

#### Scenario: Optional analytics runs after cutover
- **WHEN** an operator invokes the explicit DuckDB analytics/export command
- **THEN** output identifies the PostgreSQL snapshot/export source
- **AND** no readiness, queue, maintenance or publication state is mutated.
