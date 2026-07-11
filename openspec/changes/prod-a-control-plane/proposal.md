# Proposal: Production control plane for opencode-like auto research

## Summary

Harden the default `vnalpha` opencode-like TUI into the production control
plane for OpenStock's read-only research workflow.

```text
single composer
  -> admission and correlation
  -> control | chat | research command | operational bridge
  -> bounded execution
  -> safe inline rendering
  -> redacted evidence
```

This is **Phase A: Foundation / Control Plane**. It owns TUI routing,
connection lifetime, admission control, UI-thread dispatch, and observability
glue. It does not own the repair, validation, promotion, or rollback domain
state machines; those remain Phase D (`prod-d-closed-loop-repair`) concerns.

## Review outcome

The original change had four production blockers:

- it had no `design.md` despite shared DuckDB, worker, and observability
  lifetimes;
- proposal/tasks required seven operational forms while the normative delta
  specified only five;
- a lifecycle context manager could report a returned `FAILED` or
  `VALIDATION_ERROR` result as `COMMAND_SUCCEEDED`;
- a single composer did not specify single-flight, shutdown, correlation, or
  post-unmount callback behavior.

This revision resolves those gaps before implementation. The implementation
target is `vnalpha/` in the OpenStock repository; root-level `make` targets
are the authoritative validation interface.

## Why

The visual TUI refactor already provides the intended composer and output
stream, but production safety requires a deterministic control plane:

- `TuiInputRouter` must construct `CommandExecutor` with its real DuckDB
  contract and retain exactly one owned connection.
- A second submission must never concurrently use that connection or mutate a
  `ChatController` while another turn is running.
- `/logs`, `/repair`, and `/deploy` need a strict TUI grammar and a bridge
  that does not fall through to the research command registry.
- Every accepted, rejected, failed, and rendered outcome must be reconstructible
  using a fresh correlation ID without persisting secrets.
- Worker callbacks must not mutate Textual widgets after the app unmounts.

## Goals

- Construct `CommandExecutor(conn, surface="tui", default_date=target_date)`
  after migrations and retain its router-owned DuckDB connection.
- Make command setup failures observable and actionable while leaving chat
  available in degraded command mode.
- Serialize router submissions with deterministic busy rejection and safe,
  exactly-once deferred connection shutdown.
- Bridge all seven documented operational forms before generic slash-command
  routing, while delegating their domain semantics to the existing
  observability/Phase D layer.
- Create one fresh correlation ID for every non-empty submission and emit a
  truthful lifecycle for success, returned failure, thrown failure, control,
  and busy-rejected outcomes.
- Preserve redaction-by-default at input, event, error, result, and repair
  bundle persistence boundaries.
- Marshal worker callbacks through a live Textual dispatcher only.
- Preserve the single default `OutputStream` and `ComposerInput` model.
- Add focused regression coverage and reproducible validation evidence.

## Non-goals

- No sandbox compute, autonomous research loops, or arbitrary code execution.
- No implementation of repair proposal, repair retry, validation-gate, promotion,
  or rollback state machines. Phase A only invokes their existing domain entry
  points and reports their result.
- No broker, order, account, portfolio, margin, transfer, allocation, or
  trading execution capability.
- No remote deployment, source-tree editing, Git/GitHub mutation, or
  user-supplied shell command execution through `/deploy` or `/repair`.
- No reintroduction of `ContentSwitcher` or a persistent secondary `ChatPanel`
  in the default TUI path.
- No unrelated rewrite of scoring, watchlist, quality, lineage, notes, repair,
  or deploy domain logic.

## Scope

### Router ownership and admission

`TuiInputRouter` is the production router for the default TUI path. It owns one
DuckDB command connection, creates the command executor after migrations, and
accepts at most one active route at a time. A non-empty submission made while
busy or closing is rendered as a redacted inline warning, logged as
`TUI_INPUT_REJECTED`, and must not start a second command, chat turn, or
operational action.

`/approve`, `/cancel`, and `/clear` remain local control actions. They are not
execution cancellation primitives in Phase A; while an execution is active,
they follow the same deterministic rejection policy rather than mutating a
controller concurrently.

On shutdown the router stops accepting work. If a route is active, it defers
connection close until that route exits; otherwise it closes immediately. Both
paths are idempotent and must close the owned connection exactly once.

### Operational command bridge

The composer supports exactly these forms before generic research slash-command
dispatch:

```text
/logs errors --latest
/logs summarize --latest
/repair prepare --latest
/repair status <repair-id>
/deploy verify <candidate>
/deploy promote <candidate> --deployment-id <id>
/deploy rollback <deployment-id>
```

`--latest` resolves one run pointer at operational-execution start and the
chosen path is used for that entire action. Identifiers are opaque,
allowlisted-format references, never paths or shell fragments. Unsupported or
invalid forms render a clear inline error and retain lifecycle evidence.

`/deploy` means only research-artifact verification, promotion, and rollback.
Phase A must not bypass any Phase D validation or promotion gate; it simply
bridges to the domain operation and renders the redacted domain outcome.

### Observability and privacy

Each non-empty submission receives a fresh correlation ID before any audit,
render, worker dispatch, or route decision. The ID propagates into command,
chat, operational, trace, error, and callback evidence for that submission.

Slash-command lifecycle is truthful:

```text
TUI_INPUT_SUBMITTED
  -> TUI_COMMAND_ROUTED
  -> COMMAND_STARTED
  -> COMMAND_SUCCEEDED | COMMAND_FAILED
```

`FAILED` and `VALIDATION_ERROR` command results are failures, even when the
executor returns normally. A raised exception is also a failure and is captured
through `capture_exception()`. Control and busy-rejected submissions have their
own route/rejection events and never emit `COMMAND_STARTED`.

Raw input, arguments, exception text, output tails, and bundle material are
redacted before persistence. Local writes to audit logs, repair bundles, and
research-artifact state are allowed; they do not relax the read-only research
boundary.

### Thread-safe rendering

All assistant message, trace, warning, and error callbacks that originate from
a worker use the app-provided Textual dispatcher. If the dispatcher is absent,
inactive, or the app has unmounted, the callback is dropped and recorded safely;
it must never fall back to direct widget mutation.

## Success criteria

This change is complete only when:

- `vnalpha tui` mounts one `OutputStream`, one `ComposerInput`, exactly one
  Textual `Input`, no default `ContentSwitcher`, and no persistent default
  `ChatPanel`.
- `/help` uses a real migrated `CommandExecutor` setup and renders inline.
- All seven documented operational forms bypass the research executor and
  preserve Phase D gates.
- Invalid IDs, unsupported grammar, and busy submissions do not invoke domain
  actions or an executor.
- A returned `FAILED` or `VALIDATION_ERROR` result emits `COMMAND_FAILED`, not
  `COMMAND_SUCCEEDED`.
- A raised exception produces inline redacted error output, error evidence, and
  `COMMAND_FAILED` with the submission correlation ID.
- Concurrent submissions do not share the DuckDB connection, and shutdown never
  closes it while the active route still uses it.
- Worker callbacks render only through the app loop and are harmless after
  unmount.
- No persisted fixture secret appears in command, audit, error, trace, or
  repair-bundle evidence.
- The read-only research boundary is preserved.

## Validation commands

Run from the OpenStock repository root in the feature worktree, with isolated
state so the checks do not touch an operator's live workspace:

```bash
export VNALPHA_WAREHOUSE_PATH="/tmp/openstock-prod-a-control-plane.duckdb"
export VNALPHA_LOG_ROOT="/tmp/openstock-prod-a-control-plane-logs"
make test-vnalpha
make lint-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

The change must also record targeted TUI command/lifecycle test output in its
validation evidence before it is marked complete.

## Production boundary

This phase may route read-only research commands and write bounded local
observability, repair-bundle, and research-artifact metadata. It shall not
create or route broker, order, account, portfolio, margin, transfer,
allocation, trading execution, arbitrary shell, source-edit, Git, GitHub, or
remote deployment actions.
