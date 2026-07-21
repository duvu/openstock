# Design: Queue-backed cache-first research runtime

## Context

OpenStock is a modular monolith deployed on one supported host. `vnstock-service` owns provider access and provider-independent data contracts. `vnalpha` owns the DuckDB research warehouse, deterministic analysis and terminal UX.

DuckDB remains the authoritative research store, but its one-writer constraint is currently enforced inconsistently. Interactive current-symbol requests and daily maintenance can open writable connections and run provisioning directly. A symbol/date lock does not prevent different symbols from writing the same database concurrently. The warehouse connection helper can also create a fallback copy, which violates the single-source-of-truth requirement.

This design introduces a small durable queue and one sequential worker while retaining existing business services and the single-host deployment model.

## Goals

- Reuse persisted valid artifacts before any provider/build work.
- Serialize every DuckDB mutation through one coordinator.
- Make missing-data remediation durable, observable and resumable.
- Support user-controlled wait, bounded wait and detach behavior.
- Preserve truthful degraded/unavailable results.
- Keep maintenance acquisition bounded and finalize session-level artifacts once.
- Avoid a distributed-system or generic-workflow redesign.

## Non-Goals

- Multi-host or high-availability queue processing.
- More than one active provisioner.
- Generic task graphs, arbitrary jobs or per-artifact child jobs.
- Changing deterministic feature/scoring methodologies.
- Changing the provider-independent `vnstock` boundary.
- Moving research data out of DuckDB.

## Decision 1: One warehouse truth and one write coordinator

Production SHALL open only the configured warehouse path. Failure to open it returns a typed error; it MUST NOT copy or substitute the file.

### Read lifecycle

```text
open configured DuckDB read-only
→ query readiness/analysis/status
→ close
```

### Write lifecycle

```text
acquire global warehouse lock
→ open configured DuckDB writable
→ execute bounded transaction/stage
→ commit or rollback
→ close connection
→ release lock
```

The write coordinator applies to provisioning, migrations, finalization, outcomes, context/memory projection and short metadata writes such as chat/session traces. Not every write must be a queue job, but every write must use the same coordinator.

## Decision 2: SQLite is execution state, DuckDB is research truth

Queue path:

```text
/var/lib/openstock/queue/provisioning.sqlite3
```

SQLite stores job identity, lifecycle, priority, lease, stage and bounded result/error data. It does not store market rows, feature values, credentials or business policy.

DuckDB stores all data/research evidence and the maintenance ledger. A `maintenance_run_job` table maps frozen expected goal identities to queue job IDs. A job may be referenced by multiple maintenance runs and interactive callers.

There is no cross-database transaction. Correctness comes from idempotent phased operations and re-reading both stores.

## Decision 3: Finite typed goals

Exactly three top-level goal types are supported:

```text
ENSURE_CURRENT_SYMBOL
SYNC_DATASET_RANGE
FINALIZE_MARKET_SESSION
```

### `ENSURE_CURRENT_SYMBOL`

Identity includes:

```text
symbol
effective_date
desired_capability
allowed_fallback
normalized requested enrichments
refresh_mode
source_policy_version
contract_version
```

### `SYNC_DATASET_RANGE`

Identity includes:

```text
dataset
entity_type
entity_id
bounded start/end or observation range
refresh_mode
source_policy_version
contract_version
```

### `FINALIZE_MARKET_SESSION`

Identity includes:

```text
maintenance_run_id
resolved_session
frozen universe hash
source_policy_version
finalization_contract_version
```

Unknown types, enrichments or versions fail before persistence or execution.

## Decision 4: Capability-scoped readiness

Artifact states:

```text
READY | STALE | MISSING | INVALID
```

Action states:

```text
REUSED | SKIPPED | SUCCESS | FAILED | BLOCKED
```

Protocol states:

```text
READY | DEGRADED | ACCEPTED | PENDING | UNAVAILABLE | FAILED
```

### `PRICE_ANALYSIS`

Requires canonical symbol identity and valid canonical OHLCV with configured history, effective-session coverage, acceptable quality and no unresolved true gap.

Benchmark, feature and score evidence are optional.

### `CANDIDATE_RANKING`

Additionally requires valid benchmark OHLCV, exact-date feature/relative-strength evidence, exact-date score and required lineage.

Readiness combines persisted artifact evidence with source/provider/auth/persistence policy. A gap is repairable only when an allowlisted bounded action can currently run.

## Decision 5: Read before enqueue and re-plan after claim

Interactive flow:

```text
read-only readiness
→ ready: no queue job
→ non-repairable: UNAVAILABLE
→ repairable: submit or join one goal
```

The readiness action proposal is diagnostic, not authoritative execution state. The worker re-opens the warehouse after claim and recalculates the minimum plan because earlier jobs may already have satisfied the goal.

## Decision 6: Queue runtime and joining

SQLite runtime settings are explicit:

```text
journal_mode=WAL
foreign_keys=ON
busy_timeout=<bounded configuration>
synchronous=NORMAL or stronger documented policy
```

Transactions are short; external/provider/DuckDB work never runs inside a queue transaction.

Claim ordering:

```text
priority DESC, created_at ASC
```

When an incoming request joins an existing `QUEUED` job, priority becomes the maximum of existing and incoming priority. Join escalation does not change identity.

Cancellation is administrative at job level. Wait timeout or client disconnect does not cancel shared work.

## Decision 7: Sequential worker semantics

The worker has `max_concurrency=1` and an explicit handler registry.

```text
claim
→ validate payload/version/handler
→ acquire write coordinator when required
→ re-read/re-plan
→ run ordered bounded stages
→ verify postconditions
→ close/release warehouse
→ persist terminal queue result
```

Delivery is at-least-once. A crash after a DuckDB commit but before queue completion is recovered by lease expiry, retry and persisted-evidence reuse.

Every provider/build/finalization stage has a bounded timeout. Lease duration exceeds the maximum active stage or is extended before the stage. Heartbeat occurs between stages and before long stages.

On shutdown, the worker stops claiming, finishes or rolls back at a safe boundary, persists/relinquishes lease state and exits. It never interrupts an active DuckDB transaction.

## Decision 8: Fail-fast action execution

Actions execute in dependency order. After the first failed prerequisite:

- the failed action is `FAILED`;
- dependent actions are not called and are recorded as `BLOCKED`;
- independent, explicitly safe actions may continue only when the plan declares no dependency;
- the original root cause remains the primary failure.

The initial current-symbol chain is linear and does not require a generic DAG engine.

## Decision 9: One current-symbol application operation

Public application boundary:

```text
CurrentSymbolResearchApplication.execute(request)
```

It performs:

```text
normalize
→ read readiness and close DuckDB
→ optionally submit/join
→ wait/detach without DuckDB
→ optionally reopen read-only
→ select highest allowed capability
→ run deterministic analysis only for READY/DEGRADED
→ return typed result
```

The assistant planner emits one application/tool step. It does not emit unconditional `provision → analyze` steps.

Default behavior:

```text
CLI/TUI/chat: WAIT_UP_TO 30 seconds
explicit --wait: WAIT_UNTIL_TERMINAL
explicit --no-wait: DETACH
maintenance producer: DETACH
```

## Decision 10: Maintenance is producer plus finalizer

### Producer state machine

```text
ENQUEUING → ACQUIRING → FINALIZATION_QUEUED → FINALIZING
                                         → SUCCESS|PARTIAL|FAILED
```

The producer freezes:

```text
resolved session
validated universe snapshot/hash
exact symbol set
source-policy version
calendar version
expected normalized goal identities
```

It persists expected identities before submitting jobs, persists each returned job ID, and transitions to `ACQUIRING` only when every expected goal is mapped. Retry resumes missing submissions/mappings.

Acquisition goals:

```text
VNINDEX → SYNC_DATASET_RANGE(index.ohlcv)
equities → ENSURE_CURRENT_SYMBOL(PRICE_ANALYSIS)
```

Acquisition does not build batch features, scores or watchlists.

### Finalization trigger

After a maintenance-linked acquisition job becomes terminal, the worker calls:

```text
maybe_submit_session_finalization(maintenance_run_id)
```

The operation submits or joins finalization only when every expected job is mapped and terminal. A recovery command may invoke the same idempotent operation for stranded runs.

### Finalization stages

```text
reload acquisition evidence
→ determine eligible coverage/exclusions
→ build features once
→ build score/watchlist once
→ build market/sector/group context
→ mature outcomes
→ project approved memory
→ persist final run result
```

The finalizer never changes the frozen universe and never reacquires market data.

## Decision 11: Operations and retention

Queue health reports schema/pragmas, integrity, file/WAL size, disk space, queue depth, oldest age and lease state. Invalid schema or integrity failure prevents new claims.

Active jobs are never pruned. Terminal details use bounded retention. Before pruning a job referenced by a retained maintenance run, a bounded terminal summary is retained in the DuckDB ledger or the queue row remains until run-evidence retention expires.

Recovery is non-destructive and preserves the original queue file. The system never silently recreates an empty queue after corruption.

## Decision 12: Packaging and documentation

The supported package provides:

- queue directory and permissions;
- exactly one provisioner daemon;
- maintenance producer timer disabled by default;
- queue migration/health checks;
- backup/restore of DuckDB and queue state;
- global writer lock path;
- operator commands for jobs health/status/prune/checkpoint.

Issue #279 remains acceptance-only for the earlier installer. The new queue-runtime delta is owned by #344.

## Risks and Trade-offs

### Queue and warehouse are not transactional together

Mitigation: phased idempotent producer, normalized goal identity, run-to-job mapping and authoritative warehouse re-planning.

### One worker limits throughput

Accepted for current single-host scale. Bounded jobs and priority escalation prevent an interactive request from waiting behind an unbounded maintenance job.

### Short metadata writes may contend with provisioning

They use the same coordinator. If contention becomes material, metadata storage can be split later based on measured evidence; it is not pre-optimized now.

### Exact-key deduplication misses subset/superset reuse

Accepted for MVP. Exact normalized identities are easier to reason about. Warehouse re-planning still reuses shared persisted artifacts.

## Migration Plan

1. Implement #343 and migrate connection/write call sites.
2. Implement #320 and compatibility-readiness adapters.
3. Add typed goals and SQLite repository (#338/#323).
4. Add worker and current-symbol handler (#324).
5. Convert reuse/incremental/fail-fast behavior (#318/#319/#321).
6. Replace interactive orchestration (#325/#322).
7. Convert maintenance and finalization (#326/#337).
8. Add operations and package runtime (#339/#344).
9. Reconcile docs (#340) and collect live proof (#255).

## Validation Strategy

Each issue closes only with focused tests named in `tasks.md`. Program completion additionally requires:

- OpenSpec validation on the exact final SHA;
- full repository lint/test/package gates;
- crash/failure-injection fixtures;
- single-writer concurrency tests;
- exact queue identity and priority tests;
- ten-session installed-host evidence under #255.
