## Context

The repository already has deterministic provisioning/build services, typed
provider outcomes, point-in-time context builders, structured memory and Debian
packaging. They are currently invoked through several user and legacy surfaces,
while daily operation, scheduling and release acceptance require one bounded
orchestrator. GitHub issue #238 owns dependency order; the warehouse and tool
results remain authoritative over memory and model prose.

## Goals / Non-Goals

**Goals:**

- resolve one effective Vietnam market session and one correlation identity;
- run symbol snapshot, incremental OHLCV, benchmark, gap, canonical, feature,
  score, market/group context and selective memory stages in order;
- isolate per-symbol/provider failures and report truthful aggregate status;
- make dry-run, non-session and repeated execution mutation-safe;
- ship an explicit-timezone, disabled-by-default timer with stable locking;
- prove the exact package/commit on a prepared clean-host fixture before closure.

**Non-Goals:**

- replacing deterministic application services with assistant orchestration;
- autonomous assistant data provisioning;
- generic workflow engines, arbitrary group ontologies or vector memory;
- broker, order, account, portfolio, allocation, margin, transfer or execution;
- enabling scheduled work during package installation or upgrade.

## Decisions

1. A Typer `maintain daily` command calls one application service and emits a
   versioned result. Reusing the existing provisioning facade keeps CLI, TUI,
   assistant, readiness and packaged semantics aligned. A shell chain was
   rejected because it loses typed per-symbol outcomes and stage correlation.

2. Explicit non-session dates return `NOOP` without opening the persistent
   warehouse. This prevents surprising mutation and makes catch-up behavior
   deliberate. A versioned Vietnam session calendar owns weekday and holiday
   semantics.

3. Fresh canonical rows and same-date source snapshots are reused. Stale or
   missing symbols alone proceed downstream; failed symbols are isolated and
   successful symbols continue. Overall `PARTIAL` is distinct from `FAILED` and
   exits 3 for systemd while remaining visible in JSON.

4. Memory projection runs only from persisted validated artifacts. Symbol
   projection stores material classification/setup/taxonomy changes; entity
   projection uses MARKET, SECTOR, INDUSTRY and ASSET_CLASS identities. Repeated
   equivalent snapshots create neither claims nor card generations.

5. Debian installs service and timer units under `/usr/lib/systemd/system` but
   never enables or starts them. The timer owns `[Install]`; the oneshot service
   does not. `flock` uses one stable `/run/openstock-pipeline.lock` inode, and
   lock contention exits 75.

6. The root README and ROADMAP point to #238; component documents link there
   rather than duplicating priority. Historical documents carry an explicit
   non-authoritative banner, and repository consistency rejects #90/#209 live
   pointers even if #238 is also present.

7. Closure requires a report generated from the exact candidate package and
   commit. Focused or local tests are diagnostic until the full root gates,
   package install, real command paths, repeated execution, failure injection
   and research-only boundary checks are recorded.

## Risks / Trade-offs

- [Provider outage creates a mixed run] → isolate failed symbols, preserve typed
  diagnostics and return `PARTIAL` without fabricating readiness.
- [A holiday table becomes stale] → version it, test known closures and disclose
  unsupported dates rather than silently treating every weekday as open.
- [Two writers corrupt DuckDB] → acquire one external stable lock for the whole
  packaged invocation and retain internal transaction boundaries.
- [Derived memory outranks fresh evidence] → revalidate sources, enforce expiry
  and keep retrieval language explicitly non-authoritative.
- [Package install changes operator state] → daemon-reload only; never enable or
  start the timer in maintainer scripts.
- [Clean-host fixtures overstate live-provider proof] → label fixture and live
  lanes separately and close only with the evidence the issue requires.

## Migration Plan

1. Apply additive warehouse migrations and backfill existing memory rows as
   `SYMBOL` entities without changing symbol command behavior.
2. Install package units disabled and reload systemd.
3. Run `vnalpha maintain daily --dry-run --json`, then an explicit manual run.
4. Enable the timer only through an operator command after verification.
5. Roll back by disabling the timer and reinstalling the previous package; the
   warehouse and knowledge roots are never removed.

## Open Questions

None for implementation. Exact commit/package identity and live-provider
availability remain validation evidence, not design assumptions.
