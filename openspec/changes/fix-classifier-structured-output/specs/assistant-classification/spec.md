# Assistant Classification Specification Delta

## ADDED Requirements

### Requirement: Structured classifier output is validated within each gateway route attempt

The system SHALL treat a model route as successful for classification only after the provider response envelope, text content, JSON object, and typed intent envelope have all been validated.

#### Scenario: Invalid primary structured output falls back

- **WHEN** the primary classifier route returns HTTP success with malformed or schema-invalid content
- **THEN** the gateway SHALL record that route attempt as a structured-output failure
- **AND** SHALL continue to the next allowed distinct route within the bounded attempt budget
- **AND** SHALL return only a validated `IntentResult`.

#### Scenario: Valid primary structured output succeeds

- **WHEN** the primary classifier route returns a valid typed intent envelope
- **THEN** the gateway SHALL emit route success
- **AND** SHALL not invoke a fallback route.

### Requirement: Classifier retry attempts are materially distinct and bounded

The system SHALL NOT issue an identical same-endpoint, same-model, same-prompt classifier retry merely because two model profiles resolve to the same route.

#### Scenario: SMALL and DEFAULT resolve to the same model

- **WHEN** the initial route fails structured validation
- **AND** the configured stronger profile resolves to the same endpoint and model ID
- **THEN** the system SHALL either use one explicitly different repair prompt/capability variant or skip the duplicate route
- **AND** SHALL record the duplicate skip or repair variant
- **AND** SHALL remain within the configured total attempt budget.

#### Scenario: All bounded attempts fail

- **WHEN** every allowed distinct classifier attempt returns invalid structured output or a fallbackable malformed response
- **THEN** the system SHALL stop retrying at the bounded limit
- **AND** SHALL raise a typed retryable classification-unavailable error
- **AND** SHALL NOT infer an intent or select tools from unvalidated prose.

### Requirement: Intent response fields are strictly validated

The classifier SHALL validate the complete intent response envelope before normalization, policy evaluation, or plan construction.

#### Scenario: Invalid confidence

- **WHEN** `confidence` is non-numeric, non-finite, or outside `[0, 1]`
- **THEN** classification SHALL fail with a typed validation error
- **AND** SHALL NOT silently replace the value with a default.

#### Scenario: Invalid entities

- **WHEN** `entities` is not a JSON object
- **THEN** classification SHALL fail with a typed validation error.

#### Scenario: Invalid safety flags

- **WHEN** `safety_flags` is null, a scalar, an object, or contains non-string entries
- **THEN** classification SHALL fail with a typed validation error
- **AND** SHALL NOT coerce a string into a character list.

#### Scenario: Invalid clarification fields

- **WHEN** `needs_clarification` is not a boolean
- **OR** `clarification_question` is neither null nor a string
- **OR** clarification is required but the question is blank
- **THEN** classification SHALL fail with a typed validation error.

#### Scenario: Unknown but structurally valid intent

- **WHEN** the envelope is structurally valid but the normalized intent is not supported and has no accepted legacy alias
- **THEN** the classifier SHALL map the intent fail-closed to `unsupported_or_unsafe`.

### Requirement: Conservative JSON recovery remains supported

The classifier parser SHALL retain deterministic recovery for known harmless wrappers and SHALL NOT use permissive semantic repair as the default behavior.

#### Scenario: Markdown-fenced object

- **WHEN** the model returns one valid classifier object inside one outer Markdown code fence
- **THEN** the parser SHALL extract and validate the object without requiring a fallback attempt.

#### Scenario: Object embedded in prose

- **WHEN** the model returns surrounding prose containing one balanced valid classifier JSON object
- **THEN** the parser SHALL extract and validate that object without requiring a fallback attempt.

#### Scenario: Truncated or pseudo-JSON content

- **WHEN** the model returns truncated JSON, single-quoted pseudo-JSON, or content requiring invented fields or values
- **THEN** the parser SHALL reject the content unless an explicitly documented deterministic syntax-only transform applies
- **AND** any transformed result SHALL still pass the typed envelope validator.

### Requirement: Provider response envelopes are hardened

The gateway SHALL validate provider response structure before recording success.

#### Scenario: Null, empty, or non-text message content

- **WHEN** `message.content` is missing, null, blank, or not a string
- **THEN** the route SHALL fail as a fallbackable malformed-response error
- **AND** SHALL NOT emit a successful call event.

#### Scenario: Malformed choices or message shape

- **WHEN** `choices`, the first choice, or its message has an invalid shape
- **THEN** the route SHALL fail as a fallbackable malformed-response error.

### Requirement: Structured-output capability is explicit

The gateway SHALL support declared provider/model capability modes for strict JSON Schema, JSON-object-only, and prompt-only structured output.

#### Scenario: Strict schema provider

- **WHEN** a route is configured for strict JSON Schema
- **THEN** the request SHALL include the full named intent JSON Schema with strict validation enabled.

#### Scenario: Capability-related strict-schema rejection

- **WHEN** a strict-schema request receives a recognized capability-related rejection
- **THEN** the gateway MAY downgrade once to the configured compatible structured-output mode
- **AND** SHALL record the downgrade
- **AND** SHALL NOT treat unrelated HTTP 400 errors as capability downgrade signals.

### Requirement: Classification failures always terminalize lifecycle records

Every classification path after assistant-session creation SHALL leave the classify trace and assistant session in a terminal state.

#### Scenario: Expected classifier failure

- **WHEN** classification raises a typed assistant error
- **THEN** the classify trace SHALL be finished as `FAILED`
- **AND** the assistant session SHALL be finished as `FAILED`
- **AND** persisted error metadata SHALL contain only a sanitized summary and correlation ID by default.

#### Scenario: Unexpected parser or orchestration failure

- **WHEN** an unexpected exception occurs during preparation after session creation
- **THEN** a final catch-all terminalization path SHALL finish the assistant session as `FAILED`
- **AND** SHALL re-raise the exception for diagnostics
- **AND** SHALL not leave the session in `RUNNING`.

### Requirement: User-visible classifier errors are safe and actionable

The normal CLI/TUI transcript SHALL display a stable classification-unavailable message rather than raw parser output or classifier content.

#### Scenario: Exhausted classifier attempts

- **WHEN** bounded classifier attempts are exhausted
- **THEN** the user SHALL receive concise retry/model-selection guidance
- **AND** a correlation/error ID
- **AND** SHALL NOT receive raw model output fragments by default.

### Requirement: Structured-output observability excludes raw content by default

The system SHALL record sufficient allowlisted metadata to diagnose structured-output reliability without persisting or logging raw classifier content by default.

#### Scenario: Structured route attempt is observed

- **WHEN** a classifier route is attempted
- **THEN** observability SHALL record route/model identity, attempt count, structured-output mode, prompt variant, parse status, validation error code, response character count, response SHA-256, fallback state, duplicate-route state, and correlation ID as applicable
- **AND** SHALL omit the raw classifier body unless the existing explicit raw-storage policy is enabled.

### Requirement: Deterministic safety and read-only boundaries remain unchanged

The structured-output recovery mechanism SHALL NOT weaken deterministic prechecks, policy enforcement, or the product's read-only research boundary.

#### Scenario: Deterministically unsafe request

- **WHEN** the deterministic precheck identifies a prohibited execution-related request
- **THEN** the classifier SHALL return the existing fail-closed unsafe result without invoking the LLM.

#### Scenario: Unvalidated model prose suggests an action

- **WHEN** a malformed classifier response contains tool, trade, order, broker, account, portfolio, or execution instructions
- **THEN** the system SHALL ignore that prose as unvalidated content
- **AND** SHALL NOT create an execution plan or broaden product scope.
