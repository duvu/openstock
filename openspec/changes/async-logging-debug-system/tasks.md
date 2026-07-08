## 1. Foundation — logging module

- [x] 1.1 Add `structlog` to `vnalpha/pyproject.toml` explicit dependencies (if not already present)
- [x] 1.2 Create `vnalpha/src/vnalpha/logging.py` with `configure_logging(level, log_path)` — sets up `QueueHandler`+`QueueListener` around `RotatingFileHandler` (10 MB × 5) and a colored stderr `StreamHandler` via `structlog`
- [x] 1.3 Implement `get_logger(name) -> BoundLogger` factory in `vnalpha/logging.py` — returns a `structlog` bound logger with timestamp, level, logger, event processors
- [x] 1.4 Implement correlation ID `ContextVar` in `vnalpha/logging.py` — `set_correlation_id()` generates a UUID and stores it; `structlog` processor injects `correlation_id` into every record
- [x] 1.5 Write unit tests `vnalpha/tests/test_logging.py` — covers configure_logging idempotency, get_logger output fields, correlation ID propagation across asyncio tasks

## 2. CLI entry-point wiring

- [x] 2.1 Call `configure_logging()` at the start of `vnalpha/src/vnalpha/cli/main.py` (the Typer app callback) — reads `VNALPHA_LOG_LEVEL` and `VNALPHA_LOG_PATH` env vars
- [x] 2.2 Call `set_correlation_id()` at the start of each CLI command handler (sync, build, score, watchlist, outcome, cmd, ask, init) to bind a fresh UUID per invocation
- [x] 2.3 Write test that calling `vnalpha init` emits at least one log record to the file with the expected fields

## 3. Replace print / bare logging calls — core modules

- [x] 3.1 Replace all `print()` and bare `logging.*` calls in `vnalpha/src/vnalpha/warehouse/` with `get_logger(__name__)` calls at appropriate levels
- [x] 3.2 Replace all `print()` / `logging.*` calls in `vnalpha/src/vnalpha/sync/` modules
- [x] 3.3 Replace all `print()` / `logging.*` calls in `vnalpha/src/vnalpha/features/` modules
- [x] 3.4 Replace all `print()` / `logging.*` calls in `vnalpha/src/vnalpha/scoring/` modules
- [x] 3.5 Replace all `print()` / `logging.*` calls in `vnalpha/src/vnalpha/outcomes/` modules
- [x] 3.6 Replace all `print()` / `logging.*` calls in `vnalpha/src/vnalpha/assistant/` and `vnalpha/src/vnalpha/chat/` modules

## 4. Enable ruff T201 lint rule

- [x] 4.1 Add `"T201"` to the `ruff` `select` list in `vnalpha/pyproject.toml` (ban `print` in production code)
- [x] 4.2 Add `# noqa: T201` or move to test helpers any legitimate `print` calls that must remain (e.g., TUI test output)
- [x] 4.3 Run `make lint-vnalpha` and confirm zero T201 violations

## 5. `vnalpha log` CLI subcommand

- [x] 5.1 Create `vnalpha/src/vnalpha/cli/commands/log.py` with Typer `log` command — options: `--level`, `--since`, `--grep`, `--tail`
- [x] 5.2 Implement log file reader: reads JSON lines, parses timestamp, applies level/time/grep filters, pretty-prints with colored level labels using `rich`
- [x] 5.3 Register the `log` command in `vnalpha/src/vnalpha/cli/main.py`
- [x] 5.4 Write tests `vnalpha/tests/test_cli_log.py` — covers filter by level, filter by `--since`, `--grep` substring, `--tail N`

## 6. TUI Log Viewer screen

- [x] 6.1 Create `vnalpha/src/vnalpha/tui/screens/log_viewer.py` with `LogScreen(Screen)` — uses `RichLog` for display, level filter buttons (`ALL`/`DEBUG`/`INFO`/`WARNING`/`ERROR`), a Textual `Worker` that polls the log file every 0.5 s and appends new lines
- [x] 6.2 Add `set_correlation_id()` call in `vnalpha/src/vnalpha/tui/widgets/command_input.py` (or command dispatch path) so each TUI command gets a fresh correlation ID
- [x] 6.3 Wire `LogScreen` into `vnalpha/src/vnalpha/tui/app.py` — add `"log"` to the `ContentSwitcher`, bind `L` key to switch to it
- [x] 6.4 Write pilot test `vnalpha/tests/test_tui_log_viewer.py` — covers mount without crash, level filter button click changes displayed records, `L` key binding activates the screen

## 7. Final validation

- [x] 7.1 Run `make test-vnalpha` — all tests pass (773+ passed, 0 failures in new tests)
- [x] 7.2 Run `make lint-vnalpha` — zero violations including T201
- [x] 7.3 Smoke test: `vnalpha sync symbols` → `vnalpha log --level INFO --tail 20` shows sync activity records
- [x] 7.4 Smoke test: launch TUI → press `L` → Log Viewer screen opens and shows live entries
- [x] 7.5 Update `openspec/changes/async-logging-debug-system/tasks.md` to mark all tasks complete
