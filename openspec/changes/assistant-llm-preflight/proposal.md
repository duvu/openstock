## Why

OpenStock already supports a LiteLLM/OpenAI-compatible transport, explicit
model profiles and capability declarations, strict JSON-Schema requests with
capability-aware fallback, a controlled `json_schema` → `json_object`
downgrade, and typed routing/config failures. What is missing for MVP1 is
*deployment acceptance*: the repository does not verify the exact endpoint,
model alias, capability and startup behaviour used by the MVP host, and an LLM
misconfiguration currently surfaces as a generic per-turn runtime error rather
than a clear, actionable startup diagnostic.

Issue #165 makes the optional AI layer operationally predictable using one
verified model route, and keeps deterministic slash/data commands usable when
the model is unavailable.

## What Changes

- add a bounded, typed assistant preflight `run_llm_preflight` in
  `vnalpha.assistant.preflight` returning `LLMPreflightResult` with a
  `LLMPreflightCode` that distinguishes missing configuration, missing API key,
  missing model/routing, unreachable gateway, authentication failure, missing
  model on the gateway, unsupported structured output and a generic probe
  failure — each with redaction-safe detail and remediation;
- the preflight reuses `LLMGatewayConfig.validate()` and the existing gateway
  chat path via an injectable probe (tests use a fake gateway; no live network),
  records the successful `ModelRouteDecision` identity, and never surfaces
  secrets or prompt content;
- add a `vnalpha preflight` CLI command (human and `--json` output) that exits
  non-zero when natural-language chat is unavailable while telling the operator
  deterministic commands remain usable;
- surface the degraded-mode message in `vnalpha ask` when the LLM route is
  unavailable, and upgrade the `openstock-verify` assistant check to the typed
  preflight;
- document the single verified-model MVP1 decision and the preflight in the
  config templates.

## Capabilities

### Added Capabilities

- `assistant-llm-preflight`: a bounded, typed, redaction-safe startup preflight
  that verifies one MVP1 LLM route and drives degraded-mode behaviour.

## Impact

- new `vnalpha/src/vnalpha/assistant/preflight.py`,
  `vnalpha/src/vnalpha/cli_app/preflight.py`; wiring in
  `cli_app/app.py`, `cli_app/ask.py`; `packaging/scripts/openstock-verify`;
  docs in `.env.example`, `packaging/config/vnalpha.env`;
- tests in `vnalpha/tests/test_issue_165_llm_preflight.py`;
- No change to the read-only research boundary. Raw LLM storage stays disabled
  by default. Automated tests use a fake gateway; no provider names are guessed.
