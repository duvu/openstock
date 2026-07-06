## Context

`vnalpha` already has a `AssistantScreen` (TUI screen, hotkey `a`) and `AssistantApp.ask()` for natural-language queries. The TUI is built on Textual (already a dependency). The issue is that the assistant is isolated: users must navigate away from the watchlist to ask a question, there is no live feedback during tool calls, and the chat history is lost when leaving the screen.

opencode's UX model — input bar always at the bottom, streaming tool events inline, persistent history — is the target pattern.

## Goals / Non-Goals

**Goals:**
- Persistent `ChatPanel` widget always visible at the bottom of every TUI screen.
- Real-time tool-trace streaming: each tool call shows `RUNNING` → `SUCCESS`/`FAILED` + duration inline in chat log.
- Chat input accepts both free-form assistant questions and `/command args` dispatch.
- Per-session message history preserved across screen navigation.
- Zero new external dependencies.

**Non-Goals:**
- Persistent chat history across TUI sessions (no DB write for chat messages).
- Multi-turn LLM conversation context (each question is independent, matching current `AssistantApp.ask()` behaviour).
- Web/mobile UI.
- Streaming LLM token output (response appears fully after synthesis completes).

## Decisions

### Split-pane layout via Textual `Vertical` + `ChatPanel` in root `App`

Mount `ChatPanel` directly in `VnAlphaApp.compose()` below the screen stack placeholder (`ScreenContainer`). This means every screen automatically has the chat panel beneath it — no changes needed per-screen, no shared base class required.

**Alternative considered**: A base `Screen` class all screens inherit from. Rejected because Textual's `App.compose()` is the correct place for persistent layout elements; per-screen composition would duplicate the widget and reset its state on every screen push.

### Tool-trace streaming via callback injection

Add an optional `on_trace_event: Callable[[TraceEvent], None] | None` parameter to `AssistantApp.ask()`. `TracedLocalToolExecutor` gains an optional `trace_event_callback` that is called on each `start_tool_trace` / `finish_tool_trace`. When the TUI calls `ask()`, it passes a callback that posts a `TraceEvent` message to the Textual app via `app.call_from_thread()`.

**Alternative considered**: A global event bus / observer. Rejected as over-engineered; the callback keeps the dependency inversion minimal.

### Worker thread for blocking LLM calls

Textual's UI thread is async. `AssistantApp.ask()` is synchronous (httpx sync). Run it in a `asyncio.to_thread` call inside the `ChatPanel.on_input_submitted` handler, post a `ChatMessage` back to the panel when done.

### `/command` dispatch reuses `CommandHandler`

If input starts with `/`, parse `CommandHandler` name and args, delegate to existing `commands/handlers/*.py`. Tool trace callback is the same. Chat result is formatted from `CommandResult`.

### `ChatPanel` is a self-contained Textual `Widget`

Contains: `RichLog` (history + trace log), `Input` (bottom bar). No static state outside the widget instance — the `VnAlphaApp` instance owns one `ChatPanel` and all screens share the same instance via `app.query_one(ChatPanel)`.

## Risks / Trade-offs

- **Textual version API drift** → Use only stable `RichLog`, `Input`, `Vertical`, `App.compose` APIs. Textual is already pinned in `pyproject.toml`.
- **Blocking LLM call hangs UI during slow network** → Mitigated by running in `asyncio.to_thread`; the input is disabled during processing and re-enabled on completion.
- **AssistantApp.ask() is not thread-safe (DuckDB connection)** → Each chat call opens its own `get_connection()` call inside the thread; the TUI's main connection is separate. DuckDB supports multiple readers.
- **Chat panel height takes screen real estate** → Default height is 30% of terminal; user can toggle hide/show with `ctrl+\`.

## Migration Plan

1. Add `trace_event_callback` optional param to `TracedLocalToolExecutor` and `AssistantApp.ask()` — backward compatible (defaults to `None`).
2. Add `ChatPanel` widget.
3. Update `VnAlphaApp.compose()` to mount `ChatPanel`.
4. Existing `AssistantScreen` remains; hotkey `a` still works for full-screen mode.
5. No DB migration. No CLI changes.

## Open Questions

- Should the chat panel auto-focus on startup, or require explicit click/`ctrl+/` to focus? → Default: focus on `ctrl+/`; watchlist keeps focus on startup to avoid accidental input.
