# Tasks: Phase 5.10 OpenCode-style Research Chat Workspace

## 1. TUI shell and layout

- [x] 1.1 Add `MainWorkspaceContainer` or equivalent region for main screens.
- [x] 1.2 Mount `ChatPanel` as a persistent bottom pane, not as a full screen replacement.
- [x] 1.3 Route existing Watchlist, Detail, Quality, Outcome, Command, and Assistant screens into the main workspace region.
- [x] 1.4 Add/fix keybindings: toggle chat, focus chat, resize chat pane, cancel pending plan.
- [x] 1.5 Add test proving chat panel remains visible when switching main screens.

## 2. ChatController

- [x] 2.1 Create `ChatController` to own chat orchestration.
- [x] 2.2 Move input classification out of `ChatPanel` into `ChatController`.
- [x] 2.3 Make `ChatPanel` delegate slash commands and natural-language prompts to `ChatController`.
- [x] 2.4 Add connection factory so each turn can open/run/close a short-lived DuckDB connection.
- [x] 2.5 Add fake connection/controller tests.

## 3. Unified slash command execution

- [x] 3.1 Remove custom command parsing/execution path from `ChatPanel`.
- [x] 3.2 Execute research slash commands through `CommandExecutor(surface='tui-chat')`.
- [x] 3.3 Ensure default date is injected consistently through `CommandExecutor(default_date=target_date)`.
- [x] 3.4 Forward trace events from command tool execution to the chat log.
- [x] 3.5 Persist command result messages with `research_session_id` when available.
- [x] 3.6 Add tests proving `/scan`, `/filter`, `/quality`, and `/explain` entered in chat use `CommandExecutor`.

## 4. Chat persistence schema

- [x] 4.1 Add `chat_session` DDL.
- [x] 4.2 Add `chat_message` DDL.
- [x] 4.3 Add migration helper for future additive chat columns.
- [x] 4.4 Add repository methods: create session, finish/update session, append message, list messages, clear visible session.
- [x] 4.5 Persist user messages, assistant messages, command results, plan previews, trace events, validation errors, refusals, and runtime errors.
- [x] 4.6 Add tests for transcript ordering and replay.

## 5. Multi-turn context

- [x] 5.1 Add `ChatContext` model.
- [x] 5.2 Build context from current target date, selected screen state, and latest chat messages.
- [x] 5.3 Track `last_symbols`, `selected_symbol`, `selected_rank`, `last_watchlist_date`, and last tool summaries.
- [x] 5.4 Resolve references such as `the first one`, `top candidate`, `that symbol`, and `same date` deterministically.
- [x] 5.5 Pass context into `AssistantApp.ask()` or an equivalent assistant context interface.
- [x] 5.6 Add tests for context-aware follow-up questions.

## 6. Plan preview and approval

- [x] 6.1 Add execution mode: `AUTO_EXECUTE_SAFE_READ_ONLY`, `PLAN_THEN_APPROVE`, `PLAN_ONLY`.
- [x] 6.2 Add plan preview rendering in ChatPanel.
- [x] 6.3 Add approve/cancel/edit state machine for pending plans.
- [x] 6.4 Persist pending plan as chat message.
- [x] 6.5 Execute approved plan through AssistantExecutor with trace callback.
- [x] 6.6 Ensure canceled plans do not execute tools.
- [x] 6.7 Add tests for preview, approve, cancel, and plan-only behavior.

## 7. Streaming or staged response UX

- [x] 7.1 Add event model for assistant stages: classify, plan, tool_start, tool_success, tool_failed, synthesize, token, final.
- [x] 7.2 Implement staged fallback if true LLM token streaming is not yet available.
- [x] 7.3 Add optional streaming interfaces in LLM gateway and synthesizer when supported.
- [x] 7.4 Render staged events in ChatPanel.
- [x] 7.5 Persist final answer and relevant stage summaries.
- [x] 7.6 Add tests for fallback staged output and, if implemented, token streaming.

## 8. Trace timeline

- [x] 8.1 Link trace events to the current chat turn.
- [x] 8.2 Persist trace event messages or trace ids for replay.
- [x] 8.3 Render tool trace timeline compactly in the chat log.
- [x] 8.4 Add `/trace` chat command for current/previous turn.
- [x] 8.5 Add tests proving trace events are rendered and persisted.

## 9. Chat-local commands

- [x] 9.1 Add `/new` to start a new chat session.
- [x] 9.2 Add `/clear` to clear visible log while preserving transcript by default.
- [x] 9.3 Add `/clear --forget` only if explicit transcript deletion is implemented safely.
- [x] 9.4 Add `/context` to show current context.
- [x] 9.5 Add `/plan` to toggle/show plan mode.
- [x] 9.6 Add `/trace` to show trace timeline.
- [x] 9.7 Update `/help` output to include chat-local and research slash commands.
- [x] 9.8 Add tests for all chat-local commands.

## 10. Safety and tool allowlist

- [x] 10.1 Keep assistant tool allowlist read-only.
- [x] 10.2 Ensure chat cannot call broker/order/allocation/account tools.
- [x] 10.3 Ensure future Python/web/MCP tools require plan approval and policy gates.
- [x] 10.4 Add tests for disallowed tool names and unsafe prompt refusals.

## 11. Error and validation handling

- [x] 11.1 Render validation errors as non-fatal yellow chat messages.
- [x] 11.2 Render runtime failures as red error messages.
- [x] 11.3 Persist refusal, validation error, and runtime error messages.
- [x] 11.4 Ensure failed tool calls still create failed `tool_trace` rows.
- [x] 11.5 Add tests for validation, refusal, and runtime failure paths.

## 12. Documentation

- [x] 12.1 Document Phase 5.10 chat workspace behavior.
- [x] 12.2 Document keybindings.
- [x] 12.3 Document chat-local commands.
- [x] 12.4 Document plan approval behavior.
- [x] 12.5 Document research-only safety boundary.

## 13. Validation

- [x] 13.1 Run `cd vnalpha && pytest -q`.
- [x] 13.2 Run targeted chat controller tests.
- [x] 13.3 Run targeted chat persistence tests.
- [x] 13.4 Run targeted TUI shell/layout tests.
- [x] 13.5 Run targeted assistant trace/plan tests.
- [x] 13.6 Run existing Phase 5.8 command tests.
- [x] 13.7 Run existing Phase 5.9 assistant tests.
