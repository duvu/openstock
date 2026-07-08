## Why

`vnalpha` has no persistent, queryable log trail. When a command fails, a background sync
stalls, or the TUI misbehaves, the only visibility is whatever scrolled past in the
terminal. There is no way to review past errors, filter by severity, or correlate activity
across async tasks. This change adds a structured, async-safe logging subsystem so every
activity (DEBUG → INFO → WARNING → ERROR) is captured, persisted, and inspectable.

## What Changes

- New `vnalpha.logging` package provides a `get_logger()` factory that returns a
  `structlog`-backed logger wired to both a stderr sink (colored for dev) and a
  rotating file sink under `~/.local/share/openstock/logs/`.
- All existing `print()` / bare `logging` calls in CLI, TUI, warehouse, sync, and outcome
  modules are replaced with structured logger calls (`logger.debug`, `.info`, `.warning`,
  `.error`) with key=value context fields.
- A `vnalpha log` CLI subcommand reads and filters the persisted log file — by level,
  time range, or substring — and pretty-prints results to the terminal.
- The TUI gets a **Log Viewer** screen (accessible via the `L` key binding in the workspace
  switcher) that tails the live log file with level-based filtering.
- Async tasks (sync workers, feature builders, pipeline steps) bind a correlation ID to
  each log record so all records from one run can be grouped.

## Capabilities

### New Capabilities

- `async-logging`: Structured, async-safe log capture via `structlog` with rotating file
  persistence, level filtering, correlation IDs, and a CLI/TUI viewer.

### Modified Capabilities

<!-- No existing spec-level requirements change — this is additive infrastructure. -->

## Impact

- **vnalpha package**: adds `vnalpha/logging.py` (or `vnalpha/logging/` package) and
  `vnalpha/cli/commands/log.py`. Touches every module that currently uses `print()` or
  the stdlib `logging` root logger.
- **TUI**: adds `LogScreen` to the `ContentSwitcher` workspace; minor change to `app.py`
  key bindings.
- **Dependencies**: `structlog` added to `pyproject.toml` (already a transitive dep via
  `textual` ecosystem; may already be present). No new runtime deps beyond that.
- **Config**: `VNALPHA_LOG_LEVEL` env var (default `INFO`) and `VNALPHA_LOG_PATH` env var
  (default `~/.local/share/openstock/logs/vnalpha.log`) for operator control.
- **Packaging**: log directory created by `postinst` / `openstock-verify`.
