# Tasks: PostgreSQL authoritative storage

A task is complete only when its named artifact and validation evidence exist. The epic remains open until #390 completion criteria pass; a checked #391 section does not imply runtime migration.

## 1. Target architecture and inventory — #391

- [x] 1.1 Record PostgreSQL version support, one-database/four-schema topology, Psycopg 3 pool choice, roles, transactions, timeout/retry policy, type semantics, partitioning threshold, optional DuckDB boundary and rejected alternatives in `proposal.md` and `design.md`.
- [x] 1.2 Assign every current storage domain/schema module to `market`, `research`, `operations` or `audit` and one implementation owner.
- [x] 1.3 Add `scripts/postgresql_storage_inventory.py` to scan DuckDB/SQLite imports, direct SQL, DDL, database paths, locks, tests, packaging and documentation into deterministic classified JSON.
- [x] 1.4 Add focused inventory fixture validation and a repository target that checks the exact checkout.
- [x] 1.5 Add normative architecture and inventory requirements under `specs/`.
- [x] 1.6 Record #390 persistence precedence on #306, #376, #377 and #381; keep their non-storage process/application scope intact.

## 2. PostgreSQL runtime boundary — #392

- [ ] 2.1 Add Psycopg 3 and bounded sync pool configuration.
- [ ] 2.2 Add database-neutral read/write/migration interfaces and typed error mapping.
- [ ] 2.3 Add role/session timeout configuration, readiness and pool observability.
- [ ] 2.4 Add savepoint/rollback-only behavior and bounded retry contracts.
- [ ] 2.5 Isolate DuckDB as a migration-only adapter.

## 3. PostgreSQL schemas and migrations — #393

- [ ] 3.1 Produce the exact current-table catalog and destination map.
- [ ] 3.2 Add immutable ordered migrations for `market`, `research`, `operations` and `audit`.
- [ ] 3.3 Add constraints, JSONB/type conversions, indexes and schema-version readiness.
- [ ] 3.4 Prove fresh and supported-baseline upgrades.

## 4. Repository and pipeline port — #394

- [ ] 4.1 Port reference, market, canonical, quality and context repositories.
- [ ] 4.2 Port features, scores, watchlists, outcomes, replay and evaluation.
- [ ] 4.3 Port research, memory, audit and maintenance persistence.
- [ ] 4.4 Prove idempotency, point-in-time exclusion and atomic publication parity.

## 5. PostgreSQL provisioning queue — #395

- [ ] 5.1 Port finite typed jobs, submit/join, priority and cancellation.
- [ ] 5.2 Add row-locking claim, leases, heartbeats and bounded retry.
- [ ] 5.3 Make maintenance membership and required publication transitions atomic.
- [ ] 5.4 Remove production creation/use of `provisioning.sqlite3`.

## 6. Data migration and reconciliation — #396

- [ ] 6.1 Add source identity, checkpointed export/import and conversion quarantine.
- [ ] 6.2 Migrate every DuckDB/SQLite domain with bounded memory and idempotent batches.
- [ ] 6.3 Emit row, key, null, hash, date-range and domain-invariant reconciliation.
- [ ] 6.4 Prove interruption/restart and source immutability.

## 7. Parity, cutover and soak — #397

- [ ] 7.1 Freeze representative DuckDB/SQLite outputs and fixtures.
- [ ] 7.2 Run PostgreSQL shadow parity and classify every difference.
- [ ] 7.3 Rehearse write freeze, final copy, cutover and rollback.
- [ ] 7.4 Complete the declared PostgreSQL soak and ten-session proof.

## 8. Performance decision — #398

- [ ] 8.1 Benchmark realistic ingest, cross-section, history, build, replay and queue workloads.
- [ ] 8.2 Select measured indexes and native partitions.
- [ ] 8.3 Approve or reject TimescaleDB with reproducible evidence.

## 9. Production operations — #399

- [ ] 9.1 Add Compose and Debian/systemd PostgreSQL operation.
- [ ] 9.2 Add least-privilege roles, secret-safe configuration and readiness.
- [ ] 9.3 Add metrics, lock/pool/queue diagnostics and runbooks.
- [ ] 9.4 Prove backup restore and declared RPO/RTO.

## 10. Legacy authority removal — #400

- [ ] 10.1 Remove production DuckDB/SQLite dependencies, paths, locks and migrations.
- [ ] 10.2 Replace migration backend gates with one PostgreSQL authority.
- [ ] 10.3 Isolate any retained DuckDB tooling as explicit read-only derived analytics.
- [ ] 10.4 Reconcile docs/issues and retain frozen legacy files only for audit/rollback policy.
