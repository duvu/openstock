# vnalpha TUI — opencode-like Chat-First Workspace

> Developer and operator reference for the refactored single-pane TUI.

---

## Overview

The `vnalpha tui` command launches an opencode-style workspace with a vertical stack layout:

```
┌────────────────────────────────────────────────────────────────┐
│  StatusBar (id="status-bar")  height=1                         │
├────────────────────────────────────────────────────────────────┤
│  OutputStream (id="output-stream")                             │
│  Append-only. All output — assistant messages, command        │
│  results, tool traces, errors, warnings — renders here.       │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  ComposerInput (id="composer-input")  height=3                 │
│  > Ask or run /command ...                                     │
├────────────────────────────────────────────────────────────────┤
│  FooterHint (id="footer-hint")  height=1                       │
│  Enter submit · ↑/↓ history · Ctrl+L clear · /help · Esc      │
└────────────────────────────────────────────────────────────────┘
```

No screen switcher. No secondary chat panel. One input, one output stream.

---

## Input Routing Rules

`TuiInputRouter` routes every submitted text according to these rules (evaluated top-to-bottom):

| Input | Action |
|-------|--------|
| (empty) | No-op |
| `/clear` | `OutputStream.clear_visible()` — visible output only, no audit log deletion |
| `/approve` or `approve` | `ChatController.approve_pending_plan()` |
| `/cancel` or `cancel` | `ChatController.cancel_pending_plan()` |
| starts with `/` | `CommandExecutor.execute(text)` → result rendered inline |
| anything else | `ChatController.handle_turn(text)` → assistant reply rendered inline |

---

## Slash Command Examples

```
/help                        # Show available commands
/scan AAPL                   # Run stock scan
/explain SMA_CROSSOVER       # Explain a pattern
/filter ...                  # Filter watchlist
/history AAPL                # Show price history
/logs list                   # List recent run logs
/logs show <run-id>          # Show a run's events
/repair prepare --latest     # Create repair bundle from latest run
/repair status <repair-id>   # Check repair status
/deploy verify <candidate>   # Verify a deploy candidate
/deploy promote <candidate>  # Promote candidate (requires verified)
/deploy rollback <dep-id>    # Rollback a deployment
```

---

## Observability Events

Every TUI interaction emits structured events to the run's JSONL logs:

| Event | When |
|-------|------|
| `TUI_INPUT_SUBMITTED` | Any non-empty submitted input |
| `TUI_COMMAND_ROUTED` | Slash command routing |
| `TUI_CHAT_ROUTED` | Natural-language routing |
| `TUI_RENDER_ERROR` | Any render exception (also calls `capture_exception`) |
| `TUI_STARTED` | App mount |
| `TUI_HISTORY_PUSHED` | Input pushed to history (includes kind and length) |
| `TUI_HISTORY_PREVIOUS` | User navigated to previous history item |
| `TUI_HISTORY_NEXT` | User navigated to next history item |
| `TUI_HISTORY_DRAFT_RESTORED` | Draft restored after history navigation |
| `TUI_STATUS_CHANGED` | Status bar state transition |

Correlation ID is auto-assigned if not already set.

---

## Legacy Dashboard Status

The following screens are **importable but not mounted by default**:

- `HomeScreen` — `vnalpha.tui.screens.home`
- `WatchlistScreen` — `vnalpha.tui.screens.watchlist`
- `CommandScreen` — `vnalpha.tui.screens.command`
- `AssistantScreen` — `vnalpha.tui.screens.assistant`
- `RejectedScreen` — `vnalpha.tui.screens.rejected`
- `QualityScreen` — `vnalpha.tui.screens.quality`
- `OutcomeScreen` — `vnalpha.tui.screens.outcomes`
- `LogScreen` — `vnalpha.tui.screens.log_viewer`

Screen-switching bindings (`h/w/c/a/r/p/o/l`) are removed. These screens remain available for direct use via `app.push_screen()` if needed in future.

---

## Key Bindings

| Key | Action |
|-----|--------|
| `Enter` | Submit input, push to history |
| `Up` / `Ctrl+P` | Previous history item |
| `Down` / `Ctrl+N` | Next history item (restore draft past newest) |
| `q` | Quit |
| `Ctrl+L` | Clear visible OutputStream |
| `Escape` | Cancel pending plan |

---

## Input History

Shell-like input history with Up/Down navigation:

- Stores up to 500 items per session (in-memory only)
- Consecutive duplicate submissions are deduplicated
- Current draft text is preserved during navigation
- Draft restored when moving past newest history item
- Persistent history (JSONL/warehouse) deferred to future phase

---

## Status Bar

A compact 1-row bar at the top shows the current runtime state:

| State | Badge | Meaning |
|-------|-------|---------|
| IDLE | `IDLE` | No work in progress |
| READY | `READY` | Last operation completed successfully |
| ROUTING_INPUT | `ROUTING` | Processing user input |
| COMMAND_RUNNING | `RUNNING` | Executing a slash command |
| CHAT_THINKING | `THINKING` | LLM is processing a question |
| TOOL_RUNNING | `TOOL` | A research tool is executing |
| DATA_ENSURE_RUNNING | `DATA` | Checking data availability |
| DATA_SYNCING | `SYNCING` | Syncing market data |
| BUILDING_FEATURES | `FEATURES` | Computing feature vectors |
| SCORING | `SCORING` | Scoring candidate symbols |
| WARNING | `⚠ WARN` | Completed with warnings |
| ERROR | `✗ ERROR` | Operation failed |
| SERVICE_UNAVAILABLE | `✗ UNAVAIL` | vnstock-service unreachable |

### Diagnosing ERROR / SERVICE_UNAVAILABLE

1. Check `~/.local/share/openstock/logs/vnalpha.log` for details
2. For SERVICE_UNAVAILABLE: verify vnstock-service is running
   (`curl http://127.0.0.1:6900/healthz`)
3. For ERROR: the status detail field shows the exception message

---

## Architecture

### OutputStream (`vnalpha.tui.widgets.output_stream`)

Append-only RichLog-based widget. Methods:

- `show_user_input(text)` — renders input line with `>` prefix
- `show_assistant_message(text, style=None)` — renders assistant reply
- `show_command_result(command, markup)` — renders command result with header
- `show_error(message, source=None)` — renders error in red
- `show_warning(message, source=None)` — renders warning in yellow
- `show_trace_event(event)` — renders tool trace event
- `show_data_ensure_progress(step, status, detail)` — renders data provisioning progress
- `show_table_or_markup(markup)` — renders rich markup / tables
- `show_repair_bundle(path, repair_id=None)` — renders repair bundle path
- `show_deploy_status(status, details=None)` — renders deploy status
- `clear_visible()` — clears visible area only (does not affect JSONL logs)

### ComposerInput (`vnalpha.tui.widgets.composer_input`)

Single Input widget with InputHistory. Emits `ComposerSubmitted(text)` on Enter. Clears on submit. `Up/Down` navigate history. `Ctrl+L` sends `/clear` to the router.

### StatusBar (`vnalpha.tui.widgets.status_bar`)

Compact 1-row status display. Updated by the router during operation. Shows state badge + optional label + detail.

### InputHistory (`vnalpha.tui.input_history`)

Bounded in-memory history with push/previous/next/reset_navigation. Stores up to 500 items, deduplicates consecutive, preserves draft.

### RuntimeStatus (`vnalpha.tui.runtime_status`)

Dataclass + enum model for TUI runtime state. Tracks state, label, detail, timing, last_error.

### TuiInputRouter (`vnalpha.tui.input_router`)

Stateful router. Bootstraps `ChatController` and `CommandExecutor` lazily on first use. Renders user input and results into OutputStream. All errors are captured via `capture_exception`.

---

## Validation Evidence

- Full test suite: 1100+ tests pass (pre-existing DuckDB lock + textual_renderer failures excluded)
- `make lint-vnalpha`: all checks passed, 224 files formatted
- `make verify-r4`: 80 passed
- Layout tests: `test_tui_layout_and_history.py` (13 tests)
- History tests: `test_input_history.py` (22 tests)
- Status tests: `test_tui_runtime_status.py` (11 tests)
- Governance: no ContentSwitcher, no secondary ChatPanel, no separate panes
