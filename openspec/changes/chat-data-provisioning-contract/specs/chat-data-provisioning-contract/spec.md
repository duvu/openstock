# Capability: chat data provisioning contract

## ADDED Requirements

### Requirement: One shared current-symbol provisioning operation

Natural-language chat and slash commands SHALL provision bounded current-symbol
analysis inputs through one typed application operation,
`ensure_current_symbol_ready`, which delegates to the existing fail-closed
readiness and data-availability services. No duplicate provisioning logic SHALL
exist in TUI or controller code.

#### Scenario: Empty warehouse analysis provisions before analysis
- **GIVEN** an empty warehouse
- **WHEN** a user asks `Phân tích FPT`
- **THEN** the plan contains an explicit `data.ensure_current_symbol` step before
  the analysis step, and provisioning runs before analysis succeeds.

#### Scenario: Slash and natural language share the operation
- **WHEN** `/analyze FPT` and the equivalent natural-language request run
- **THEN** both call `ensure_current_symbol_ready` and produce equivalent
  persisted evidence.

### Requirement: Fresh data reuse and bounded refresh

Fresh persisted data SHALL be reused without unnecessary provider requests. An
explicit refresh SHALL perform bounded incremental work and disclose each action.

#### Scenario: Fresh reuse
- **GIVEN** fresh persisted data satisfying the freshness policy
- **WHEN** the operation runs without refresh
- **THEN** the outcome is `REUSED` and no provider download is required.

#### Scenario: Explicit refresh
- **GIVEN** an explicit refresh intent
- **WHEN** the operation runs with `refresh=True`
- **THEN** it performs bounded incremental provisioning and reports the actions
  taken (`sync_ohlcv`, `build_canonical`, `build_features`, `score_symbol`).

### Requirement: Explicit, correlated, fail-closed trace

Every provisioning action SHALL appear in the tool/audit trace under one
correlation chain. A failed or partial provisioning turn SHALL NOT promote
incomplete analysis or corrupt existing valid data.

#### Scenario: Provisioning appears on trace
- **WHEN** the assistant executes a provisioning step
- **THEN** a `tool_trace` row is recorded for `data.ensure_current_symbol`.

#### Scenario: Fail-closed on non-ready provisioning
- **GIVEN** provisioning that does not reach a ready state
- **WHEN** the plan also contains an analysis step
- **THEN** the analysis step does not execute and a typed remediation error is
  returned.

### Requirement: Read-only research boundary preserved

The operation SHALL remain bounded to the current symbol and its benchmark. It
SHALL NOT perform arbitrary or unrestricted data fetching, and the unrestricted
`data.fetch` tool SHALL remain command-only and never eligible for autonomous
assistant plans.

#### Scenario: Unrestricted fetch stays non-autonomous
- **WHEN** eligibility is evaluated
- **THEN** `data.ensure_current_symbol` is assistant- and autonomous-eligible
  while `data.fetch` is not.

### Requirement: Actionable typed failures survive the chat boundary

Every supported prepared natural-language chat path SHALL render and persist an
explicitly public structured assistant tool failure exactly once. Immediate,
post-approval, and compatibility/legacy execution are all supported paths. The
failure SHALL be stored as
`tool_failed`. Its public text SHALL be sanitized, markup-neutralized and
length-bounded while retaining the available readiness reason, remediation and
correlation ID. Known request and plan validation failures SHALL use validation
presentation. Ordinary tool failures and unexpected exceptions, including an
exception originating inside a tool, SHALL continue to use the generic retry
presentation and SHALL NOT expose exception details. Length truncation SHALL NOT
reactivate escaped markup, and public sanitization SHALL redact common structured
credential forms before persistence.

Affected tool-trace and assistant-session audit error summaries SHALL also be
sanitized and length-bounded while retaining truthful failure status and error
type.

#### Scenario: Current-symbol provisioning fails
- **GIVEN** `data.ensure_current_symbol` raises an explicitly public structured
  tool failure containing a readiness reason, remediation and correlation ID
- **WHEN** prepared natural-language execution reaches the chat boundary
- **THEN** one visible and persisted `tool_failed` message retains those public
  details, contains no terminal controls or secrets, and no second generic error
  is emitted.

#### Scenario: Approved current-symbol provisioning fails
- **GIVEN** a current-symbol plan is previewed and approved
- **WHEN** its explicitly public provisioning failure reaches chat
- **THEN** the same `tool_failed` presentation and persistence contract applies.

#### Scenario: Legacy current-symbol provisioning fails
- **GIVEN** the compatibility assistant path emits a failed trace and then raises
  the explicitly public provisioning failure
- **WHEN** it reaches chat
- **THEN** the trace remains `tool_trace_event`, exactly one actionable
  `tool_failed` row is persisted, and no generic duplicate is emitted.

#### Scenario: Approved legacy current-symbol provisioning fails
- **GIVEN** the compatibility assistant path previews a current-symbol plan
- **WHEN** approval execution raises an explicitly public provisioning or known
  validation failure
- **THEN** chat persists the corresponding `tool_failed` or `validation_error`
  presentation once and emits no generic duplicate.

#### Scenario: Known validation fails
- **GIVEN** prepared natural-language preparation raises a known request or plan
  validation error
- **WHEN** it reaches the chat boundary
- **THEN** one sanitized, bounded `validation_error` message is rendered and
  persisted.

#### Scenario: Unexpected execution fails
- **GIVEN** prepared natural-language preparation or execution raises an
  unexpected exception
- **WHEN** it reaches the chat boundary
- **THEN** the existing generic retry message is rendered and persisted as a
  runtime error without exposing the exception text.

#### Scenario: Unexpected exception originates inside a tool
- **GIVEN** an allowlisted tool raises an arbitrary runtime exception containing
  internal or credential-bearing detail
- **WHEN** the executor and chat boundary handle it
- **THEN** the failed trace remains truthful while chat renders only the generic
  runtime error and persists none of the internal detail.

#### Scenario: Long public failure contains markup and credential forms
- **GIVEN** an explicitly public failure contains an oversized Rich link/style
  sequence and structured credential text
- **WHEN** chat sanitizes, bounds, renders and persists it
- **THEN** the final text remains within the public bound, Rich parses no active
  spans, and no credential payload is retained.

#### Scenario: Unexpected tool failure is audited
- **GIVEN** an allowlisted tool raises an unexpected exception containing a
  structured credential form
- **WHEN** tool and assistant lifecycle rows are finalized as failed
- **THEN** both rows retain truthful failure type/status but their bounded error
  summaries contain no credential payload.
