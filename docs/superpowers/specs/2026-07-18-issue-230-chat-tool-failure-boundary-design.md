# Issue 230 Chat Tool Failure Boundary Design

## Goal

Preserve actionable, public `ToolExecutionError` details across prepared
natural-language chat without weakening unexpected-exception redaction or the
stage/tool lifecycle fixed by issue #228.

## Boundary and data flow

The tool layer marks only explicitly public readiness data as a structured
`PublicToolFailure` and raises `ActionableToolError`. `AssistantExecutor`
preserves that provenance as `ActionableToolExecutionError`. Arbitrary tool
exceptions and ordinary `ToolExecutionError` values never receive that marker
and therefore remain internal. `AssistantApp.execute_prepared` persists the
assistant/prepared-turn failure and re-raises it. The chat controller is the
presentation boundary: it renders only the actionable subtype and keeps every
other execution failure on the generic path.

The same typed presentation helper owns immediate prepared execution,
post-approval prepared execution, and the compatibility/legacy assistant path.
Post-approval dispatch sends only sandbox approval-required plans through the
sandbox approval service; safe prepared data plans execute directly after the
user approval is persisted.
Tool trace callbacks continue to own `RUNNING`/`SUCCESS`/`FAILED` events; trace
failure events do not create a second semantic chat error.

## Public failure contract

Chat error formatting will reuse `vnalpha.core.text_safety.sanitize_text`,
collapse whitespace, escape Rich markup, cap pre-sanitization scan work, and cap
the complete public error at 4,096 characters. It sanitizes the structured
reason, remediation and correlation fields independently before composition,
so no raw head/tail crop can orphan a credential marker while the bounded
remediation and correlation suffix stays visible. This removes terminal
controls, prevents truncation or cross-field composition from reactivating
links/styles, and redacts
quoted inline credentials, URI user-info, Basic credentials, JWT-like tokens
and PEM private-key bodies. Standalone Basic values are validated as encoded
`user:password`, including credentials cut at the bounded scan edge. Bearer
credential candidates accept the complete token alphabet; an explicit
research-domain vocabulary preserves bearer bonds, shares, notes, instruments
and securities while other candidates fail closed. Parsed HTTP(S) and database
host/port endpoints, including driver qualifiers, IPv6, query parameters and
sentence punctuation, remain unchanged. A no-`@` authority with a valid numeric
port remains an endpoint because it has no syntactic credential evidence;
invalid-port/cropped authorities and malformed authorities that still contain
userinfo are redacted.

Only `ActionableToolExecutionError` receives a `[TOOL FAILED]` presentation and
transcript type `tool_failed`. Known assistant input and plan validation receive
`[WARNING]` and `validation_error`. Ordinary tool failures, arbitrary nested
tool exceptions, and any other exception keep the fixed generic retry text and
`error` transcript type.

The controller emits exactly one presentation for a typed failure. It does not
add a generic fallback afterward and does not synthesize an answer after failed
tool execution. Tool and assistant lifecycle rows remain diagnostically useful,
but their error summaries are sanitized and bounded before persistence.
File-backed exception records apply their declared content mode recursively to
message, stacktrace, context, likely cause and suggested next step, and preserve
legacy bearer key/value redaction when using the shared sanitizer. Metadata mode
retains no content in exception-record content fields without changing the
established semantics of structural identifiers in other consumers. Redacted
nested context accepts JSON-valid key types while normalizing common camelCase
and delimiter spellings for canonical sensitive-key prefix and suffix forms.
Prefix matching excludes ambiguous `token_*` operational metrics such as the
real memory-status budget fields.

## Scope

The implementation adds one structured public-failure value at the existing
tool/assistant error seam, marks only the current-symbol readiness failure with
it, and centralizes its controller presentation across supported natural-
language paths. It does not redesign readiness, retries, slash commands,
providers or the research-only security boundary.

## Verification

Focused tests drive the real controller and DuckDB chat repository with a real
`PreparedAssistantTurn`, including immediate execution, approval, the legacy
compatibility branch, and an arbitrary exception originating inside the real
assistant executor/tool trace. They prove public reason/remediation/correlation,
redaction, markup neutralization, bounds, persisted message types, validation
mapping, generic fallback, legacy post-approval parity, the established private
assistant error contract, real safe-plan approval dispatch, complete-record
observability redaction, and absence of duplicate generic output. Existing
issue #163/#228, stage, routing, trace and R4 tests prove the surrounding
lifecycle remains unchanged; manual QA drives the same controller/repository
path and inspects visible output plus transcript rows.
