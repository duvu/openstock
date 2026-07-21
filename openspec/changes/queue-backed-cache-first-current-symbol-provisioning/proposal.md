# Change: Queue-backed cache-first research runtime

## Status

Proposed. This change is the normative program specification for issues #317–#344 and the operational proof in #255. No runtime capability is considered implemented merely because it appears in this proposal.

## Why

OpenStock already persists raw, canonical and derived evidence in DuckDB, but the current request and maintenance paths still provision directly. The current implementation can:

- open writable DuckDB connections from interactive processes;
- fall back to a copied warehouse when the configured database cannot be opened;
- lock only by symbol/date while multiple symbols share one DuckDB file;
- continue downstream actions after an upstream provisioning failure;
- reacquire a complete lookback and reprocess complete symbol history for a small tail gap;
- treat benchmark, feature and score evidence as one global readiness gate;
- run daily acquisition, feature building, scoring, context, outcomes and memory in one one-shot process;
- model assistant provisioning and analysis as two unconditional steps.

These behaviors conflict with the target single-host operating model: one research warehouse, one writer, persisted-data reuse, durable queued work, explicit wait/detach behavior and truthful full/degraded/unavailable results.

## What Changes

### 1. Warehouse ownership

- Production uses one configured `warehouse.duckdb`; no automatic copy or fallback warehouse is allowed.
- Read paths use short-lived read-only connections.
- Every DuckDB mutation uses one `WarehouseWriteCoordinator`, one global filesystem lock and a writable connection opened only after lock acquisition.
- Queue waiting and polling never retain a DuckDB connection.

Owned by #343.

### 2. Source-aware artifact readiness

A read-only `ArtifactReadinessReport` classifies relevant artifacts as:

```text
READY | STALE | MISSING | INVALID
```

Readiness is capability-scoped and combines warehouse evidence with source policy, provider capability/auth readiness, persistence permission and bounded remediation availability.

Initial capabilities:

```text
PRICE_ANALYSIS
CANDIDATE_RANKING
```

Owned by #320 and used by #318/#319/#325/#322.

### 3. Finite durable provisioning queue

A local SQLite queue at `/var/lib/openstock/queue/provisioning.sqlite3` stores exactly three versioned goal types:

```text
ENSURE_CURRENT_SYMBOL
SYNC_DATASET_RANGE
FINALIZE_MARKET_SESSION
```

Equivalent active goals join one job. Different desired states never collide. SQLite runtime settings, payload limits, priority escalation, leases and terminal results are explicit and testable.

Owned by #338 and #323.

### 4. One sequential provisioner

One long-running worker claims jobs sequentially, uses an explicit handler registry, re-reads and re-plans persisted evidence, executes bounded stages, verifies postconditions and uses at-least-once delivery with idempotent effects.

The worker supports bounded stage timeouts, lease extension, cooperative cancellation and graceful shutdown.

Owned by #324 and #321.

### 5. Cache-first incremental provisioning

- Ready same-date evidence creates no job and no write work.
- Missing OHLCV work is limited to the exact missing tail or bounded repair range.
- Raw-ready/canonical-stale work performs no provider call.
- Canonical promotion accepts an affected range instead of scanning full symbol history.
- Downstream actions are marked `BLOCKED` and are not invoked after a failed prerequisite.

Owned by #318, #319 and #321.

### 6. One current-symbol application boundary

CLI, TUI, slash commands and assistant call one `CurrentSymbolResearchApplication`. It owns readiness, queue submit/join, wait policy, capability selection and deterministic analysis.

Protocol states are:

```text
READY | DEGRADED | ACCEPTED | PENDING | UNAVAILABLE | FAILED
```

The planner no longer emits unconditional provisioning followed by analysis. Non-analysis states never call deterministic analysis.

Owned by #325 and #322.

### 7. Queue-backed daily maintenance and finalization

A maintenance producer freezes a validated session, universe snapshot and source-policy version, persists expected typed goals, enqueues bounded benchmark/equity acquisition jobs and detaches.

Acquisition jobs prepare canonical evidence only:

- benchmark: `SYNC_DATASET_RANGE(index.ohlcv)`;
- equity: `ENSURE_CURRENT_SYMBOL(PRICE_ANALYSIS)`.

After every expected job is mapped and terminal, an idempotent trigger submits one `FINALIZE_MARKET_SESSION` job. Finalization builds features, scores/watchlist, context, outcomes and memory once for the frozen session and records `SUCCESS`, `PARTIAL` or `FAILED`.

Owned by #326 and #337.

### 8. Operations, packaging and documentation

- Queue health, retention, checkpoint and fail-closed recovery are explicit.
- The queue worker, queue paths, global lock and maintenance producer are packaged for one supported host.
- Canonical architecture, pipeline, deployment and operator documentation are reconciled.
- Ten consecutive market sessions provide live evidence for the complete flow.

Owned by #339, #344, #340 and #255. Issue #279 remains a separate acceptance-only closure for the previously delivered installer.

## Impact

### Code

Primary affected packages:

```text
vnalpha/warehouse
vnalpha/data_availability
vnalpha/data_provisioning
vnalpha/provisioning_queue
vnalpha/current_symbol
vnalpha/maintenance
vnalpha/assistant
vnalpha/chat
vnalpha/cli_app
vnalpha/tui
packaging/systemd
```

### Data and state

- Existing DuckDB research data remains authoritative and is not migrated to another database.
- Queue state is stored separately in SQLite.
- A small `maintenance_run_job` mapping is added to DuckDB; it is a run ledger, not a generic dependency graph.
- Existing direct commands may remain for diagnostics but must use the global writer coordinator and are no longer the canonical operating path.

### Compatibility

- Existing read-only deterministic research outputs remain compatible.
- Current provisioning result models may require a compatibility adapter while callers move to the new application result.
- Historical replay/backtest remains read-only and never auto-enqueues current acquisition.
- Queue payloads and results are explicitly versioned; unsupported versions fail closed.

## Dependencies

- Existing source-policy and dataset-readiness work (#253).
- Existing maintenance ledger atomicity (#252).
- Existing canonical, features, scoring, outcomes and memory services.
- Existing trading calendar validity boundary (#254).

## Migration Strategy

1. Introduce the write coordinator and fail-closed connection lifecycle without changing user-visible queue behavior.
2. Introduce read-only readiness and typed goal models.
3. Add the SQLite repository and worker with the current-symbol handler.
4. Move interactive current-symbol orchestration to the queue-backed application service.
5. Convert scheduled maintenance to producer/finalizer behavior.
6. Add queue operations and package the daemon.
7. Reconcile documentation and run the live soak.

At each phase, old direct write paths either delegate to the new coordinator/application service or are explicitly marked diagnostic-only. There is no big-bang warehouse migration.

## Non-Goals

- No Redis, RabbitMQ, Kafka, Celery or external orchestrator.
- No distributed or concurrent worker pool.
- No generic DAG/workflow language or per-artifact jobs.
- No server-database migration.
- No arbitrary SQL, shell, dynamic module or unrestricted URL payloads.
- No provider-router redesign.
- No automatic scoring-policy mutation.
- No broker, portfolio or trading execution behavior.
