# Change: PostgreSQL authoritative storage

## Status

Proposed and partially implemented. This change is the normative storage program for GitHub epic #390 and child issues #391–#400. The architecture and inventory slice is owned by #391; no runtime migration, cutover or source cleanup is considered complete merely because it appears in this proposal.

## Why

`vnalpha` has outgrown a production topology built around one writable DuckDB file plus a separate SQLite provisioning queue.

The current design requires application-level coordination for concerns that a server database should own:

- a process-global `fcntl` lock before every DuckDB mutation;
- one writer across migrations, ingestion, features, scoring, outcomes, memory, audit and maintenance;
- separate SQLite and DuckDB transactions with crash recovery between queue state and business state;
- file paths, bind mounts and copied-file backup/restore as application architecture;
- DuckDB driver types and exceptions in repository and transaction signatures;
- long-running API/worker processes constrained by a local file rather than explicit database roles and connection budgets.

These constraints block safe concurrent reads and writes, multi-process worker correctness, atomic queue/business transitions, conventional schema migration, least-privilege roles and operational PostgreSQL backup/restore.

## What Changes

### 1. One authoritative PostgreSQL database

All mutable production state moves to one PostgreSQL database. Logical ownership is separated with schemas:

```text
openstock database
├─ market       reference, raw/canonical market data and source evidence
├─ research     features, scores, watchlists, outcomes and research state
├─ operations   schema versions, ingestion/maintenance state and typed jobs
└─ audit        assistant, tool, model, policy and operator evidence
```

PostgreSQL 18 is the canonical target. PostgreSQL 16 is the minimum supported major during migration. Deployments SHALL run a currently supported minor release for their selected major.

### 2. Database-neutral application boundary

The synchronous application layer uses Psycopg 3 and `psycopg_pool` behind explicit repository and transaction interfaces. Raw driver connections, cursors, SQLSTATE values and driver exceptions SHALL NOT cross infrastructure boundaries.

DuckDB remains behind a migration-only adapter until cutover. SQLite remains behind the existing queue facade until #395 replaces it.

### 3. PostgreSQL queue and transaction ownership

The finite typed provisioning goals remain unchanged, but their durable lifecycle moves to PostgreSQL. Atomic claim uses row-state invariants and PostgreSQL locking rather than a file lock. Queue membership and business publication may share one transaction when the operation is bounded and requires atomicity.

### 4. Versioned schema and explicit migration

PostgreSQL schemas are created through ordered immutable migrations, not Python `CREATE TABLE IF NOT EXISTS` loops or lazy TUI/chat startup. Every current DuckDB/SQLite domain has a named PostgreSQL destination and owner in `design.md`.

### 5. Resumable data migration and reversible cutover

A bounded migration tool copies frozen DuckDB and SQLite state into PostgreSQL, records source identities and checkpoints, quarantines invalid conversions, and emits row/key/hash/domain reconciliation evidence. Cutover uses a finite write freeze and rehearsed rollback. Permanent application dual-write is prohibited.

### 6. Evidence-based physical design

Native PostgreSQL indexes and unpartitioned tables are the baseline. Native range partitioning is introduced only for measured large time-oriented tables. TimescaleDB remains optional and requires reproducible workload evidence plus accepted packaging, backup and upgrade costs.

### 7. Optional DuckDB is derived and read-only

After cutover, DuckDB may exist only as an optional offline analytical/export accelerator reading a declared PostgreSQL snapshot or immutable files. It SHALL NOT serve readiness, queue state, maintenance, current-symbol analysis or authoritative research publication.

## Impact

### Code

Primary affected areas:

```text
vnalpha/core/config.py
vnalpha/warehouse/
vnalpha/provisioning_queue/
vnalpha/data_availability/
vnalpha/data_provisioning/
vnalpha/maintenance/
vnalpha/research and analysis repositories
vnalpha/chat and assistant persistence
packaging/
docker-compose.yml
scripts/
```

### Data and state

- DuckDB and SQLite remain authoritative only until the controlled #397 cutover.
- PostgreSQL becomes authoritative only after schema readiness, migration reconciliation and cutover gates pass.
- No production process writes both old and new stores permanently.
- Legacy files remain frozen, hashed and read-only for a declared rollback retention period.

### Compatibility

- Public CLI/TUI/service DTOs and research semantics remain stable.
- Point-in-time exclusion, idempotent keys, source policy, quality, provenance and fail-closed behavior remain authoritative.
- Physical SQL, table placement, internal identifiers and JSON storage may change when migrations preserve the public contracts.

## Dependencies

- #376 retains the thin-client/service process boundary.
- #338 retains finite typed provisioning goals.
- Existing canonical, feature, scoring, outcome, memory and audit contracts define parity expectations.
- #391 must close before runtime implementation; subsequent dependency order is owned by #390.

## Migration Strategy

1. Specify the target architecture and run the repository-wide coupling inventory (#391).
2. Add the Psycopg runtime, pool, typed errors and transaction abstraction (#392).
3. Add versioned PostgreSQL schemas and migration readiness (#393).
4. Port production repositories and pipeline writes (#394).
5. Move the durable typed queue to PostgreSQL (#395).
6. Build resumable migration and reconciliation tooling (#396).
7. Prove parity, rehearse rollback and execute cutover/soak (#397).
8. Benchmark and accept the physical design (#398).
9. Prove deployment, least privilege, backup/restore and observability (#399).
10. Remove authoritative DuckDB/SQLite runtime paths after rollback expiry (#400).

## Non-Goals

- No public database listener or multi-tenant SaaS platform.
- No repository or package split.
- No generic distributed workflow engine or arbitrary SQL job payload.
- No Kafka, RabbitMQ or Celery requirement.
- No automatic TimescaleDB adoption.
- No permanent DuckDB/PostgreSQL dual write.
- No broker, account, portfolio or trading execution behavior.
