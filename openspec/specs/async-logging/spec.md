# async-logging Specification

## Purpose
TBD - created by archiving change async-logging-debug-system. Update Purpose after archive.
## Requirements
### Requirement: Logging module initialisation
The system SHALL expose a `configure_logging(level: str, log_path: Path | None)` function
in `vnalpha.logging` that sets up `structlog` with a `QueueHandler`-backed
`RotatingFileHandler` (10 MB × 5) and a colored stderr handler. It SHALL be idempotent
(safe to call multiple times). The default log level SHALL be read from the
`VNALPHA_LOG_LEVEL` env var (default `INFO`). The default log path SHALL be read from
`VNALPHA_LOG_PATH` (default `~/.local/share/openstock/logs/vnalpha.log`).

#### Scenario: Default initialisation
- **WHEN** `configure_logging()` is called with no arguments
- **THEN** a rotating file handler is attached at the default path and a colored stderr handler is attached

#### Scenario: Env var override
- **WHEN** `VNALPHA_LOG_LEVEL=DEBUG` is set and `configure_logging()` is called
- **THEN** DEBUG-level records appear in both stderr and the log file

#### Scenario: Idempotent call
- **WHEN** `configure_logging()` is called twice in the same process
- **THEN** no duplicate handlers are added and no exception is raised

---

### Requirement: Logger factory
The system SHALL expose `get_logger(name: str) -> BoundLogger` returning a `structlog`
bound logger. Every record emitted SHALL include `timestamp`, `level`, `logger`, and
`event` fields. Key=value context can be bound with `logger.bind(key=value)`.

#### Scenario: Module-level logger
- **WHEN** a module calls `logger = get_logger(__name__)` and `logger.info("msg", key="val")`
- **THEN** the record appears in the log file with `logger=<module>`, `level=info`, `event=msg`, `key=val`

#### Scenario: Error with exception
- **WHEN** `logger.error("failed", exc_info=True)` is called inside an except block
- **THEN** the log file record includes the exception traceback

---

### Requirement: Correlation ID propagation
The system SHALL maintain a `ContextVar[str]` correlation ID. It SHALL be automatically
set to a new UUID at the start of each CLI command handler and each TUI command dispatch.
Every log record emitted within that context SHALL include `correlation_id=<uuid>`.

#### Scenario: CLI command correlation
- **WHEN** `vnalpha sync symbols` is run
- **THEN** every log record produced during that invocation shares the same `correlation_id`

#### Scenario: Async task inheritance
- **WHEN** an `asyncio.Task` is spawned inside a coroutine that has a correlation ID set
- **THEN** the child task's log records carry the same `correlation_id`

---

### Requirement: Async-safe file writing
The system SHALL use `logging.handlers.QueueHandler` / `QueueListener` so file writes
occur on a background thread and never block the asyncio event loop.

#### Scenario: High-frequency async logging
- **WHEN** 1000 log calls are made from async code in rapid succession
- **THEN** the asyncio event loop is not blocked and all records eventually appear in the file

---

### Requirement: CLI log viewer
The system SHALL provide a `vnalpha log` subcommand with:
- `--level` filter (DEBUG/INFO/WARNING/ERROR, default ALL)
- `--since` filter (ISO datetime or relative like `1h`, `30m`)
- `--grep` substring filter on the `event` field
- `--tail N` to show the last N lines (default 50)

Output SHALL be human-readable with colored level labels.

#### Scenario: Filter by level
- **WHEN** `vnalpha log --level ERROR` is run
- **THEN** only ERROR-level records are printed

#### Scenario: Filter by time
- **WHEN** `vnalpha log --since 1h` is run
- **THEN** only records from the last 60 minutes are printed

#### Scenario: Tail lines
- **WHEN** `vnalpha log --tail 10` is run
- **THEN** only the last 10 matching log lines are printed

---

### Requirement: TUI Log Viewer screen
The system SHALL add a `LogScreen` to the Textual `ContentSwitcher` workspace, accessible
via the `L` key binding. The screen SHALL tail the live log file and display new records
in real time (≤1 s latency). It SHALL offer level filter buttons (ALL / DEBUG / INFO /
WARNING / ERROR) rendered above the log display. The log display SHALL use `RichLog` with
color-coded level labels.

#### Scenario: Open log viewer
- **WHEN** the user presses `L` in the TUI workspace
- **THEN** the Log Viewer screen is displayed showing recent log entries

#### Scenario: Level filter
- **WHEN** the user activates the WARNING filter button
- **THEN** only WARNING and ERROR records are displayed

#### Scenario: Live tail
- **WHEN** a new log record is written to the file while the Log Viewer is open
- **THEN** the new record appears in the viewer within 1 second

---

### Requirement: Replace print and bare logging calls
All existing `print()` calls in `vnalpha` source (excluding test output helpers) SHALL be
replaced with appropriate `logger.<level>()` calls. The `T201` ruff lint rule (ban print)
SHALL be enabled in `pyproject.toml` to prevent regressions.

#### Scenario: No print statements in production code
- **WHEN** `ruff check vnalpha/` is run
- **THEN** no T201 violations are reported

