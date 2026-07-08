# vnalpha TUI — opencode-like Chat-First Workspace

> Developer and operator reference for the refactored single-pane TUI.

---

## Overview

The `vnalpha tui` command launches an opencode-style workspace with two regions:

```
┌────────────────────────────────────────────────────────────────┐
│  OutputStream (id="output-stream")                             │
│  Append-only. All output — assistant messages, command        │
│  results, tool traces, errors, warnings — renders here.       │
│                                                                │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  ComposerInput (id="composer-input")  height=3                 │
│  > Ask or run /command ...                                     │
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
| `q` | Quit |
| `ctrl+l` | Clear visible OutputStream |
| `escape` | Cancel pending plan |

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
- `show_table_or_markup(markup)` — renders rich markup / tables
- `show_repair_bundle(path, repair_id=None)` — renders repair bundle path
- `show_deploy_status(status, details=None)` — renders deploy status
- `clear_visible()` — clears visible area only (does not affect JSONL logs)

### ComposerInput (`vnalpha.tui.widgets.composer_input`)

Single Input widget. Emits `ComposerSubmitted(text)` on Enter. Clears on submit. `Ctrl+L` sends `/clear` to the router.

### TuiInputRouter (`vnalpha.tui.input_router`)

Stateful router. Bootstraps `ChatController` and `CommandExecutor` lazily on first use. Renders user input and results into OutputStream. All errors are captured via `capture_exception`.

---

## Validation Evidence

- 1091 tests pass (excluding `test_tui_pilot.py` with pre-existing failures)
- `ruff check src/` — all checks passed
- New workspace tests: `vnalpha/tests/test_tui_workspace.py` (16 tests)
- Updated layout tests: `vnalpha/tests/test_tui_layout.py`
