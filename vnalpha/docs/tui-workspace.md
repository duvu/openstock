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

## Routing module paths

The active router is `vnalpha.tui.routing.router.TuiInputRouter`. Focused
routing code lives in `vnalpha.tui.routing.command_path`,
`vnalpha.tui.routing.chat_path`, `vnalpha.tui.routing.status_adapter`,
`vnalpha.tui.routing.lifecycle_hooks`, and `vnalpha.tui.routing.events`.
Existing imports of `vnalpha.tui.input_router.TuiInputRouter` remain compatible
and re-export the routing router class.

---

## Input Routing Rules

`TuiInputRouter` routes every submitted text according to these rules (evaluated top-to-bottom):

| Input | Action |
|-------|--------|
| (empty) | No-op |
| `/clear` | `OutputStream.clear_visible()` — visible output only, no audit log deletion |
| `/approve` or `approve` | `ChatController.approve_pending_plan()` |
| `/cancel` or `cancel` | `ChatController.cancel_pending_plan()` |
| operational route | Routed before the generic executor, then rendered inline |
| other text starting with `/` | `CommandExecutor.execute(text)` → result rendered inline |
| anything else | `ChatController.handle_turn(text)` → assistant reply rendered inline |

---

## Slash Command Examples

```
/help                        # Show available commands
/scan AAPL                   # Run stock scan
/explain SMA_CROSSOVER       # Explain a pattern
/filter ...                  # Filter watchlist
/history AAPL                # Show price history
/logs errors --latest        # Show errors from the latest run
/logs summarize --latest     # Summarize the latest run
/repair prepare --latest     # Create repair bundle from latest run
/repair status <repair-id>   # Check repair status
/deploy verify <candidate>   # Verify a deploy candidate
/deploy promote <candidate> --deployment-id <id>  # Promote verified candidate
/deploy rollback <dep-id>    # Rollback a deployment
```

The seven operational routes are handled before the generic command executor:

1. `/logs errors --latest`
2. `/logs summarize --latest`
3. `/repair prepare --latest`
4. `/repair status <id>`
5. `/deploy verify <candidate>`
6. `/deploy promote <candidate> --deployment-id <id>`
7. `/deploy rollback <id>`

### Safe tools and LLM boundary

Assistant-safe research tools can run automatically. `data.fetch` is a trusted
manual provisioning command that mutates warehouse data, so assistant and
autonomous plans refuse it; deterministic analysis readiness remains handled by
`ensure_symbol_analysis_ready()`.

The planner, executor, and chat path refuse unknown or forbidden tools. The LLM is limited to research work. It can explain, summarize, and propose work, but it cannot bypass deterministic routing, invoke forbidden tools, or perform deployment actions outside the operational routes above.

Tool activity follows the run lifecycle and is recorded with sensitive values redacted.
`/deploy` only verifies, promotes, or rolls back research artifacts; it never
places broker or trading actions. When the router finishes, it closes its owned
DuckDB command connection.

---

## Observability Events

Every TUI interaction emits structured events to the run's JSONL logs:

| Event | When |
|-------|------|
| `TUI_INPUT_SUBMITTED` | Any non-empty submitted input |
| `TUI_COMMAND_ROUTED` | Slash command routing |
| `TUI_CHAT_ROUTED` | Natural-language routing |
| `COMMAND_STARTED` | A research or operational command begins |
| `COMMAND_SUCCEEDED` | A research or operational command completes |
| `COMMAND_FAILED` | A research or operational command fails and is captured |
| `TUI_RENDER_ERROR` | Any render exception (also calls `capture_exception`) |
| `TUI_STARTED` | App mount |
| `TUI_HISTORY_PUSHED` | Input pushed to history (includes kind and length) |
| `TUI_HISTORY_PREVIOUS` | User navigated to previous history item |
| `TUI_HISTORY_NEXT` | User navigated to next history item |
| `TUI_HISTORY_DRAFT_RESTORED` | Draft restored after history navigation |
| `TUI_STATUS_CHANGED` | Status bar state transition |
| `TUI_TODO_PANEL_VISIBLE` | Responsive policy made the TODO rail visible |
| `TUI_TODO_PANEL_HIDDEN` | Responsive policy hid the TODO rail |
| `TUI_TODO_PANEL_TOGGLED` | User toggled the TODO rail on a wide terminal |
| `TUI_TODO_PANEL_REFRESHED` | TODO rail reloaded items from its source |
| `TUI_TODO_ITEM_ADDED` | `/todo add` persisted an item (redacted metadata only) |
| `TUI_TODO_ITEM_UPDATED` | `/todo done`, `/todo block`, or `/todo clear-done` changed items (redacted metadata only) |

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
| `Ctrl+T` | Toggle TODO side panel on wide terminals |
| `q` | Quit |
| `Ctrl+L` | Clear visible OutputStream |
| `Escape` | Cancel pending plan |

---

## Responsive TODO Side Panel

The chat-first layout now keeps the primary stack intact while adding a read-only TODO rail on sufficiently wide terminals.

### Layout behavior

- Width `<120`: the TODO side panel is hidden.
- Width `>=120`: the TODO side panel is shown beside the main chat stack.
- `Ctrl+T` toggles the side panel only when the terminal is wide enough.
- Resize events re-evaluate visibility automatically.
- Composer focus is restored after mount, clear, toggle, and resize so the single input workflow stays uninterrupted.

### Data model and sources

The panel is display-only. It does **not** mount a second `Input`, and it does not introduce a new command surface.

Current TODO items are derived from workspace context state:

- `WorkspaceState.open_tasks`
- `WorkspaceState.warnings`

Warnings are surfaced as blocked TODO-style items so the operator can see unresolved workspace risks in the same rail. When no workspace TODO data is available, the panel renders an empty-state hint instead of opening an editor.

### TODO commands

The panel remains read-only; use the primary composer to manage persisted workspace tasks:

```text
/todo list
/todo add <text>
/todo done <id>
/todo block <id>
/todo clear-done
```

`/todo list` returns structured item rows (`id`, `status`, `priority`, `text`, and
`updated_at`). Adding defaults to `pending` and `medium`; completing uses
`completed`; blocking uses `blocked`; and `clear-done` removes only `completed`
or legacy `done` items. Item events and audit metadata redact task text.

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

Stateful router. At setup it opens a DuckDB connection, runs migrations, and
constructs `CommandExecutor(conn, surface="tui", default_date=target_date)`.
It owns and closes that connection during app shutdown. Setup failures render an
actionable inline error and are captured via `capture_exception`.

---

## Validation Evidence

- Responsive TODO coverage: `pytest vnalpha/tests/test_tui_todo_panel.py vnalpha/tests/test_tui_pilot.py vnalpha/tests/test_tui_layout_and_history.py` → 40 passed
- `make verify-r4`: 80 passed
- `./packaging/scripts/openstock-verify --ci`: PASS (16 OK, 1 WARN, 0 FAIL)
- `make test-vnalpha`: passes with an isolated `VNALPHA_WAREHOUSE_PATH`
- `make lint-vnalpha`: passes
- Layout tests: `test_tui_layout_and_history.py` (13 tests)
- History tests: `test_input_history.py` (22 tests)
- Status tests: `test_tui_runtime_status.py` (11 tests)
- Governance: no ContentSwitcher, no secondary ChatPanel, no separate panes
