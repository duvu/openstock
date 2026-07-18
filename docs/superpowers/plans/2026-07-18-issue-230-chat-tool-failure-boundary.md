# Issue 230 Chat Tool Failure Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve sanitized, bounded actionable tool failures in prepared chat while keeping validation distinct and unexpected failures generic.

**Architecture:** Add one pure public-error sanitizer/length bound in `vnalpha.chat.errors`, correct the `TOOL_FAILED` transcript mapping, and catch only assistant-layer typed failures before the existing unexpected-exception fallback in `ChatController`. Tool trace and stage callbacks remain unchanged.

**Tech Stack:** Python 3.10+, pytest, DuckDB, uv, Ruff, OpenSpec.

---

### Task 1: Lock the chat-boundary contract with failing tests

**Files:**
- Create: `vnalpha/tests/test_issue_230_chat_tool_failures.py`
- Modify: `vnalpha/tests/test_chat_errors.py`

- [x] **Step 1: Add the typed tool failure integration test**

Construct a complete `PreparedAssistantTurn`, a real in-memory migrated DuckDB
chat session, and a `ChatController`. Replace only `_prepare_turn` and
`_execute_prepared_turn`; raise assistant `ToolExecutionError` with a readiness
reason, remediation, correlation ID, terminal control and bearer token. Assert
one visible `[TOOL FAILED]` message, no generic retry text, redacted token,
preserved actionable fields, and one persisted `message_type='tool_failed'` row.

- [x] **Step 2: Add validation and unexpected fallback tests**

Raise `AssistantInputValidationError`, `PlanValidationError`, and `RuntimeError`
from the same prepared boundary. Assert known validation persists as
`validation_error`; assert the runtime error keeps the exact generic retry text
and never exposes its detail.

- [x] **Step 3: Add public-text bound and mapping assertions**

Pass an oversized error through the typed path and assert the complete rendered
message is bounded by the prefix plus 4,096 public-detail characters while its
leading reason and remediation/correlation suffix remain available. Change the
existing enum mapping expectation from `tool_trace_event` to `tool_failed`.

- [x] **Step 4: Run the red tests**

Run: `cd vnalpha && uv run --extra dev pytest -q tests/test_issue_230_chat_tool_failures.py tests/test_chat_errors.py`

Expected: failures showing typed tool/validation exceptions still reach the
generic branch, tool text is unbounded/unsanitized, and `TOOL_FAILED` maps to
`tool_trace_event`.

### Task 2: Implement the minimal typed presentation mapping

**Files:**
- Modify: `vnalpha/src/vnalpha/chat/errors.py`
- Modify: `vnalpha/src/vnalpha/chat/controller.py`
- Modify: `vnalpha/src/vnalpha/chat/__init__.py`

- [x] **Step 1: Add the public-error sanitizer and correct transcript mapping**

Add `MAX_PUBLIC_ERROR_CHARS: Final = 4_096` and:

```python
def sanitize_public_error(message: str) -> str:
    sanitized = " ".join(sanitize_text(message).split())
    if len(sanitized) <= MAX_PUBLIC_ERROR_CHARS:
        return sanitized
    suffix_chars = MAX_PUBLIC_ERROR_CHARS * 3 // 4
    prefix_chars = MAX_PUBLIC_ERROR_CHARS - suffix_chars - 1
    return (
        sanitized[:prefix_chars].rstrip()
        + "…"
        + sanitized[-suffix_chars:].lstrip()
    )
```

Map `ChatErrorKind.TOOL_FAILED` to `"tool_failed"` and export the new public
helper/constant through `vnalpha.chat`.

- [x] **Step 2: Catch assistant-layer typed failures before the fallback**

Import `AssistantInputValidationError`, `PlanValidationError` and
`ToolExecutionError` from `vnalpha.assistant.errors`. In
`_handle_prepared_natural_language`, add exact typed branches before the broad
top-level fallback:

```python
except ToolExecutionError as exc:
    error_text = f"[TOOL FAILED] {sanitize_public_error(str(exc))}"
    self._on_message("red", error_text)
    self._persist_error_message(error_text, ChatErrorKind.TOOL_FAILED)
    return error_text
except (AssistantInputValidationError, PlanValidationError) as exc:
    error_text = format_validation_error(sanitize_public_error(str(exc)))
    self._on_message("yellow", error_text)
    self._persist_error_message(error_text, ChatErrorKind.VALIDATION)
    return error_text
```

Leave the unexpected fallback text and stage/tool callbacks unchanged.

- [x] **Step 3: Run focused green tests and Ruff**

Run: `cd vnalpha && uv run --extra dev pytest -q tests/test_issue_230_chat_tool_failures.py tests/test_chat_errors.py`

Expected: all selected tests pass.

Run: `cd vnalpha && uv run --extra dev ruff check src/vnalpha/chat tests/test_issue_230_chat_tool_failures.py tests/test_chat_errors.py`

Expected: exit 0.

### Task 3: Prove lifecycle compatibility and close OpenSpec evidence

**Files:**
- Modify: `openspec/changes/chat-data-provisioning-contract/tasks.md`
- Modify: `openspec/changes/chat-data-provisioning-contract/validation.md`

- [x] **Step 1: Run affected regressions**

Run the issue #163 provisioning, issue #228 lifecycle, staged response, chat
controller, TUI routing, R4 trace, plan approval and observability test files.
Expected: all selected tests pass with no changed stage ordering or tool status.

- [x] **Step 2: Exercise the controller/repository path manually**

Run an in-memory migrated DuckDB driver through
`ChatController.handle_natural_language` for typed tool, validation and runtime
failures. Inspect visible messages and persisted rows. Expected: `tool_failed`,
`validation_error`, and generic `error` respectively, with no duplicate generic
tool failure.

- [x] **Step 3: Run repository gates**

Run strict OpenSpec validation, Ruff, the full vnalpha suite, `make verify-r4`,
and the relevant package/root gates named by the OpenStock Makefile. Record each
as passed, failed, skipped, inconclusive or not run; do not infer unrun gates.

- [x] **Step 4: Update task and validation evidence**

Mark OpenSpec tasks 14-16 only after their evidence exists, and append exact
commands/outcomes to `validation.md`. Do not mark CI passed unless GitHub Actions
is green on the exact implementation commit.

### Task 4: Correct exact-commit review blockers before publication

**Files:**
- Modify: `vnalpha/src/vnalpha/tools/errors.py`
- Modify: `vnalpha/src/vnalpha/tools/ensure_current_symbol.py`
- Modify: `vnalpha/src/vnalpha/assistant/errors.py`
- Modify: `vnalpha/src/vnalpha/assistant/executor.py`
- Modify: `vnalpha/src/vnalpha/chat/errors.py`
- Modify: `vnalpha/src/vnalpha/chat/controller.py`
- Create: `vnalpha/tests/test_issue_230_chat_tool_failure_surfaces.py`

- [x] **Step 1: Reproduce trust and surface-parity defects**

Add red regressions proving that an arbitrary exception originating inside a
real tool remains generic, an unclassified assistant tool error remains generic,
approval preserves actionable tool/validation presentation, the legacy path
persists one semantic failure, and arbitrary Rich link/style markup is inert.

- [x] **Step 2: Preserve explicit public-failure provenance**

Carry an immutable `PublicToolFailure` through exact tool-layer and assistant-
layer actionable exception subtypes. Mark only non-ready
`data.ensure_current_symbol` results. Let unexpected tool runtime exceptions
retain their original type so the controller's generic catch owns them.

- [x] **Step 3: Reuse typed presentation across supported paths**

Use the same actionable and validation presentation helpers for immediate,
approved, and legacy prepared execution. Keep trace rows as
`tool_trace_event` and remove the legacy trace callback's duplicate semantic
failure persistence.

- [x] **Step 4: Bound work and neutralize Rich markup**

Crop oversized raw input before regex processing, retain the actionable
head/tail, escape remaining Rich markup, then enforce the final 4,096-character
bound.

- [ ] **Step 5: Recommit and repeat exact-SHA review/publication gates**

Run focused and full validation, five independent review lanes, the runtime
debugging audit, exact-commit GitHub Actions and PR/issue reconciliation on the
new full SHA. A pass recorded against the rejected candidate is not reusable.
