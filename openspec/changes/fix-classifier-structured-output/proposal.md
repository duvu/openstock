# Change: Harden classifier structured-output recovery

## Current status

Issue #59 is reproducible from the current `main` code path. `IntentClassifier.classify()` calls `LLMGatewayClient.chat()`, but classifier parsing and envelope validation occur only after the gateway has accepted a model route as successful. Consequently, malformed structured content cannot trigger gateway route fallback. The retry then reuses the same messages and may resolve to the same model ID.

The current parser conservatively supports a Markdown fence and one balanced JSON object embedded in prose. Those recovery behaviors are useful and must remain. However, the response contract is not typed, `response_schema` is collapsed to `json_object`, classifier logs include a raw response preview, and unexpected parser/conversion failures can escape lifecycle terminalization.

## Dependencies

- Existing model-routing configuration, route resolver, fallback decisions, and observability events.
- Existing assistant error hierarchy and assistant/LLM trace persistence.
- Existing raw-storage opt-in policies.
- Pydantic already used by the project; no new validation framework is required.

No trading, brokerage, portfolio, account, order, or execution capability is introduced. The read-only research boundary remains unchanged.

## Verified existing capability

- Deterministic unsafe-keyword precheck remains fail-closed before any LLM call.
- Gateway transport and malformed API-envelope failures can already fall through to configured model routes.
- Classifier JSON recovery already handles one outer Markdown fence and one balanced object embedded in prose.
- Assistant classify traces are explicitly finished on ordinary exceptions.
- Raw prompt persistence is already opt-in.

## Remaining gap

1. Structured content validity is outside the gateway route-attempt loop.
2. The classifier schema is only `{ "type": "json_object" }` and does not validate fields.
3. The retry may be an identical same-model/same-prompt request.
4. Null or non-string `message.content` is not explicitly rejected before success emission.
5. Classifier field types are partially coerced rather than validated; malformed collections can still fail unpredictably or be silently changed.
6. Raw classifier fragments are exposed through exceptions and normal structured logs.
7. Unexpected failures after session creation are not guaranteed to terminalize the assistant session.

## Proposed change

Introduce a bounded structured-output gateway path that validates model content inside each model-route attempt. The gateway returns only after the provided parser/validator succeeds. Structured parse or schema failures are fallbackable to the next distinct configured route.

Add a strict typed intent envelope and convert every classifier decode/validation failure into a stable `IntentClassificationError` subtype carrying a safe public summary and an internal error code. Preserve conservative fence/embedded-object extraction before typed validation.

Make retry behavior materially different by adding an explicit repair instruction and by deduplicating equivalent model routes. Where provider capability allows, send the full JSON Schema using strict `json_schema`; otherwise use a declared bounded downgrade (`json_object` or prompt-only) and record the mode.

Guarantee classify-trace and assistant-session terminalization for all expected and unexpected failures. Persist and display safe error metadata only; raw output is retained solely under the existing explicit raw-storage/debug policy.

## User-visible outcome

A transient invalid classifier response either recovers via a distinct validated route or ends with a concise message such as:

> The classifier returned an invalid structured response after the allowed attempts. Retry the request or select another classification model. Error ID: `cls-…`

Raw parser text and model output fragments are not shown by default.

## Non-goals

- Permissive semantic repair of truncated, single-quoted, or arbitrary pseudo-JSON.
- Inferring an intent from unvalidated prose.
- Weakening deterministic policy checks or intent policy.
- Refactoring synthesis structured output except for reusable gateway primitives where compatibility is preserved.
- Adding autonomous data fetch, unrestricted tools, or any trading-execution capability.
- Implementing a broad TUI command redesign; a minimal retry affordance may be included only where an existing retry path exists.

## Compatibility and migration impact

- Keep `LLMGatewayClient.chat()` behavior compatible for unstructured callers.
- Add `chat_structured()` or an optional validator callback without forcing immediate migration of synthesis callers.
- Extend fake clients and tests with a compatible structured method.
- Existing routing configuration remains valid. New structured-output capability settings default conservatively so existing OpenAI-compatible endpoints continue to operate.
- Observability fields are additive; raw content fields are removed or gated for classifier events.

## Acceptance summary

- Invalid primary output can recover through a distinct validated route.
- Duplicate same-model/same-prompt attempts are not issued.
- All malformed classifier envelopes produce typed failures.
- Null/non-text content is fallbackable.
- All failure paths terminalize traces and sessions.
- Diagnostics contain route/attempt/hash/status but not raw output by default.
- Existing safe parser recovery and read-only research policy remain intact.
