# Design: OpenCode-style Research Chat Workspace

## Design principles

### One execution path

Slash commands typed into chat must use the same execution path as CLI/TUI command surfaces.

```text
chat /scan -> CommandExecutor -> CommandRegistry -> TracedLocalToolExecutor -> LocalToolRegistry
cli  /scan -> CommandExecutor -> CommandRegistry -> TracedLocalToolExecutor -> LocalToolRegistry
```

Chat must not maintain a parallel command-dispatch implementation that can drift.

### Chat is a workspace, not a one-shot question box

A chat turn must know prior turns, last selected symbols, last watchlist date, last tool outputs, and current workspace context.

### Tool execution must remain explicit and inspectable

Assistant-generated plans should be visible before execution when tools are involved. The user must be able to approve, cancel, or preview.

### Research-only safety boundary

The chat workspace must never expose order, broker, allocation, account, or portfolio-mutating tools.

### Progressive UX

The design should support full streaming where available, but the MVP may use staged output events if LLM streaming is not yet implemented.

## Proposed architecture

```text
VnAlphaApp
  ├── MainWorkspaceContainer
  │     ├── WatchlistScreen
  │     ├── DetailScreen
  │     ├── QualityScreen
  │     ├── OutcomeScreen
  │     └── CommandScreen
  └── ChatPanel
        ├── ChatController
        ├── ChatSessionRepository
        ├── CommandExecutor adapter
        ├── AssistantApp adapter
        ├── PlanApprovalState
        └── TraceTimeline renderer
```

## 1. True split-pane layout

### Problem

The current TUI yields a `ChatPanel` and then pushes screens. Screen navigation may overlay or replace the main UI in a way that prevents the chat panel from being structurally persistent.

### Design

Create a TUI shell layout:

```text
Vertical
  MainWorkspaceContainer  height: 70% or 1fr
  ChatPanel               height: 30% or configurable
```

Screens should be mounted or swapped inside `MainWorkspaceContainer`, not pushed as full-screen overlays that hide the chat panel.

Required shell actions:

```text
action_show_watchlist
action_show_detail
action_show_quality
action_show_outcomes
action_show_command_screen
action_toggle_chat
action_focus_chat
action_resize_chat_larger
action_resize_chat_smaller
```

Default bindings:

```text
ctrl+backslash  toggle chat
ctrl+slash      focus chat
ctrl+up/down    resize chat pane
esc             return focus to main workspace or cancel pending plan
```

## 2. ChatPanel execution model

### Problem

Current ChatPanel manually parses and dispatches slash commands and may run without a DB connection.

### Design

Introduce a `ChatController` responsible for:

```text
- input classification: chat command vs slash command vs assistant prompt
- chat session creation/loading
- message persistence
- command execution through CommandExecutor
- assistant execution through AssistantApp
- trace event forwarding
- plan approval state
```

ChatPanel should be a thin UI component:

```text
ChatPanel
  renders messages
  captures input
  delegates to ChatController
```

Slash command path:

```text
raw input startswith '/'
  -> ChatController.execute_slash_command(raw)
  -> CommandExecutor(conn, surface='tui-chat', default_date=target_date).execute(raw)
  -> persist command result as chat_message(role='tool_result')
  -> render summary/table preview
```

DB connection policy:

```text
- ChatController opens a short-lived connection per turn, runs migrations, executes, then closes it.
- Long-lived UI widgets must not rely on a shared DuckDB connection.
- The controller may use a connection factory for testability.
```

## 3. Chat session and message persistence

### Schema

Add tables:

```text
chat_session
  chat_session_id       VARCHAR PRIMARY KEY
  started_at            TIMESTAMPTZ NOT NULL
  updated_at            TIMESTAMPTZ
  status                VARCHAR NOT NULL
  surface               VARCHAR NOT NULL
  target_date           DATE
  title                 VARCHAR
  context_json          VARCHAR

chat_message
  chat_message_id       VARCHAR PRIMARY KEY
  chat_session_id       VARCHAR NOT NULL
  created_at            TIMESTAMPTZ NOT NULL
  role                  VARCHAR NOT NULL
  content               VARCHAR NOT NULL
  message_type          VARCHAR
  assistant_session_id  VARCHAR
  research_session_id   VARCHAR
  tool_trace_ids_json   VARCHAR
  plan_json             VARCHAR
  metadata_json         VARCHAR
```

Allowed `chat_message.role` values:

```text
user
assistant
system
tool
trace
plan
error
```

Allowed `message_type` values:

```text
plain_text
slash_command
assistant_answer
plan_preview
tool_trace_event
command_result
validation_error
refusal
error
```

Migration requirements:

```text
- CREATE TABLE IF NOT EXISTS for new tables.
- Future additive columns must use ALTER TABLE ADD COLUMN IF NOT EXISTS.
```

## 4. Multi-turn context

### Problem

Natural-language chat currently runs as independent `AssistantApp.ask()` calls.

### Design

Add a `ChatContext` object built from the latest persisted messages and workspace state.

```text
ChatContext
  chat_session_id
  target_date
  last_symbols
  last_watchlist_date
  last_command
  last_assistant_intent
  last_plan
  last_tool_outputs_summary
  selected_symbol
  selected_rank
```

Context extraction rules:

```text
- /scan updates last_watchlist_date and last_symbols.
- /detail or clicking/selecting a symbol updates selected_symbol.
- assistant compare/explain plans update last_symbols.
- phrases like 'the first one', 'top candidate', or 'that symbol' resolve through context.
```

AssistantApp changes:

```text
AssistantApp.ask(..., chat_context: ChatContext | None = None)
```

Intent classifier/planner may use context only for deterministic entity resolution. It must not invent symbols that are not in context or input.

## 5. Plan preview and approval

### Problem

Assistant currently executes tools immediately.

### Design

Add execution modes:

```text
AUTO_EXECUTE_SAFE_READ_ONLY
PLAN_THEN_APPROVE
PLAN_ONLY
```

MVP default:

```text
- Slash commands execute immediately.
- Assistant prompts with only safe read-only tools may auto-execute by default.
- A user setting or chat command can switch to PLAN_THEN_APPROVE.
- Any future non-read-only, web, Python, MCP, or external tool must require approval.
```

Plan approval UX:

```text
Assistant Plan
1. watchlist.scan(date=2026-07-06)
2. quality.get_many_status(symbols=[...])

Approve? Enter=approve | e=edit | Esc=cancel
```

Persist plan preview as `chat_message(role='plan', message_type='plan_preview')`.

## 6. Streaming and staged output

### Target

Support token streaming when the LLM gateway and synthesizer provide it.

Interfaces:

```text
AssistantApp.ask_stream(..., on_token, on_trace_event, on_plan_event)
AnswerSynthesizer.synthesize_stream(...)
LLMGatewayClient.stream(...)
```

MVP fallback if true streaming is unavailable:

```text
- show user message immediately
- show intent/classification stage
- show plan stage
- show tool trace events live
- show final answer when synthesis completes
```

The fallback must be explicit in code and tests.

## 7. Trace timeline

Trace events from `TracedLocalToolExecutor` should be rendered and persisted.

Runtime events:

```text
RUNNING
SUCCESS
FAILED
```

Persistence:

```text
- tool_trace remains the canonical tool audit table.
- chat_message can store trace events for UI replay.
- chat_message.tool_trace_ids_json links assistant/chat turns to tool traces.
```

UI rendering:

```text
⟳ watchlist.scan running...
✓ watchlist.scan success 42ms
✗ quality.get_status failed 18ms
```

## 8. Chat commands

Add chat-local commands that do not conflict with research slash commands:

```text
/new       start a new chat session
/clear     clear visible log, preserve persisted transcript unless --forget
/context   show current chat context
/plan      toggle plan preview mode or show pending plan
/trace     show trace timeline for current or previous turn
/help      include chat commands and research slash commands
```

Research slash commands continue to be handled by CommandExecutor.

## 9. Error and validation handling

User-facing statuses:

```text
validation error -> yellow message, persisted as validation_error
runtime failure  -> red message, persisted as error
refusal          -> yellow/red policy message, persisted as refusal
```

Tool trace failures must still be persisted as `tool_trace.status = FAILED`.

## 10. Tests

Required tests:

```text
test_tui_shell_contains_main_workspace_and_chat_panel
test_chatpanel_routes_slash_commands_through_command_executor
test_chatpanel_opens_db_for_slash_commands
test_chat_transcript_persists_user_assistant_and_tool_messages
test_chat_context_resolves_first_candidate
test_assistant_plan_preview_persists_plan_message
test_plan_approval_executes_tools_after_approval
test_plan_cancel_does_not_execute_tools
test_trace_events_render_and_persist
test_chat_streaming_fallback_shows_staged_events
test_chat_research_only_tool_allowlist
test_chat_commands_new_clear_context_plan_trace
```

Use unit tests for controller/repositories and integration tests for Textual widgets where feasible. If full Textual integration is heavy, use widget/controller tests with fake app callbacks.

## Migration path

```text
1. Add schema/repository for chat_session and chat_message.
2. Create ChatController and move command/assistant orchestration out of ChatPanel.
3. Refactor TUI layout into MainWorkspaceContainer + ChatPanel.
4. Route slash commands through CommandExecutor.
5. Add chat context extraction.
6. Add plan preview/approval.
7. Add streaming or staged fallback.
8. Add tests and docs.
```

## Compatibility

Existing CLI commands stay unchanged.

Existing `vnalpha ask` stays available as a single-shot CLI interface.

Existing `AssistantScreen` and `CommandScreen` may remain, but the persistent ChatPanel becomes the preferred interactive workspace entrypoint.
