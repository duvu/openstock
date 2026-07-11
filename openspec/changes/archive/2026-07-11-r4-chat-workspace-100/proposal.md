# Proposal: Complete R4 Chat Workspace to 100% POC Definition

## Summary

Add a focused OpenSpec change to move R4 — OpenCode-style Chat Workspace — from the current partial implementation to **100% complete within the agreed POC scope**.

This does not mean unlimited production perfection. It means R4 is complete against its own terminal-first, local-first, research-only POC definition, with no known blocker remaining inside that scope.

## Current state from code review

R4 has already closed several major gaps:

- ChatPanel now delegates input to ChatController.
- ChatPanel approval and cancellation call ChatController methods.
- ChatPanel no longer owns the old command registry / assistant dispatch path.
- Chat repository supports `chat_session` and `chat_message`.
- `/clear` now supports transcript-preserving hide behavior with `is_visible` and `hidden_at`.
- Trace persistence exists when `chat_session_id` is set.
- Permission-state helpers and plan permission checks exist.

However, the current implementation should not yet be considered 100% because:

1. ChatPanel constructs ChatController without creating or resuming a chat session.
2. ChatController only persists selected error/refusal/trace paths; normal user prompts, assistant answers, slash command inputs/results, local command inputs/results, plan previews, approvals, and cancellations are not guaranteed to persist through the actual controller flow.
3. Several persistence tests validate repository helpers directly instead of proving `ChatController.handle_turn()` persists each turn type.
4. `/trace` persistence is useful only after a session exists; session bootstrapping is incomplete.
5. The docs and completion matrix currently claim R4 90%, but those claims are not yet fully backed by controller-level evidence.
6. There is no R4-only verification target that acts as a hard completion gate.

## Goal

Raise R4 from approximately 74–78% to **100% POC-complete** by closing all in-scope chat workspace gaps with implementation, tests, and validation evidence.

## Non-goals

- No broker integration.
- No order placement.
- No account, portfolio, margin, allocation, transfer, or trading execution.
- No general-purpose shell agent.
- No raw SQL agent.
- No arbitrary Python execution agent.
- No filesystem write agent.
- No web-browsing agent.
- No MCP tool surface for R4.
- No production multi-user server.
- No R5 local runtime/server dependency.
- No full LLM integration test that requires a real API key in CI.
- No visual regression framework beyond Textual headless/pilot coverage.

## In-scope R4 completion definition

R4 is 100% POC-complete when all of the following are true:

```text
1. ChatPanel always starts with an active chat_session_id.
2. ChatPanel delegates all input, approval, and cancellation to ChatController.
3. ChatController owns orchestration for slash commands, chat-local commands, natural language, plans, trace, and persistence.
4. Every real controller turn is persisted through ChatController, not only through repository helper tests.
5. `/clear` preserves transcript by default and requires an explicit destructive flag to delete rows.
6. `/new` starts a new session and preserves the previous session transcript.
7. `/context` reflects actual controller/session state.
8. `/plan` controls execution mode deterministically.
9. `/trace` reads persisted trace events for the active session.
10. Restricted tools cannot become pending plans and cannot be approved later.
11. Safe read-only plans can auto-run; approval-required plans can become pending only in approval mode.
12. Controller-level tests cover every persisted turn type.
13. Textual headless tests prove ChatPanel session bootstrap inside VnAlphaApp.
14. R4 docs and completion matrix match the actual implementation.
15. `make verify-r4` passes and is listed in validation evidence.
```

## Success criteria

The implementation is complete only when these commands pass or are recorded with explicit justified exceptions:

```bash
make lint-vnalpha
make test-vnalpha
make verify-r4
python -m pytest \
  vnalpha/tests/test_r4_chat_panel.py \
  vnalpha/tests/test_r4_controller_persistence.py \
  vnalpha/tests/test_r4_clear.py \
  vnalpha/tests/test_r4_permissions.py \
  vnalpha/tests/test_r4_session.py \
  vnalpha/tests/test_r4_trace.py
```

R4 may be marked **100%** only after:

- `vnalpha/docs/13-r0-r4-completion-matrix.md` records R4 as 100% with evidence;
- `vnalpha/docs/14-r0-r4-validation-report.md` includes `make verify-r4` output;
- all R4 OpenSpec tasks in this change are complete;
- no remaining R4 blocker is open.

## Completion principle

Do not mark R4 100% because the OpenSpec exists. Mark it 100% only after the actual ChatPanel and ChatController runtime path satisfies the spec and tests prove it.
