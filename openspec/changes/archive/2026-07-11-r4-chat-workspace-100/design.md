# Design: R4 Chat Workspace 100% POC Completion

## Design objective

R4 becomes complete when ChatPanel and ChatController behave like a real persistent terminal chat workspace:

```text
TUI input -> ChatPanel -> ChatController -> command/assistant/plan/trace -> chat_session/chat_message audit trail
```

The key design change is to make persistence and session lifecycle part of the controller runtime path, not only repository-level helper functionality.

## Core architecture

```text
VnAlphaApp
  └── ChatPanel(target_date)
        ├── bootstrap chat session
        ├── construct ChatController(chat_session_id=...)
        └── delegate all user actions

ChatController
  ├── handle_turn(raw)
  ├── classify_input(raw)
  ├── handle_slash_command(raw)
  ├── handle_natural_language(question)
  ├── handle_chat_local_command(cmd, args)
  ├── approve_pending_plan()
  ├── cancel_pending_plan()
  ├── persist message/audit rows
  └── persist trace events

warehouse.chat_repo
  ├── create_chat_session
  ├── get_or_create_active_chat_session
  ├── resume_latest_active_chat_session
  ├── append_chat_message
  ├── clear_visible_messages
  ├── append_trace_event
  └── list_trace_events_for_session
```

## Session lifecycle design

### ChatPanel bootstrap

On initialization or mount, ChatPanel must obtain a chat session before constructing the controller.

Preferred behavior:

```text
1. Open short-lived warehouse connection through the configured connection factory.
2. Run migrations.
3. Resume latest active chat session for surface='tui-chat' and target_date if one exists.
4. Otherwise create a new chat_session.
5. Construct ChatController with chat_session_id.
6. Close the bootstrap connection.
```

Fallback behavior:

If session creation fails, ChatPanel may still render the UI, but it must show a visible warning and R4 must not be marked 100% until that failure is fixed.

### `/new`

`/new` must:

```text
1. finish or leave previous session active according to documented policy;
2. create a new chat_session;
3. switch ChatController._chat_session_id to the new id;
4. clear pending plan state;
5. emit and persist a system/local-command result.
```

Preferred policy: previous session remains queryable and is marked `finished` if the product wants a single active session per date. If multiple active sessions are allowed, docs must state this explicitly.

## Persistence design

### Persist at controller boundary

ChatController should include dedicated persistence methods:

```python
def _persist_user_message(content: str, message_type: str = 'plain_text', **meta): ...
def _persist_assistant_message(content: str, message_type: str = 'answer', **meta): ...
def _persist_system_message(content: str, message_type: str = 'system', **meta): ...
def _persist_plan_preview(plan, content: str): ...
def _persist_plan_decision(decision: str, content: str): ...
def _persist_command_result(result): ...
```

These methods should be best-effort: persistence failure should not crash the TUI, but failure must be rendered as a warning and covered by tests where practical.

### Required persisted turn types

| Runtime event | Required persisted rows |
|---|---|
| natural-language question | `user/plain_text` or `user/prompt` |
| assistant answer | `assistant/answer` |
| assistant refusal | `assistant/refusal` |
| assistant runtime error | `system/runtime_error` or `error/runtime_error` |
| slash command input | `user/slash_command` |
| slash command result | `assistant/slash_command_result` with `research_session_id` if available |
| chat-local command input | `user/chat_local_command` |
| chat-local command output | `system/chat_local_command_result` |
| plan preview | `assistant/plan_preview` with `plan_json` |
| plan approval | `user/plan_approval` |
| plan cancellation | `user/plan_cancel` |
| approved execution result | `assistant/answer` or `assistant/refusal` |
| tool trace | `trace/tool_trace_event` |

## Slash command flow

```text
handle_slash_command(raw)
  -> persist user/slash_command
  -> CommandExecutor.execute(raw)
  -> render result
  -> persist assistant/slash_command_result
  -> include research_session_id when available from CommandResult metadata
```

Command execution failures should persist a runtime/tool error row.

## Natural-language flow

```text
handle_natural_language(question)
  -> persist user/prompt
  -> no_execute=True ask for answer + plan
  -> evaluate plan permissions before pending storage
  -> if auto safe-read and plan safe:
       run ask no_execute=False
       persist assistant answer/refusal
       persist trace events via trace callback
  -> if plan-only:
       persist assistant/plan_preview with plan_json
  -> if approval mode:
       persist assistant/plan_preview with plan_json
       store pending plan
  -> if denied:
       persist assistant/refusal
```

## Plan approval flow

```text
approve_pending_plan()
  -> if no plan: render no-op or warning, optionally persist system message
  -> evaluate pending plan permissions again before execution
  -> persist user/plan_approval
  -> run ask no_execute=False using stored question
  -> persist assistant answer/refusal/error
  -> clear pending plan state
```

Re-evaluating permission on approval is required because pending state may be stale or manipulated during tests/refactors.

## Plan cancellation flow

```text
cancel_pending_plan()
  -> if pending plan exists: persist user/plan_cancel
  -> clear pending plan state
  -> render cancellation confirmation
```

If no plan exists, a warning may be rendered but should not create a misleading plan-cancel audit row.

## Clear behavior

`/clear` default behavior:

```text
persist user/chat_local_command for /clear
hide visible rows with is_visible=false and hidden_at=<now>
preserve all rows for audit
render visible log-cleared confirmation
```

`/clear --forget` behavior:

```text
persist user/chat_local_command for /clear --forget first if possible
delete rows only after explicit flag
render destructive confirmation
```

If deleting the `/clear --forget` command row itself is unavoidable, docs must state that destructive deletion removes the entire session transcript.

## Trace design

Trace persistence already exists when `chat_session_id` is set. The missing piece is session bootstrap.

After this change:

```text
ChatPanel mount -> active chat_session_id
ChatController trace callback -> append_trace_event(chat_session_id=active_id)
/trace -> list_trace_events_for_session(active_id)
```

## Permission design

Plan permission evaluation must happen at two points:

```text
1. before storing any pending plan;
2. immediately before approving/running a pending plan.
```

Permission outcomes:

| Permission state | Behavior |
|---|---|
| ALLOW | may auto-run in safe-read mode |
| ASK | may become pending only in PLAN_THEN_APPROVE mode |
| DENY | refuse in current mode; not pending |
| HARD_DENY | refuse permanently; never pending; never approvable |

## Tests required

### Repository helper tests

Keep the existing helper tests. They prove schema and CRUD behavior.

### Controller-level tests

Add a new test file:

```text
vnalpha/tests/test_r4_controller_persistence.py
```

It must call controller methods and inspect database rows after each runtime path.

Required tests:

```text
handle_turn(natural language) persists user prompt
handle_natural_language auto safe-read persists assistant answer
handle_natural_language refusal persists assistant refusal
handle_slash_command persists slash input and result
handle_turn('/help') persists chat-local input and output
handle_turn('/plan only') persists mode change output
plan preview persists plan_json
approve_pending_plan persists approval and answer
cancel_pending_plan persists cancellation
restricted planned tool is not pending
restricted pending plan cannot be approved if injected
trace callback persists event for ChatPanel-created session
```

### Textual/TUI tests

Add or update tests to prove:

```text
VnAlphaApp mounts ChatPanel with non-null _chat_controller
ChatPanel controller has non-null _chat_session_id after mount
ChatPanel target_date is stored in chat_session
ChatPanel input delegates to controller and preserves session id
/trace works in app-created session
```

### Validation target

Add:

```makefile
verify-r4:
	cd vnalpha && pytest -q \
		tests/test_r4_chat_panel.py \
		tests/test_r4_controller_persistence.py \
		tests/test_r4_clear.py \
		tests/test_r4_permissions.py \
		tests/test_r4_session.py \
		tests/test_r4_trace.py
```

## Documentation updates

Update:

```text
vnalpha/docs/13-r0-r4-completion-matrix.md
vnalpha/docs/14-r0-r4-validation-report.md
vnalpha/docs/12-operator-runbook.md if needed
```

R4 may be set to 100% only when documentation references actual passing command output for `make verify-r4` and no known R4 blocker remains.
