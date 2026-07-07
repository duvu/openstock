# Phase 5.10 — OpenCode-style Research Chat Workspace

## Summary

Add a dedicated OpenSpec change for completing the `vnalpha` chat experience so the TUI behaves like an OpenCode-style research workspace rather than a simple one-shot assistant panel.

The current codebase already has a useful prototype:

```text
- VnAlphaApp imports and mounts a persistent ChatPanel.
- ChatPanel has a RichLog history area and an Input bar.
- User input can be routed to slash commands or AssistantApp.ask().
- Tool trace events can be emitted and rendered as RUNNING / SUCCESS / FAILED.
- AssistantApp and AssistantExecutor support an on_trace_event callback.
```

However, the implementation is not yet a complete chat workspace. There are still execution-path, layout, context, persistence, and UX gaps.

This change defines Phase 5.10 to close those gaps without expanding into broker execution, Python sandboxing, web retrieval, or ML ranking.

## Problem

The current TUI chat implementation is a prototype, not yet an OpenCode-style workspace.

Key issues:

```text
1. ChatPanel slash commands do not use the shared CommandExecutor path.
2. ChatPanel is mounted without a DB connection and can fail slash commands.
3. Natural-language chat is one-shot; it has no multi-turn context.
4. Chat transcript is not persisted as a first-class chat session/message model.
5. Answer streaming is absent; assistant output appears only after completion.
6. There is no plan-preview / approve / cancel flow for tool execution.
7. Split-pane layout is not structurally guaranteed; screens may overlay the panel.
8. Chat history, command recall, and workspace commands are incomplete.
9. Trace timeline is useful but not yet linked to persisted chat turns.
10. There is no targeted test suite for chat workspace behavior.
```

## Goals

- Provide a persistent bottom chat panel similar to OpenCode/Cursor-style terminal chat UX.
- Support both natural-language prompts and slash commands through one input bar.
- Route slash commands through the same `CommandExecutor` used by CLI and command screens.
- Preserve a first-class chat session and ordered message transcript.
- Support multi-turn context so follow-up questions can refer to previous symbols, commands, and tool outputs.
- Render tool trace timeline inside the chat pane.
- Add plan preview, approve/cancel, and no-execute modes.
- Add streaming answer support or a staged fallback if LLM streaming is unavailable.
- Keep all chat tools research-only.
- Add targeted regression tests for TUI chat behavior and assistant/tool integration.

## Non-goals

```text
- No broker orders.
- No portfolio allocation.
- No margin or account access.
- No automatic trading.
- No Python compute sandbox.
- No web retrieval sandbox.
- No MCP client expansion.
- No ML ranking.
- No change to scoring rules.
```

## User experience target

The target interaction should feel like:

```text
┌──────────────────────────────────────────────────────────────┐
│ Main research workspace                                      │
│ Watchlist / detail / outcomes / quality screens              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Chat                                                         │
│ You: /scan VN30                                              │
│ ✓ watchlist.scan SUCCESS 42ms                                │
│ Assistant: 12 candidates found. Top: FPT, MWG, MBB...        │
│                                                              │
│ You: explain the first one                                   │
│ Plan: candidate.explain(FPT), lineage, quality               │
│ Approve? [enter] approve | [e] edit | [esc] cancel           │
│ ✓ candidate.explain SUCCESS 35ms                             │
│ ✓ lineage.get_symbol_lineage SUCCESS 19ms                    │
│ ✓ quality.get_status SUCCESS 12ms                            │
│ Assistant: FPT is ranked #1 because...                       │
│ >                                                            │
└──────────────────────────────────────────────────────────────┘
```

## Scope

### In scope

```text
TUI split-pane shell
persistent ChatPanel
unified command execution
assistant conversation context
chat session/message schema
trace-to-chat-turn linkage
plan preview and approval
streaming answer callback or staged fallback
chat history and recall commands
chat-specific slash commands: /new, /clear, /context, /plan, /trace
TUI and assistant tests
research-only safety constraints
```

### Out of scope

```text
trade execution
portfolio/account integration
external web retrieval
Python code execution
broker API integration
LLM-driven mutation of scoring rules
```

## Acceptance summary

This change is complete when:

```text
- TUI has a true persistent main-workspace + chat split-pane layout.
- ChatPanel executes slash commands through CommandExecutor.
- ChatPanel can execute commands even when it creates its own short-lived DB connection.
- Natural-language prompts support multi-turn context.
- Chat transcript is persisted in chat_session and chat_message tables.
- Tool traces and assistant sessions are linked to chat turns.
- Plan preview/approve/cancel flow is available for assistant tool calls.
- Streaming answer events are supported, or the fallback staged output is explicit and tested.
- Chat commands /new, /clear, /context, /plan, and /trace are supported.
- Research-only policy remains enforced.
- Targeted tests cover layout shell, command routing, assistant chat, transcript persistence, trace events, and plan approval.
```
