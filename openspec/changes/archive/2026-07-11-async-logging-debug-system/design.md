## Context

`vnalpha` currently has no coherent logging infrastructure. Diagnostic output is a mix of
`print()` calls, bare `logging.basicConfig()` at module level, and occasional
`rich.console.Console().print()` for TUI output. There is no persistent log file, no
structured fields, and no way to revisit past activity. When an async sync job silently
fails or the TUI crashes after the terminal scrolls, there is no way to diagnose it after
the fact.

The codebase already uses `structlog` as a transitive dependency (via `rich`-ecosystem
packages). Python's `logging` module supports async-safe handlers out of the box when
configured correctly. `structlog` wraps stdlib `logging` and adds structured key=value
context processors.

## Goals / Non-Goals

**Goals:**
- Single `get_logger(name)` call site; every module uses it the same way.
- All log records persisted to a rotating file (`max 10 MB × 5 backups`).
- Colored, human-readable output to stderr in dev; JSON-structured lines in the file.
- Async-safe: log calls from `asyncio` tasks and Textual workers must not block or
  deadlock.
- Correlation ID propagated automatically through each CLI invocation / TUI command so
  all records from one operation can be filtered together.
- `vnalpha log` CLI subcommand: tail, filter by level, filter by time window, grep by text.
- TUI Log Viewer screen (workspace switcher `L` key) that live-tails the log file with
  level filter buttons.
- `VNALPHA_LOG_LEVEL` and `VNALPHA_LOG_PATH` env vars for operator control.

**Non-Goals:**
- Centralized log aggregation (no remote sink — logs are local-only).
- Log encryption or access control.
- Replacing `vnstock`-service logging (separate process, separate concern).
- Structured tracing / spans (OpenTelemetry is out of scope).

## Decisions

### D1: structlog over stdlib logging directly

**Decision**: Use `structlog` as the front-end logger factory; use stdlib `logging` as the
back-end (handler chain) so third-party libraries route through the same system.

**Rationale**: `structlog` gives us key=value context fields and processor pipelines
(timestamp → level → event → JSON/colored) with minimal boilerplate. Stdlib `logging` as
back-end means `logging.getLogger("httpx")` and `logging.getLogger("duckdb")` also land
in our file handler — one destination for all records.

**Alternative considered**: `loguru` — simpler API but harder to bridge third-party stdlib
loggers; no processor pipeline model.

### D2: Rotating file handler with `QueueHandler` for async safety

**Decision**: Wrap the file `RotatingFileHandler` in a `logging.handlers.QueueHandler` /
`QueueListener` pair so file I/O never happens on the asyncio event loop thread.

**Rationale**: Textual workers and `asyncio` tasks log frequently. A synchronous file
write on the event loop causes jitter. The queue listener drains on a background thread,
keeping the event loop unblocked.

**Alternative considered**: `asyncio`-native file logging — more complex, no stdlib
support, not worth the effort for local files.

### D3: Correlation ID via `contextvars.ContextVar`

**Decision**: Use a `ContextVar[str]` (`LOG_CORRELATION_ID`) set at the start of each CLI
invocation and each TUI command dispatch. The `structlog` processor reads it and injects
`correlation_id=<uuid>` into every record.

**Rationale**: `ContextVar` propagates automatically across `asyncio.Task` children
spawned within the same context, so a sync job and all its sub-tasks share the same
correlation ID without manual threading.

### D4: Log Viewer TUI screen tails the file, not an in-memory buffer

**Decision**: The TUI `LogScreen` reads the log file and tails it using a `Worker` that
polls via `asyncio.sleep(0.5)`. It does not maintain an in-memory ring buffer.

**Rationale**: Decouples the log viewer from the logging pipeline (no shared state). File
already exists; tail semantics are simple. Textual's `RichLog` widget handles the display.

**Alternative considered**: In-memory queue consumed by TUI — would lose logs from before
TUI was opened; more complex lifecycle.

### D5: Log format — colored text to stderr, JSON to file

**Decision**: stderr → `structlog.dev.ConsoleRenderer` (colored). File → JSON lines via
`structlog.processors.JSONRenderer`.

**Rationale**: Developers see readable colored output; the file is machine-parseable so
`vnalpha log` can filter efficiently with `json.loads()` per line.

## Risks / Trade-offs

- **Risk**: QueueHandler fills under extreme log volume → Mitigation: default queue size
  is `maxsize=0` (unbounded); add a warning log if queue depth exceeds 10k.
- **Risk**: Log file grows too fast if DEBUG is left on → Mitigation: default level is
  INFO; file rotates at 10 MB × 5 backups (~50 MB max).
- **Risk**: TUI log viewer file-tail polling introduces 0.5 s latency → Mitigation:
  acceptable for a debug viewer; user can reduce interval via env var if needed.
- **Risk**: Migration of existing `print()` calls misses some paths → Mitigation: `ruff`
  lint rule `T201` (ban `print`) added to `pyproject.toml`; CI will catch regressions.

## Migration Plan

1. Add `structlog` explicitly to `pyproject.toml` dependencies.
2. Create `vnalpha/logging.py` with `configure_logging()` and `get_logger()`.
3. Call `configure_logging()` once at each CLI entry point and TUI `on_mount`.
4. Replace `print()` / `logging.basicConfig()` calls module by module (covered in tasks).
5. Add `T201` ruff rule.
6. Add `vnalpha log` command.
7. Add TUI `LogScreen` and wire into `ContentSwitcher`.

**Rollback**: Remove the `vnalpha/logging.py` module and revert `pyproject.toml`. No
schema changes, no migrations. Log files left in place are harmless.

## Open Questions

- None blocking implementation.
