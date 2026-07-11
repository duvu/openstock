# Design: Production control plane for opencode-like auto research

## Context and decision

`TuiInputRouter` already separates command, chat, status, lifecycle, and event
paths, but it needs a clear production ownership model. This design limits
Phase A to control-plane behavior. Phase D owns repair/validation/promotion
semantics and Phase A must delegate to it rather than recreate its state model.

The implementation target is `vnalpha/` in the OpenStock repository. The
feature branch/worktree is created from the repository root because root-level
`Makefile` targets are the authoritative validation interface.

## Component model

```text
Textual VnAlphaApp
  ComposerInput.ComposerSubmitted
            |
            v
  TuiInputRouter.admit_and_route()
      | fresh correlation ID + TUI_INPUT_SUBMITTED
      |
      +-- busy/closing ----> TUI_INPUT_REJECTED + inline warning
      |
      +-- control ---------> TUI_CONTROL_ROUTED
      |
      +-- chat ------------> ChatPath -> ChatController worker
      |                         callbacks -> SafeUiDispatcher -> app loop
      |
      +-- research command -> CommandPath -> CommandExecutor (owned DuckDB)
      |
      +-- operational -----> OperationalCommandBridge -> existing domain action
                                  (Phase D semantics/gates remain there)
```

`OutputStream` remains the only output destination. The responsive TODO rail is
not a command surface and does not change the single-composer invariant.

## Router state and DuckDB lifetime

The router owns a single command connection and uses a small explicit state
machine:

```text
ACCEPTING --submission--> ACTIVE --route finally--> ACCEPTING
    |                         |
    | close()                 | close()
    v                         v
CLOSING -----------------> CLOSED
             (after active route exits and connection closes once)
```

Implementation details:

1. `LifecycleHooks.setup_executor()` opens `get_connection()`, runs migrations,
   and returns the connection plus `CommandExecutor(conn, surface="tui",
   default_date=target_date)`.
2. The setup result also carries a safe failure detail. A partial connection is
   closed in the same failure path.
3. Router admission is decided synchronously before the route first awaits;
   an active submission marks the router busy and a second one is rejected.
   This provides one connection consumer without a queue or stale-command
   backlog.
4. `close()` is idempotent. It marks the router closing and either closes an
   idle connection immediately or lets the active route close it in its
   `finally` block. It never closes a connection currently used by
   `anyio.to_thread.run_sync`.
5. `/approve`, `/cancel`, and `/clear` are local controls only when idle. They
   are not general execution cancellation in Phase A and are rejected while an
   active route could otherwise race with `ChatController`.

This is intentionally simpler than a queue or cancellable job manager; those
belong to later automation phases.

## Submission identity and lifecycle

The router creates a new correlation ID for every non-empty input, including a
busy-rejected input. It does this before it renders user input, writes an audit
event, or submits worker work. The ID is therefore captured by the async/thread
context and used by all resulting observability writes.

| Input outcome | Required ordered events |
|---|---|
| accepted slash/operational success | `TUI_INPUT_SUBMITTED` → `TUI_COMMAND_ROUTED` → `COMMAND_STARTED` → `COMMAND_SUCCEEDED` |
| returned `FAILED` / `VALIDATION_ERROR` | `TUI_INPUT_SUBMITTED` → `TUI_COMMAND_ROUTED` → `COMMAND_STARTED` → `COMMAND_FAILED` |
| raised command/domain exception | same route/start sequence → `COMMAND_FAILED` plus captured error |
| accepted chat | `TUI_INPUT_SUBMITTED` → `TUI_CHAT_ROUTED` → existing chat lifecycle |
| accepted control | `TUI_INPUT_SUBMITTED` → `TUI_CONTROL_ROUTED` |
| busy/closing rejection | `TUI_INPUT_SUBMITTED` → `TUI_INPUT_REJECTED` |
| command setup unavailable | submitted/routed → `TUI_COMMAND_SETUP_FAILED`; no command start |
| render failure | `TUI_RENDER_ERROR` plus captured error |

The existing `command_lifecycle()` helper treats a normal context exit as
success, which is insufficient for a `CommandResult(status=FAILED)` returned
by `CommandExecutor`. The implementation will add a result-aware terminal
writer (or use explicit start/success/failure calls) so status determines the
terminal event, not merely Python exception control flow.

All audit summaries use input type and length, never raw input. Command output,
failure details, and exception text use the existing redaction layer before
persistence.

## Operational bridge contract

The bridge recognizes only these exact token sequences:

```text
/logs errors --latest
/logs summarize --latest
/repair prepare --latest
/repair status <repair-id>
/deploy verify <candidate>
/deploy promote <candidate> --deployment-id <id>
/deploy rollback <deployment-id>
```

`<repair-id>`, `<candidate>`, and `<id>` are opaque identifiers matching
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. They cannot contain slashes, whitespace,
shell quoting, traversal segments, or extra options. Parsing remains tokenized
with `shlex`, then validates each token before it reaches a domain action.

`--latest` is not a path argument. At action start the bridge resolves the
current latest-run pointer once and passes the resolved run identity through
the action. This makes a single invocation stable if another run is created
after execution begins.

The bridge has no promotion logic. It delegates verify/promote/rollback to the
existing observability/Phase D domain functions. A Phase D validation-gate
failure is displayed and logged as a command failure; the TUI cannot force or
bypass it. `candidate` is metadata only and is never interpolated into a shell
command.

## Safe Textual dispatch

`ChatController.handle_turn()` runs in a worker path. Its assistant message,
trace, warning, and error callbacks may only call a dispatcher supplied by
`VnAlphaApp`:

```text
worker callback
  -> LifecycleHooks.dispatch_ui(callback)
  -> app safe dispatcher
  -> Textual call_from_thread / app message loop
  -> OutputStream and StatusBar mutation
```

There is no direct-widget fallback for worker-originated callbacks. If no
dispatcher exists or the app has started unmounting, the callback is dropped
and recorded with redacted evidence. App unmount disables future dispatch before
requesting router close, preventing late callbacks from mutating unmounted
widgets.

## Error handling and degraded mode

| Failure | User-facing behavior | Evidence |
|---|---|---|
| executor setup failure | command-degraded inline message; chat remains usable | captured exception + `TUI_COMMAND_SETUP_FAILED` |
| invalid operational grammar/ID | inline unsupported/invalid message | `COMMAND_FAILED`, redacted arguments |
| returned command failure | rendered result/failure block | `COMMAND_FAILED` with result status |
| raised route/domain failure | redacted error block | `COMMAND_FAILED` + `capture_exception()` |
| busy/closing input | inline warning | `TUI_INPUT_REJECTED` |
| late worker callback | no widget write | redacted render-drop/error evidence |

## Read-only research boundary

Allowed writes are bounded local evidence: JSONL logs, workspace context,
repair bundles, and research-artifact state already owned by the domain layer.
The router may not execute arbitrary user strings as shell commands, write
source files, operate Git/GitHub, remotely deploy services, or access broker,
order, account, portfolio, margin, transfer, allocation, or trading systems.

## Test strategy

Tests are added before production changes and use an in-memory DuckDB or
isolated temporary roots. They cover:

1. real executor setup, setup failure, and exactly-once/deferred close;
2. one active route and deterministic busy/closing rejection;
3. fresh correlation propagation and truthful returned-result/exception
   terminal lifecycle;
4. all seven operational forms, invalid grammar/IDs, latest-run stability, and
   Phase D gate blocks;
5. worker-safe callback dispatch including a late post-unmount callback;
6. DOM invariants and secret scanning across audit/command/error evidence.

Full validation runs from the repository root with:

```bash
export VNALPHA_WAREHOUSE_PATH="/tmp/openstock-prod-a-control-plane.duckdb"
export VNALPHA_LOG_ROOT="/tmp/openstock-prod-a-control-plane-logs"
make test-vnalpha
make lint-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

## Alternatives considered

### Queue every composer submission

Rejected for Phase A. A queue makes command freshness, cancel semantics, and
shutdown materially more complex and can execute stale research commands.
Deterministic rejection is safer until a later job manager owns cancellation.

### Create a new DuckDB connection per command

Rejected. It obscures router ownership, repeats migration/setup work, and makes
shutdown/error behavior harder to reason about. One serialized router-owned
connection matches the existing command executor contract.

### Let missing UI dispatcher invoke widgets directly

Rejected. It recreates the cross-thread failure this change fixes. A dropped,
logged late callback is safer than an unmounted or cross-thread widget write.
