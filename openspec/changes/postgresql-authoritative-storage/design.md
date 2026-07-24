# Design: PostgreSQL authoritative storage

## Context

OpenStock remains a single-host modular monolith with a host-local `vnalpha` service plane and `vnstock-service` provider boundary. The process split in #376 remains valid. This design changes persistence ownership, not product scope or service decomposition.

Current production state is split between a DuckDB research warehouse and a SQLite provisioning queue. DuckDB driver types, direct SQL and file paths are widely coupled to repositories, migrations, tests, packaging and documentation. #391 therefore establishes the target and an executable repository inventory before runtime code changes.

## Goals

- Make PostgreSQL the only mutable production source of truth.
- Preserve deterministic research, point-in-time and source-lineage contracts.
- Support concurrent service reads and safe worker writes without a filesystem mutex.
- Put queue and business-state transitions in one database.
- Introduce explicit schema versions, roles, timeouts, retries, backup and restore.
- Keep the application and protocol boundaries independent of the database driver.
- Produce a resumable, reconcilable and reversible migration.

## Non-Goals

- Public database access, multi-tenancy or cross-region HA.
- A microservice or repository split.
- A generic ORM domain model.
- A generic DAG engine or arbitrary executable queue payload.
- Immediate adoption of TimescaleDB.
- Runtime cutover in #391.

## Decision 1: PostgreSQL support policy

The canonical target is PostgreSQL 18. The minimum supported major during the migration is PostgreSQL 16. PostgreSQL 14 is excluded because it reaches end of support in 2026; PostgreSQL 15 is not selected as the minimum because its shorter remaining support window would force an earlier mandatory major upgrade.

Every supported deployment SHALL:

- run a currently supported minor release for its major;
- declare the server major and exact minor in operational evidence;
- reject unsupported or ahead-of-tested majors through readiness;
- perform explicit compatibility validation before a major upgrade.

The canonical Compose development image SHALL follow the PostgreSQL 18 major and SHALL be pinned according to the repository's image-integrity policy when #399 implements it.

## Decision 2: One database with four schemas

Use one database named `openstock`. Cross-domain atomicity and operational simplicity outweigh the isolation benefit of multiple databases.

| Schema | Owns | Primary writer role |
| --- | --- | --- |
| `market` | reference identity, source snapshots, raw/canonical market data, quality, gaps, quarantine, corporate actions, fundamentals, valuation and disclosures | worker |
| `research` | features, relative strength, scores, watchlists, context, outcomes, replay/backtest, experiments, artifacts and typed memory | worker |
| `operations` | migration metadata, ingestion runs, maintenance/finalization ledgers, provisioning jobs, leases, run-to-job membership and operator state | service and worker by operation |
| `audit` | assistant, tool, model, policy and operator evidence | service and worker |

`public` SHALL contain no application tables. Application roles SHALL use a fixed trusted `search_path` or schema-qualified names; untrusted schemas SHALL NOT precede application schemas.

## Decision 3: Current-domain destination map

The table-level catalog generated during #393 SHALL use this ownership map. No current domain is left without a destination.

| Current DuckDB/SQLite domain or schema module | PostgreSQL destination | Migration owner |
| --- | --- | --- |
| `symbol_master`, source snapshots/membership, reference membership and classification history | `market` | #393/#394 |
| ingestion runs, dataset quality, gap observations, rejected rows and OHLCV quarantine | `operations` for run state; `market` for row evidence | #393/#394 |
| raw and canonical equity/index/intraday OHLCV | `market` | #393/#394 |
| corporate-action schemas and revision evidence | `market` | #393/#394 |
| fundamentals, company context, valuation and disclosures | `market` | #393/#394 |
| feature snapshots, benchmark definitions and relative-strength snapshots | `research` | #393/#394 |
| candidate scores, watchlists, scoring policy decisions/pointers and rejected candidates | `research` | #393/#394 |
| market/sector/group context snapshots | `research` | #393/#394 |
| candidate outcomes, aggregate outcomes and outcome-evaluation runs | `research` | #393/#394 |
| ranking evaluation, replay and ranking-policy decision schemas | `research` | #393/#394 |
| research artifacts, experiments, answer evidence and research-model metadata | `research`; immutable answer/model trace evidence in `audit` | #393/#394 |
| sandbox/research repair state | `research` | #393/#394 |
| memory events, claims, documents and compaction runs | `research` | #393/#394 |
| assistant sessions/messages, tool traces, model routes and prompt/audit records | `audit` | #393/#394 |
| maintenance run, stages, frozen universe, finalization and `maintenance_run_job` | `operations` | #393/#394 |
| SQLite `provision_job`, leases, cancellation, terminal evidence and queue tombstones | `operations` | #393/#395 |
| schema version and migration history | `operations` | #393 |

The #393 catalog SHALL enumerate every physical current table and record either one destination above or an explicit deletion rationale.

## Decision 4: Psycopg 3 and explicit persistence interfaces

Use synchronous Psycopg 3 with `psycopg_pool.ConnectionPool`, matching the existing synchronous application layer. Do not introduce SQLAlchemy ORM entities. Parameterized SQL, small row mappers and repository interfaces are the default; SQLAlchemy Core may be considered only when #392 demonstrates a material reduction in handwritten portability risk.

Infrastructure contracts SHALL expose application-owned protocols such as:

```text
DatabaseRuntime
ReadSession
WriteTransaction
MigrationSession
Repository-specific query interfaces
```

They SHALL NOT expose `psycopg.Connection`, `psycopg.Cursor`, `duckdb.DuckDBPyConnection`, `sqlite3.Connection`, SQLSTATE strings or driver exceptions outside infrastructure packages.

Pool creation is explicit (`open=False` followed by bounded startup readiness). Connections are short-lived and returned through context managers. Pool statistics are observable.

## Decision 5: Transactions, timeouts and retries

Default isolation is `READ COMMITTED`.

Use `REPEATABLE READ` only for bounded snapshot/reconciliation operations that require one consistent database view. Use `SERIALIZABLE` only for small, named invariants when row constraints and locking cannot express correctness more simply.

Initial timeout policy:

| Setting | Service query | Worker transaction | Migration/operator |
| --- | ---: | ---: | ---: |
| connect timeout | 5 s | 5 s | 10 s |
| pool acquisition timeout | 5 s | 10 s | N/A or explicit |
| lock timeout | 3 s | 10 s | 30 s |
| statement timeout | 15 s | 300 s | explicit per command |
| idle-in-transaction timeout | 15 s | 30 s | 60 s |

Long provider/network calls SHALL occur outside PostgreSQL transactions.

Automatic transaction retry is allowed only for SQLSTATE `40001` (serialization failure) and `40P01` (deadlock), with at most three attempts, bounded jitter and a transaction closure proven free of non-idempotent external side effects. Authentication, permission, constraint, timeout, cancellation and arbitrary operational failures are not retried automatically.

Nested transaction behavior uses savepoints or an explicit rollback-only contract. Silent nested autocommit is prohibited.

## Decision 6: Roles and grants

Define group roles and separate login roles:

| Role | Capability |
| --- | --- |
| `openstock_migrator` | owns schemas/migrations; no application login reuse |
| `openstock_service` | read market/research/audit projections; submit/join/status/cancel permitted jobs in `operations`; write bounded service audit state |
| `openstock_worker` | claim jobs and mutate allowlisted market/research/operations/audit tables through application repositories |
| `openstock_backup` | backup/restore permissions required by the selected strategy; no application execution |
| `openstock_operator` | bounded diagnostics and approved maintenance procedures, not unrestricted application DML by default |

Objects are not owned by service or worker login roles. Default privileges SHALL prevent accidental broad access. Passwords or DSNs SHALL NOT appear in process arguments, committed files or diagnostics.

## Decision 7: PostgreSQL type policy

- Internal identifiers that are semantically UUIDs use `uuid`; externally defined provider IDs remain text.
- Trading sessions and effective dates use `date`.
- Observed, created, updated and published instants use `timestamptz`, stored as absolute instants and rendered in `Asia/Ho_Chi_Minh` where appropriate.
- Existing timezone-naive intraday timestamps require an explicit dataset-specific conversion rule before migration. No implicit server-timezone cast is allowed.
- Integral counts and volumes use `integer` or `bigint` when the source contract is integral.
- Research calculations currently represented by IEEE floating point use `double precision` initially to preserve parity.
- Exact accounting, cash-flow, share-capital or provider-decimal fields use a documented `numeric(p,s)` selected from source precision and reconciliation requirements.
- Validated structured evidence, lineage, diagnostics and policy documents use `jsonb`.
- Raw payload fidelity that cannot survive JSON normalization remains immutable text/bytes with a validated normalized projection where required.
- Frequently evolving states use constrained text or reference tables, not PostgreSQL enums. Stable closed values may use checks.

## Decision 8: PostgreSQL provisioning queue

Preserve the finite typed goal model from #338. The PostgreSQL queue SHALL use:

- one normalized active-job identity protected by a partial unique index or equivalent constraint;
- short submit/join, claim, heartbeat, completion and cancellation transactions;
- `FOR UPDATE SKIP LOCKED` or an equivalent proven row-locking claim pattern;
- lease owner/expiry and bounded attempts;
- atomic priority escalation for joined queued jobs;
- idempotent maintenance run-to-job membership in `operations`;
- bounded payload/result/error documents;
- no provider, model or long analytical work inside queue transactions.

Correctness SHALL support multiple competing worker processes even if initial production configuration remains `max_concurrency=1`.

## Decision 9: Physical design and TimescaleDB threshold

Start with ordinary PostgreSQL tables and named B-tree, covering, partial or BRIN indexes tied to actual access paths. Do not partition small tables.

Native range partitioning may be approved when a candidate table has realistic projected cardinality above 10 million rows, retention/maintenance benefits, and predominantly date-bounded access, or when the unpartitioned benchmark misses an accepted p95 budget by more than 20% and partitioning materially fixes it without unacceptable write/operational cost.

TimescaleDB may be approved only when the reproducible #398 workload shows at least a 25% repeatable benefit for a required latency, storage or maintenance budget that native PostgreSQL cannot meet, and #399 accepts extension packaging, upgrades, backup and restore. These thresholds are engineering decision gates, not claims that partitioning or TimescaleDB will necessarily help.

## Decision 10: Migration, cutover and rollback

There is no permanent application dual-write.

Migration phases:

```text
inventory and schema mapping
→ PostgreSQL schema
→ repository parity against frozen fixtures
→ resumable bulk copy
→ incremental final copy under write freeze
→ zero-unexplained-mismatch reconciliation
→ configuration cutover
→ PostgreSQL soak
→ rollback expiry and legacy cleanup
```

During shadow validation, both implementations may process the same immutable inputs independently. Only one backend is authoritative for writes at any time.

Rollback returns to the frozen DuckDB/SQLite sources only within the declared rollback window and only if no incompatible PostgreSQL-only authoritative write has been accepted without a reverse plan.

## Decision 11: Optional DuckDB boundary after cutover

Optional DuckDB tooling SHALL:

- be an explicit extra/command;
- read a declared PostgreSQL snapshot, logical export or immutable Parquet files;
- open no production writable database;
- publish source snapshot/version and derived status;
- remain outside readiness, queue, maintenance and authoritative research publication.

## Decision 12: Machine-checkable coupling inventory

`scripts/postgresql_storage_inventory.py` scans the exact checkout and emits deterministic JSON findings for:

- DuckDB imports, connection types and connection creation;
- SQLite imports, connections and pragmas;
- direct SQL execution;
- DDL and implicit migrations;
- DuckDB-specific SQL/catalog use;
- file-database paths, volume assumptions and file locks;
- in-memory/temporary database tests;
- backup and restore assumptions.

Every finding receives one of the #391 classifications and one child-issue owner. The generated report is preferred over a committed static snapshot so the inventory cannot silently become stale. Archived OpenSpec changes and the inventory implementation itself are excluded and disclosed by the report policy.

`make verify-postgresql-storage-inventory` SHALL fail when required coupling families disappear unexpectedly from an incomplete migration report, a finding is unclassified, an owner is outside #391–#400, a path is unsafe or the report schema is invalid. #400 will replace the transitional required-family checks with allowlisted optional-DuckDB and prohibited-authoritative-usage checks.

## Rejected Alternatives

### Keep DuckDB and strengthen the global writer

Rejected as the target. It preserves the file mutex, split queue/business transactions and multi-process constraints that initiated #390.

### Keep SQLite for queue state

Rejected after cutover. It preserves a cross-database crash boundary and prevents atomic bounded queue/publication transitions.

### Adopt TimescaleDB immediately

Rejected without workload evidence. Native PostgreSQL is operationally simpler and sufficient until #398 proves otherwise.

### Use a heavy ORM rewrite

Rejected. The migration needs explicit SQL, stable domain contracts and controlled transaction boundaries; an ORM entity rewrite would expand scope without proving portability.

### Permanent dual write

Rejected because it creates two mutable authorities and substantially increases reconciliation and failure modes.

## Validation Strategy

#391 closes only when:

- strict OpenSpec validation passes;
- the inventory scanner compiles and its focused fixture contract passes;
- `make verify-postgresql-storage-inventory` passes on the exact repository checkout;
- repository consistency passes;
- #306, #376, #377 and #381 record #390 precedence for persistence;
- the PR records exact commands and SHA evidence.
