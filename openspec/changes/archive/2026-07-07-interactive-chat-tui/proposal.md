## Why

The existing `AssistantScreen` is a separate TUI screen (hotkey `a`) that forces the user to leave the watchlist context to ask a question, and gives no live feedback while the LLM and tool calls are running. Users need an always-accessible chat panel — similar to how opencode's chat input sits at the bottom of every screen — so they can query the assistant, issue commands, and see live tool-trace output without losing their current view.

## What Changes

- Add a persistent `ChatPanel` widget rendered at the bottom of every TUI screen (split-pane layout: content above, chat below).
- Chat input accepts free-form questions (assistant path) and slash-style commands (`/scan`, `/score`, `/quality …`).
- Tool trace events stream into a scrollable log region inside the chat panel in real-time, showing each tool call name, status (RUNNING → SUCCESS/FAILED), and duration.
- LLM synthesis result appears inline in the chat log after all tool calls complete.
- Previous exchanges are kept in a scrollable history within the session.
- The `AssistantScreen` standalone screen is kept for backward compatibility but becomes non-primary; the chat panel supersedes it for daily use.
- `vnalpha tui` launches directly into a split-pane layout (watchlist + chat) instead of pure watchlist.

## Capabilities

### New Capabilities

- `persistent-chat-panel`: Always-visible chat panel at the bottom of the TUI, with input field, scrollable message history, and real-time tool-trace log stream.
- `live-tool-trace-stream`: Tool trace events (tool name, status, timing) are pushed into the chat panel as they happen, not just shown after completion.
- `chat-command-dispatch`: `/command args` typed in the chat input dispatches to the existing `CommandHandler` pipeline (scan, score, filter, quality, explain, etc.) and shows results inline.

### Modified Capabilities

- `alpha-discovery-tui`: The root TUI layout changes from single-screen to persistent split-pane with the chat panel always mounted.

## Impact

- `vnalpha/src/vnalpha/tui/app.py`: Root app layout changes; `VnAlphaApp` mounts `ChatPanel` as a persistent bottom widget across all screens.
- `vnalpha/src/vnalpha/tui/widgets/`: New `chat_panel.py` widget containing input + history + tool-trace log.
- `vnalpha/src/vnalpha/tui/screens/`: All existing screens gain the chat panel through a shared base class or CSS layout.
- `vnalpha/src/vnalpha/assistant/app.py`: `AssistantApp.ask()` needs an optional `on_trace_event` callback for streaming tool trace events to the TUI.
- `vnalpha/src/vnalpha/tools/executor.py`: `TracedLocalToolExecutor` needs an optional event hook called on each trace start/finish.
- No new external dependencies; Textual is already in `pyproject.toml`.
- No changes to data models, warehouse schema, or provider logic.
