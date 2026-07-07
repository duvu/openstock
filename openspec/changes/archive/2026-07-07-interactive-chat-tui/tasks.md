## 1. Trace event callback infrastructure

- [x] 1.1 Define `TraceEvent` dataclass in `tools/executor.py`: fields `tool_name`, `status` (`RUNNING`/`SUCCESS`/`FAILED`), `duration_ms` (optional), `tool_trace_id`
- [x] 1.2 Add optional `trace_event_callback: Callable[[TraceEvent], None] | None = None` parameter to `TracedLocalToolExecutor.__init__`
- [x] 1.3 In `TracedLocalToolExecutor._run_tool()`: call `trace_event_callback(TraceEvent(tool_name, "RUNNING", None, trace_id))` immediately after `insert_tool_trace()`
- [x] 1.4 In `TracedLocalToolExecutor._run_tool()`: call callback with `SUCCESS`/`FAILED` + computed `duration_ms` after `finish_tool_trace()`
- [x] 1.5 Add `on_trace_event: Callable[[TraceEvent], None] | None = None` param to `AssistantApp.ask()`; if provided, pass it through to `TracedLocalToolExecutor` constructor
- [x] 1.6 Unit test: verify callback is called with RUNNING then SUCCESS/FAILED for a single tool call (mock tool)

## 2. ChatPanel widget

- [x] 2.1 Create `vnalpha/src/vnalpha/tui/widgets/chat_panel.py` with `ChatPanel(Widget)` class
- [x] 2.2 `ChatPanel.compose()`: yields `RichLog(id="chat-log", markup=True, wrap=True)` + `Input(placeholder="Ask or /command ...", id="chat-input")`
- [x] 2.3 `ChatPanel` height: `height: 30%` via inline CSS; `border: round $accent`
- [x] 2.4 Add `ChatPanel.post_message_text(text: str, style: str = "")` method that appends styled text to `#chat-log` via `self.query_one("#chat-log", RichLog).write()`
- [x] 2.5 Add `ChatPanel.post_trace_event(event: TraceEvent)` method: writes `[dim]⟳ tool_name RUNNING[/dim]` or `[green]✓ tool_name SUCCESS 42ms[/green]` / `[red]✗ tool_name FAILED[/red]`
- [x] 2.6 `on_input_submitted`: if input starts with `/`, call `_dispatch_command()`; else call `_dispatch_assistant()`; disable input during processing; re-enable on completion
- [x] 2.7 `_dispatch_assistant(question)`: run `AssistantApp.ask(question, on_trace_event=...)` in `asyncio.to_thread`; trace callback uses `app.call_from_thread(self.post_trace_event, event)`; on completion post answer summary to log
- [x] 2.8 `_dispatch_command(raw_input)`: parse command name and args from `/cmd key=val ...`; invoke appropriate `CommandHandler`; post `CommandResult.summary` to log
- [x] 2.9 Handle unknown slash commands: post error listing valid commands (`scan`, `score`, `filter`, `quality`, `explain`, `compare`, `lineage`, `note`, `history`)
- [x] 2.10 Toggle visibility: bind `ctrl+backslash` in `ChatPanel` to toggle `display` CSS property
- [x] 2.11 Focus binding: `ctrl+slash` focuses the `#chat-input` Input widget

## 3. TUI app layout integration

- [x] 3.1 Update `VnAlphaApp.compose()` in `tui/app.py`: yield `ContentSwitcher` (or screen area) then `ChatPanel()` in a `Vertical` layout
- [x] 3.2 Ensure `ChatPanel` instance is a direct child of `VnAlphaApp` (not per-screen) so state persists across screen pushes
- [x] 3.3 Add `ctrl+backslash` binding to `VnAlphaApp.BINDINGS` with description "Toggle chat"
- [x] 3.4 Add `ctrl+slash` binding to focus the chat input
- [x] 3.5 Update `vnalpha/src/vnalpha/tui/__init__.py` to export `ChatPanel`

## 4. Command dispatch wiring

- [x] 4.1 Add `CommandDispatcher` helper in `chat_panel.py` or `commands/dispatch.py`: maps command name string → `CommandHandler` class; accepts parsed args dict
- [x] 4.2 Wire `CommandDispatcher` into `ChatPanel._dispatch_command()` so `/scan`, `/filter`, `/quality`, `/score`, `/explain`, `/compare` all resolve correctly
- [x] 4.3 Pass `tool_executor` (with trace callback) through `CommandDispatcher` so tool traces stream for commands too
- [x] 4.4 Format `CommandResult` for the chat log: show `result.summary`; if `result.status == "FAILED"` show in red

## 5. Tests

- [x] 5.1 Unit test `TraceEvent` dataclass and `TracedLocalToolExecutor` callback (mock DB, verify callback sequence RUNNING → SUCCESS)
- [x] 5.2 Unit test `ChatPanel._dispatch_command()` with mock `CommandDispatcher`: verify `/scan` routes to scan handler, unknown command returns error
- [x] 5.3 Unit test `ChatPanel._dispatch_assistant()` with mock `AssistantApp.ask()`: verify trace events are posted and answer appears
- [x] 5.4 Unit test toggle visibility: `ChatPanel.display` toggles on `ctrl+backslash` action
- [x] 5.5 Smoke test: `VnAlphaApp` composes without exception; `ChatPanel` is found via `app.query_one(ChatPanel)`

## 6. Validation

- [x] 6.1 Run `PYTHONPATH=src pytest tests/ -q` — all existing tests must still pass (578 passed, 26 skipped)
- [x] 6.2 Manual smoke: `vnalpha tui` launches with chat panel visible; typing a question returns an answer in the log
- [x] 6.3 Manual smoke: `/scan` in chat returns command result inline
- [x] 6.4 Verify `ctrl+\` hides and shows chat panel
- [x] 6.5 Run `ruff check src/ && ruff format --check src/` — no lint errors
