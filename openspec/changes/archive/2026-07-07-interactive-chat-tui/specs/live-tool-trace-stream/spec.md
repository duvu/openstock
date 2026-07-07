## ADDED Requirements

### Requirement: Tool trace events stream into the chat log in real-time
When the assistant is processing a question, each tool call SHALL emit a trace event into the `ChatPanel` log as it starts and finishes — not only after all tools have completed.

#### Scenario: Tool start event appears immediately
- **WHEN** the assistant begins executing a tool call (e.g., `watchlist.filter`)
- **THEN** a line SHALL appear in the chat log showing the tool name and status `RUNNING` before the tool returns

#### Scenario: Tool finish event updates the log
- **WHEN** the tool call completes
- **THEN** the log entry SHALL update to show `SUCCESS` or `FAILED` with the elapsed duration in milliseconds

#### Scenario: Multiple tool calls stream sequentially
- **WHEN** the assistant plan contains multiple tool steps
- **THEN** each tool call SHALL appear in the log in execution order, each with its own status line

### Requirement: Trace events do not block the UI thread
Tool call execution SHALL run in a background thread so the Textual UI remains responsive. Trace events SHALL be posted to the UI thread via `app.call_from_thread()`.

#### Scenario: UI remains responsive during LLM call
- **WHEN** the assistant is waiting for an LLM response (up to 30 seconds)
- **THEN** the user SHALL still be able to scroll the watchlist and navigate screens

#### Scenario: Trace events posted from background thread
- **WHEN** `TracedLocalToolExecutor` finishes a tool call from within `asyncio.to_thread`
- **THEN** the chat log update SHALL be posted safely via `App.call_from_thread()` without raising a Textual threading error
