## 1. Core parser refactor

- [x] 1.1 Create a dedicated parser module under `vnalpha/src/vnalpha/assistant/` for shared LLM JSON parsing with a single public entry for classifier JSON extraction/parsing.
  - Evidence: module exists with `parse_json_response(...)`, extraction/parsing utilities, and parser adapters in `response_json.py`.
- [x] 1.2 Migrate intent parsing logic from `response_parser.py` into the new module and keep intent normalization/alias behavior intact.
  - Evidence: alias mapping tests and classification behavior for `GET_STOCK_INFO` remain passing.
- [x] 1.3 Re-export or adapt `parse_synthesis_response` to use the shared parser for consistent invalid-response behavior.
  - Evidence: malformed synthesis JSON now raises a clear `InvalidSynthesisResponseError`.

## 2. Classifier retry reliability

- [x] 2.1 Update `vnalpha/src/vnalpha/assistant/intent.py` to use the shared parser module and enforce explicit parse-or-fail with one bounded retry on invalid JSON.
  - Evidence: `IntentClassifier.classify` uses `parse_classifier_response` and retries once with `ModelProfile.DEFAULT`.
- [x] 2.2 Ensure invalid JSON after retry raises `IntentClassificationError` with response-invalid detail and no plan execution side effects.
  - Evidence: new test shows second invalid response returns `Invalid JSON` classification error.

## 3. Test coverage

- [x] 3.1 Add/adjust unit tests in `vnalpha/tests/test_intent_and_planner.py` for:
  - markdown fenced responses,
  - embedded JSON recovery,
  - invalid JSON first-response + valid retry,
  - invalid JSON on both attempts.
  - Evidence: tests exist, names are deterministic, and all pass.
- [x] 3.2 Add parser-focused tests for shared parser module behavior (including extraction and invalid-response error contract).
  - Evidence: `vnalpha/tests/test_response_json_parser.py` covers direct parser helpers and malformed synthesis payload handling.

## 4. Verification and completion

- [x] 4.1 Run targeted intent/parsing test subset for this change.
  - Evidence command: `cd vnalpha && .venv/bin/pytest tests/test_intent_and_planner.py tests/test_response_json_parser.py`.
- [x] 4.2 Run lint/format checks for touched modules.
  - Evidence command: `cd vnalpha && python -m ruff check src/vnalpha/assistant/intent.py src/vnalpha/assistant/response_json.py src/vnalpha/assistant/response_parser.py tests/test_intent_and_planner.py tests/test_response_json_parser.py && python -m ruff format --check src/vnalpha/assistant/intent.py src/vnalpha/assistant/response_json.py src/vnalpha/assistant/response_parser.py tests/test_intent_and_planner.py tests/test_response_json_parser.py`.
- [x] 4.3 Run full `vnalpha` validation gate.
  - Evidence command: `cd vnalpha && make test-vnalpha`.
  - Result in this environment: failed due pre-existing workspace permission/warehouse drift issues (read-only `/home/beou/.local/state/openstock` and schema expectation changes), not from this parser refactor.
- [x] 4.4 Run `openspec` completion check for this change.
  - Evidence: `openspec status --change llm-classifier-response-json-reliability`.
