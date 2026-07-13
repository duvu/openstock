# Design: Classifier structured-output recovery

## Goals

- Make structured-output validity part of a model route attempt.
- Preserve bounded, deterministic fallback behavior.
- Validate the complete classifier envelope before policy or planning.
- Ensure persistence lifecycle reaches a terminal state on every failure.
- Expose actionable diagnostics without leaking classifier content.

## Architecture

### 1. Structured gateway API

Add a generic structured call alongside the existing unstructured API:

```python
T = TypeVar("T")

class StructuredParseError(Exception):
    error_code: str


def chat_structured(
    self,
    messages: list[dict],
    *,
    schema_name: str,
    json_schema: dict[str, Any],
    parse: Callable[[str], T],
    stage: str,
    task_type: str | None = None,
    model_profile: ModelProfile | str | None = None,
    route_metadata: Mapping[str, Any] | None = None,
    repair_instruction: str | None = None,
) -> tuple[T, dict]:
    ...
```

`chat()` remains the compatibility surface for unstructured callers. Shared private helpers may construct routes, invoke providers, and normalize usage.

For each distinct route, the structured path performs:

```text
select route
  -> select provider capability mode
  -> call provider
  -> validate API envelope and text content
  -> conservative JSON extraction
  -> typed envelope validation
  -> emit success and return parsed value
```

Provider call success is emitted only after structured parsing succeeds. A parse/validation failure emits a structured failure event and proceeds to the next bounded route.

### 2. Distinct-route and repair policy

Route identity is at least `(endpoint/provider, model_id, structured_output_mode, prompt_variant)`.

- The first route uses the normal classifier prompt.
- After a structured parse failure, the next allowed attempt uses a correction instruction requiring one JSON object with no Markdown or prose.
- If SMALL and DEFAULT resolve to the same endpoint/model, do not issue the same prompt variant twice.
- A same model may be reused once only when the prompt variant or structured-output capability mode is materially different and the attempt budget allows it.
- Record skipped duplicate routes.

Transport retry remains inside one provider-route call and retains the existing configured retry bound. Structured retries do not multiply transport retries without an explicit total-attempt cap.

### 3. Provider capability modes

Represent structured-output support explicitly:

- `strict_json_schema`: send OpenAI-compatible `response_format.type=json_schema`, including schema name, strict flag, and full JSON Schema.
- `json_object_only`: send `response_format.type=json_object` and rely on local typed validation.
- `prompt_only`: omit `response_format`, retain the JSON-only system contract, and rely on local validation.

A capability-related 400 may downgrade once on the same route from `strict_json_schema` to `json_object_only`. The downgrade is not used for arbitrary 400 responses and is recorded. Configuration defaults must preserve compatibility with existing endpoints.

### 4. Intent envelope

Define a Pydantic model or equivalent strict validator:

```python
class IntentResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, allow_inf_nan=False)
    entities: dict[str, JsonValue] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    safety_flags: list[str] = Field(default_factory=list)
```

Validation rules:

- `intent` must be a nonblank string before normalization and alias mapping.
- `entities` must be an object; arrays and scalars are invalid.
- `confidence` must be finite and within `[0, 1]`; numeric strings are rejected unless project-wide validation convention explicitly permits them.
- `needs_clarification` must be a boolean, not truthy coercion.
- `clarification_question` must be null or a string; it must be nonblank when clarification is required.
- `safety_flags` must be an array of nonblank strings; null, string, object, and mixed arrays are invalid unless an explicit backward-compatibility normalization is documented.
- Extra fields are rejected to expose provider drift.

After structural validation, normalize intent casing and hyphen/underscore aliases. Unknown intent values map fail-closed to `unsupported_or_unsafe`; structurally invalid values never reach policy or planning.

### 5. Parser behavior

Keep deterministic recovery for:

- one outer Markdown code fence;
- one balanced JSON object embedded in surrounding prose.

Do not automatically repair truncated JSON, replace quote styles, remove arbitrary commas, or invent missing fields. Every recovered object must still pass the typed envelope.

Parser exceptions must not contain raw response text. Use stable categories such as:

- `empty_content`
- `non_text_content`
- `json_decode_failed`
- `root_not_object`
- `schema_validation_failed`
- `unsupported_intent_value`

An internal diagnostic may include response length and SHA-256, never the body unless raw storage is explicitly enabled.

### 6. Gateway envelope hardening

Validate all provider response layers before returning:

- response JSON root object;
- non-empty `choices` list;
- first choice object;
- message object;
- `message.content` is a nonblank string;
- usage is an object or safely normalized to `{}`.

Malformed envelopes are fallbackable and use safe errors without provider body fragments by default.

### 7. Lifecycle correctness

`AssistantApp.prepare()` owns assistant-session terminalization.

- Expected classification errors finish classify trace as `FAILED`, finish assistant session as `FAILED`, and re-raise a safe `AssistantError` subtype.
- Add a final `except Exception` after typed branches. It must finish the assistant session idempotently using a sanitized summary and correlation ID, then re-raise.
- Trace finishing and session finishing must tolerate repeated calls or use an explicit terminal-state guard.
- Persisted `error_json` must not contain raw classifier content by default.

### 8. User-facing error contract

Expose a stable classification-unavailable exception containing:

- safe public message;
- correlation/error ID (`cls-<short id>`);
- retryable flag;
- internal category not rendered as raw model content.

The TUI/CLI renderer shows the safe message and existing retry/model-selection guidance. The transcript must not show response previews.

### 9. Observability

Emit allowlisted classifier structured-output fields:

```text
stage
model_id
model_profile
provider_or_endpoint_key
route_attempt
transport_attempts
structured_output_mode
prompt_variant
parse_status
validation_error_code
response_chars
response_sha256
duplicate_route_skipped
capability_downgraded
fallback_used
correlation_id
raw_stored
```

Do not emit `raw_response` in normal classifier logs. When existing raw-storage policy is enabled, raw content must follow the same redaction/access controls as other stored raw prompts/responses.

## Alternatives considered

### Retry only in `IntentClassifier`

Rejected as the durable solution because gateway routing would still treat malformed structured content as success, route observability would remain split, and duplicate routes would be difficult to prevent consistently.

### Permissive JSON repair library

Rejected as the primary mechanism because it can hide provider regressions and alter meaning. Conservative extraction plus typed validation is more predictable.

### Fail immediately without fallback

Rejected because malformed structured output is often transient or provider-specific, and configured route fallback should handle it within a bounded budget.

## Security and product boundary

The classifier output is untrusted until schema validation completes. No tool selection, plan construction, or policy bypass may use unvalidated prose. Deterministic unsafe checks remain before the LLM. This change remains entirely within the read-only research boundary.
