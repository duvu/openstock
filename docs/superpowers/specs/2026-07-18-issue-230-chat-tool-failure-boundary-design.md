# Issue 230 Chat Tool Failure Boundary Design

## Goal

Preserve actionable, public `ToolExecutionError` details across prepared
natural-language chat without weakening unexpected-exception redaction or the
stage/tool lifecycle fixed by issue #228.

## Boundary and data flow

`AssistantExecutor` converts tool-layer failures to
`vnalpha.assistant.errors.ToolExecutionError`. `AssistantApp.execute_prepared`
persists the assistant/prepared-turn failure and re-raises it. The chat
controller is the presentation boundary: it converts that typed failure into
one visible message and one transcript row. Tool trace callbacks continue to
own `RUNNING`/`SUCCESS`/`FAILED` events; the presentation mapping does not emit
or reinterpret stage events.

## Public failure contract

Chat error formatting will reuse `vnalpha.core.text_safety.sanitize_text`,
collapse whitespace, and cap public error detail at 4,096 characters. When the
detail is oversized, the cap retains both its identifying prefix and its
actionable suffix. This removes terminal controls, Rich tags and inline
credentials while keeping a current-symbol reason, bounded remediation and
correlation ID intact.
Typed tool failures receive a `[TOOL FAILED]` presentation and transcript type
`tool_failed`. Known assistant input and plan validation receive `[WARNING]`
and `validation_error`. Any other exception keeps the fixed generic retry text
and `error` transcript type.

The controller emits exactly one presentation for a typed failure. It does not
add a generic fallback afterward and does not synthesize an answer after failed
tool execution.

## Scope

The implementation changes only `chat/errors.py`, the prepared natural-language
handler in `chat/controller.py`, and focused tests. It does not redesign
readiness, exceptions, retries, tracing, approval, slash commands, providers or
the research-only security boundary.

## Verification

Focused tests drive the real controller and DuckDB chat repository with a real
`PreparedAssistantTurn`, replacing only the prepared execution seam. They prove
the public reason/remediation/correlation, redaction and length cap, persisted
message types, validation mapping, generic fallback and absence of duplicate
generic output. Existing issue #163/#228, stage, routing, trace and R4 tests prove
the surrounding lifecycle remains unchanged; manual QA drives the same
controller/repository path and inspects visible output plus transcript rows.
