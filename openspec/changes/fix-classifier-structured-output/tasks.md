# Tasks

## Phase 1 — Contract and parser correctness

- [ ] 1.1 Add a strict typed classifier response envelope with explicit validation for intent, confidence, entities, clarification fields, safety flags, finite numeric bounds, and extra fields.
  - Evidence: focused unit tests demonstrating valid envelopes and each rejected field shape.
- [ ] 1.2 Refactor classifier parsing to preserve Markdown-fence and balanced-object extraction while removing raw response previews from public exceptions.
  - Evidence: existing recovery tests pass; malformed-output tests assert stable error codes and no raw body leakage.
- [ ] 1.3 Introduce typed structured-output/classification error categories and a safe public classification-unavailable error with correlation ID.
  - Evidence: unit tests assert all JSON and schema failures are `AssistantError` subclasses with stable safe messages.
- [ ] 1.4 Remove or gate normal classifier `raw_response` logging under the existing explicit raw-storage policy.
  - Evidence: log-capture test proves raw output is absent by default.

## Phase 2 — Gateway structured-output routing

- [ ] 2.1 Add a backward-compatible structured gateway API or validator callback that validates content inside each model-route attempt.
  - Depends on: 1.1–1.3.
  - Evidence: gateway unit test where invalid primary content falls through to a valid fallback route.
- [ ] 2.2 Harden provider response-envelope validation for choices, message, nonblank string content, and usage shape.
  - Evidence: null, list, empty, and missing content cases are fallbackable and never emit route success.
- [ ] 2.3 Support declared structured-output capability modes (`strict_json_schema`, `json_object_only`, `prompt_only`) and pass the full intent JSON Schema when configured.
  - Evidence: request-payload tests for each capability mode and bounded capability downgrade.
- [ ] 2.4 Add explicit route/prompt deduplication and a materially different repair prompt variant after structured parse failure.
  - Evidence: SMALL and DEFAULT resolving to the same model do not produce an identical same-model/same-prompt call; duplicate skip is observable.
- [ ] 2.5 Bound the combined provider, transport-retry, structured-repair, and route-fallback attempt budget.
  - Evidence: all-invalid test asserts exact maximum calls and terminal typed failure.
- [ ] 2.6 Extend `FakeLLMClient` and other test doubles without breaking existing unstructured-call tests.
  - Evidence: full assistant test suite imports and executes existing fakes unchanged or through documented compatibility adapters.

## Phase 3 — Classifier integration and lifecycle

- [ ] 3.1 Migrate `IntentClassifier.classify()` to the structured gateway path and remove the current external identical retry loop.
  - Depends on: Phase 2.
  - Evidence: classifier tests cover primary recovery, fallback recovery, repair prompt, and all-attempts-invalid.
- [ ] 3.2 Preserve deterministic unsafe precheck before any model call and ensure unvalidated content never reaches intent policy or plan construction.
  - Evidence: unsafe-precheck test records zero LLM calls and fail-closed result.
- [ ] 3.3 Make classify trace completion idempotent and include safe structured-output diagnostic summaries.
  - Evidence: persistence test proves one terminal classify trace for success and failure paths.
- [ ] 3.4 Add final catch-all terminalization in `AssistantApp.prepare()` using sanitized metadata and correlation ID.
  - Evidence: injected unexpected exception leaves assistant session terminal `FAILED`, not `RUNNING`.
- [ ] 3.5 Ensure persisted session and trace errors exclude raw classifier output unless the raw-storage flag is explicitly enabled.
  - Evidence: database assertions for default and opt-in modes.

## Phase 4 — Operator UX and observability

- [ ] 4.1 Render a concise retryable classification error in CLI/TUI and include the correlation/error ID.
  - Evidence: renderer or snapshot test contains no parser preview and includes retry/model guidance.
- [ ] 4.2 Emit allowlisted structured-output telemetry: route, attempt, mode, prompt variant, parse status, validation code, response length/hash, duplicate skip, capability downgrade, fallback usage, and correlation ID.
  - Evidence: event-capture tests for successful primary, fallback recovery, and terminal failure.
- [ ] 4.3 Integrate with an existing retry affordance if present; do not add unbounded automatic retries.
  - Evidence: retry action executes one new bounded turn and preserves audit/session separation.

## Phase 5 — Validation and completion

- [ ] 5.1 Add the complete focused test matrix for provider-ignored response format, Markdown fence, embedded object, invalid confidence, invalid entities, invalid safety flags, invalid clarification fields, non-text content, duplicate model routes, all-invalid attempts, terminal lifecycle, and raw-content suppression.
- [ ] 5.2 Run focused assistant and model-routing tests.
  - Evidence record: exact command, result, date, environment, and test output reference.
- [ ] 5.3 Run repository formatting, lint, type-check, and unit/integration gates required by root Make targets.
  - Evidence record: exact commands and results; blocked/unrun checks remain explicitly blocked/unrun.
- [ ] 5.4 Verify packaging and dependency impact; confirm no new validation dependency is introduced unless justified.
- [ ] 5.5 Run OpenSpec validation for `fix-classifier-structured-output` and record completion evidence.
- [ ] 5.6 Update issue #59 and PR description with implementation evidence mapped to each acceptance criterion.

## Completion gate

The change is complete only when malformed structured output can recover through a distinct validated attempt, every exhausted path fails with a typed safe error, all traces/sessions terminate, raw classifier content is absent by default, and the read-only research boundary remains unchanged.
