## Why

Classifier responses occasionally arrive malformed or wrapped in non-JSON text (for example markdown fences or partial payload fragments), causing the assistant flow to fail with unhelpful parse errors. This blocks user requests even when a retry could recover.

The current parser behavior is mixed with classification mapping logic in one function, so parse behavior changes are hard to reason about and test consistently across response types.

## What Changes

- Create a dedicated, reusable JSON parser module for assistant model responses with strict parse semantics, controlled fallbacks, and deterministic error objects.
- Route classifier responses through a single parse entry that always either returns a validated payload or emits an explicit invalid-response error.
- Keep the retry contract explicit: on parse failure in classifier stage, retry the LLM call with stronger routing/profile and retry with the same parser before surfacing a hard failure.
- Enforce consistent invalid-response handling for all classifier/synthesizer responses using the shared parser utility surface.
- Add unit and integration-level tests for valid response parsing, malformed JSON recovery paths, and bounded retry behavior.

## Capabilities

### New Capabilities
- `none`: N/A

### Modified Capabilities
- `natural-language-research-assistant`: Update classifier parsing/response-contract behavior to enforce "parse-or-fail-with-error-and-retry" semantics and extract parser logic into a maintainable module.

## Impact

- Code touched: `vnalpha/src/vnalpha/assistant/intent.py`, `vnalpha/src/vnalpha/assistant/response_parser.py` (and/or new parser module under `vnalpha/src/vnalpha/assistant/`).
- Shared models/errors: `vnalpha/src/vnalpha/assistant/models.py`, `vnalpha/src/vnalpha/assistant/errors.py`.
- Tests: `vnalpha/tests/test_intent_and_planner.py` plus possible new parser-focused tests around malformed classifier/synthesizer responses.
- No database schema migration is required; no product-boundary expansion (read-only research, no broker/account/trading features).
