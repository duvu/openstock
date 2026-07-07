# Tasks: Phase 5.10 OpenCode-style Research Chat Workspace

## 1. TUI shell and layout

- [ ] 1.1 Add `MainWorkspaceContainer` or equivalent region for main screens.
- [ ] 1.2 Mount `ChatPanel` as a persistent bottom pane, not as a full screen replacement.
- [ ] 1.3 Route existing Watchlist, Detail, Quality, Outcome, Command, and Assistant screens into the main workspace region.
- [ ] 1.4 Add/fix keybindings: toggle chat, focus chat, resize chat pane, cancel pending plan.
- [ ] 1.5 Add test proving chat panel remains visible when switching main screens.

## 2. ChatController

- [ ] 2.1 Create `ChatController` to own chat orchestration.
- [ ] 2.2 Move input classification out of `ChatPanel` into `ChatController`.
- [ ] 2.3 Make `ChatPanel` delegate slash commands and natural-language prompts to `ChatController`.
- [ ] 2.4 Add connection factory so each turn can open/run/close a short-lived DuckDB connection.
- [ ] 2.5 Add fake connection/controller tests.

## 3. Unified slash command execution

- [ ] 3.1 Remove custom command parsing/execution path from `ChatPanel`.
- [ ] 3.2 Execute research slash commands through `CommandExecutor(surface='tui-chat')`.
- [ ] 3.3 Ensure default date is injected consistently through `CommandExecutor(default_date=target_date)`.
- [ ] 3.4 Forward trace events from command tool execution to the chat log.
- [ ] 3.5 Persist command result messages with `research_session_id` when available.
- [ ] 3.6 Add tests proving `/scan`, `/filter`, `/quality`, and `/explain` entered in chat use `CommandExecutor`.

## 4. Chat persistence schema

- [ ] 4.1 Add `chat_session` DDL.
- [ ] 4.2 Add `chat_message` DDL.
- [ ] 4.3 Add migration helper for future additive chat columns.
- [ ] 4.4 Add repository methods: create session, finish/update session, append message, list messages, clear visible session.
- [ ] 4.5 Persist user messages, assistant messages, command results, plan previews, trace events, validation errors, refusals, and runtime errors.
- [ ] 4.6 Add tests for transcript ordering and replay.

## 5. Multi-turn context

- [ ] 5.1 Add `ChatContext` model.
- [ ] 5.2 Build context from current target date, selected screen state, and latest chat messages.
- [ ] 5.3 Track `last_symbols`, `selected_symbol`, `selected_rank`, `last_watchlist_date`, and last tool summaries.
- [ ] 5.4 Resolve references such as `the first one`, `top candidate`, `that symbol`, and `same date` deterministically.
- [ ] 5.5 Pass context into `AssistantApp.ask()` or an equivalent assistant context interface.
- [ ] 5.6 Add tests for context-aware follow-up questions.

## 6. Plan preview and approval

- [ ] 6.1 Add execution mode: `AUTO_EXECUTE_SAFE_READ_ONLY`, `PLAN_THEN_APPROVE`, `PLAN_ONLY`.
- [ ] 6.2 Add plan preview rendering in ChatPanel.
- [ ] 6.3 Add approve/cancel/edit state machine for pending plans.
- [ ] 6.4 Persist pending plan as chat message.
- [ ] 6.5 Execute approved plan through AssistantExecutor with trace callback.
- [ ] 6.6 Ensure canceled plans do not execute tools.
- [ ] 6.7 Add tests for preview, approve, cancel, and plan-only behavior.

## 7. Streaming or staged response UX

- [ ] 7.1 Add event model for assistant stages: classify, plan, tool_start, tool_success, tool_failed, synthesize, token, final.
- [ ] 7.2 Implement staged fallback if true LLM token streaming is not yet available.
- [ ] 7.3 Add optional streaming interfaces in LLM gateway and synthesizer when supported.
- [ ] 7.4 Render staged events in ChatPanel.
- [ ] 7.5 Persist final answer and relevant stage summaries.
- [ ] 7.6 Add tests for fallback staged output and, if implemented, token streaming.

## 8. Trace timeline

- [ ] 8.1 Link trace events to the current chat turn.
- [ ] 8.2 Persist trace event messages or trace ids for replay.
- [ ] 8.3 Render tool trace timeline compactly in the chat log.
- [ ] 8.4 Add `/trace` chat command for current/previous turn.
- [ ] 8.5 Add tests proving trace events are rendered and persisted.

## 9. Chat-local commands

- [ ] 9.1 Add `/new` to start a new chat session.
- [ ] 9.2 Add `/clear` to clear visible log while preserving transcript by default.
- [ ] 9.3 Add `/clear --forget` only if explicit transcript deletion is implemented safely.
- [ ] 9.4 Add `/context` to show current context.
- [ ] 9.5 Add `/plan` to toggle/show plan mode.
- [ ] 9.6 Add `/trace` to show trace timeline.
- [ ] 9.7 Update `/help` output to include chat-local and research slash commands.
- [ ] 9.8 Add tests for all chat-local commands.

## 10. Safety and tool allowlist

- [ ] 10.1 Keep assistant tool allowlist read-only.
- [ ] 10.2 Ensure chat cannot call broker/order/allocation/account tools.
- [ ] 10.3 Ensure future Python/web/MCP tools require plan approval and policy gates.
- [ ] 10.4 Add tests for disallowed tool names and unsafe prompt refusals.

## 11. Error and validation handling

- [ ] 11.1 Render validation errors as non-fatal yellow chat messages.
- [ ] 11.2 Render runtime failures as red error messages.
- [ ] 11.3 Persist refusal, validation error, and runtime error messages.
- [ ] 11.4 Ensure failed tool calls still create failed `tool_trace` rows.
- [ ] 11.5 Add tests for validation, refusal, and runtime failure paths.

## 12. Documentation

- [ ] 12.1 Document Phase 5.10 chat workspace behavior.
- [ ] 12.2 Document keybindings.
- [ ] 12.3 Document chat-local commands.
- [ ] 12.4 Document plan approval behavior.
- [ ] 12.5 Document research-only safety boundary.

## 13. Validation

- [ ] 13.1 Run `cd vnalpha && pytest -q`.
- [ ] 13.2 Run targeted chat controller tests.
- [ ] 13.3 Run targeted chat persistence tests.
- [ ] 13.4 Run targeted TUI shell/layout tests.
- [ ] 13.5 Run targeted assistant trace/plan tests.
- [ ] 13.6 Run existing Phase 5.8 command tests.
- [ ] 13.7 Run existing Phase 5.9 assistant tests.
