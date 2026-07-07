# Review: R4 Chat Workspace Remaining Gaps

## Review basis

This review is based on the current `main` implementation of:

```text
vnalpha/src/vnalpha/tui/widgets/chat_panel.py
vnalpha/src/vnalpha/tui/app.py
vnalpha/src/vnalpha/chat/controller.py
vnalpha/src/vnalpha/chat/safety.py
vnalpha/src/vnalpha/chat/modes.py
vnalpha/src/vnalpha/warehouse/chat_repo.py
vnalpha/src/vnalpha/warehouse/migrations.py
vnalpha/tests/test_chat_panel.py
vnalpha/tests/test_chat_controller.py
vnalpha/tests/test_r4_chat_panel.py
vnalpha/tests/test_r4_persistence.py
vnalpha/tests/test_r4_clear.py
vnalpha/tests/test_r4_permissions.py
vnalpha/tests/test_r4_session.py
vnalpha/tests/test_r4_trace.py
vnalpha/docs/13-r0-r4-completion-matrix.md
vnalpha/docs/14-r0-r4-validation-report.md
```

## Current R4 estimate

```text
R4 current estimate: 74–78%
R4 target estimate after this change: 100% POC-complete
```

## Already closed

### ChatPanel delegation

ChatPanel has been simplified into a view/controller adapter:

```text
ChatPanel input -> ChatController.handle_turn(raw)
ChatPanel approve -> ChatController.approve_pending_plan()
ChatPanel cancel -> ChatController.cancel_pending_plan()
```

The old local ChatPanel paths such as command registry dispatch and direct assistant dispatch have been removed from the widget.

### Chat repository and schema

`chat_session` and `chat_message` exist. `chat_message` has core metadata fields:

```text
role
content
message_type
assistant_session_id
research_session_id
tool_trace_ids_json
plan_json
metadata_json
```

Migrations add `is_visible` and `hidden_at` columns for audit-preserving `/clear` behavior.

### Clear behavior

`clear_visible_messages(..., forget=False)` hides rows by setting `is_visible=false` and `hidden_at`. `forget=True` deletes rows.

### Trace persistence

ChatController wraps the trace callback and persists trace events when `chat_session_id` exists.

### Permission helpers

Permission states exist for safe, approval-required, denied, and permanently restricted tool classes. Plan permission evaluation exists before pending storage.

## Remaining blockers

### BLOCKER-1: ChatPanel does not bootstrap a real chat session

ChatPanel currently constructs ChatController without creating or resuming a `chat_session_id`. As a result, persistence and trace behavior remain inactive unless a session is manually injected or `/new` is called.

R4 cannot be 100% until ChatPanel starts with an active session.

### BLOCKER-2: Controller-level persistence is incomplete

ChatController renders many messages to the UI but does not persist all real controller turns through the actual runtime path.

The missing or weak paths include:

```text
user prompt
assistant answer
slash command input
slash command result
chat-local command input
chat-local command result
plan preview
plan approval
plan cancellation
assistant answer after approval
```

Error/refusal persistence exists, but that is not enough for a persistent chat workspace.

### BLOCKER-3: Persistence tests are too helper-centric

Current persistence tests call `append_chat_message()` directly. That validates repository helpers, but it does not prove ChatController itself persists each turn type.

R4 needs controller-level tests that call:

```text
ChatController.handle_turn(...)
ChatController.handle_slash_command(...)
ChatController.handle_natural_language(...)
ChatController.approve_pending_plan()
ChatController.cancel_pending_plan()
```

and then inspect `chat_message` rows.

### BLOCKER-4: `/new` and resume semantics are not sufficient for 100%

`/new` can create a new session, but initial session creation/resume is not part of ChatPanel mount.

The product needs deterministic behavior:

```text
first ChatPanel mount -> creates session if none exists
reload for same target date -> resumes latest active session if configured
/new -> creates new session and switches controller context
previous session remains queryable
```

### BLOCKER-5: Plan persistence and approval audit are incomplete

Plan preview may be rendered without a persisted `plan_json`. Approval and cancellation decisions may be visible in the UI without audit rows.

R4 needs exact audit rows for:

```text
plan_preview
plan_approval
plan_cancel
approval_execution_result
```

### BLOCKER-6: Docs currently overclaim R4 completion

The completion matrix claims R4 has persistence for all turn types. The runtime code path does not yet prove that. The validation report references R4 test counts, but those tests are not sufficient to prove controller-owned persistence.

Docs must be corrected or updated after implementation evidence exists.

## Definition of done for R4 100%

R4 can be declared 100% only when:

```text
1. ChatPanel starts with active chat_session_id.
2. Every controller runtime turn persists appropriate chat_message rows.
3. Repository helper tests and controller-level tests both exist.
4. Textual app tests prove ChatPanel has an active session after mount.
5. Plan lifecycle is fully auditable.
6. Restricted plan behavior is tested at controller level.
7. /trace reads persisted events for the active session created by ChatPanel.
8. make verify-r4 exists and passes.
9. Completion matrix and validation report are corrected.
10. No R4 blocker remains open.
```
