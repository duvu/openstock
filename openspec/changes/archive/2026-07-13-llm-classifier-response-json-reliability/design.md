## Context

`vnalpha` already has classifier parsing in `vnalpha/src/vnalpha/assistant/response_parser.py` and a simple fallback retry in `vnalpha/src/vnalpha/assistant/intent.py`.  
Current behavior can still fail noisily when malformed classifier output is repeated, and parsing logic for JSON normalization/mapping is intertwined with intent-domain handling.

This change keeps the existing one-retry strategy and strengthens it with a dedicated parser module that is reused across response pathways.

## Goals / Non-Goals

**Goals:**
- Centralize robust JSON extraction/parsing for LLM responses into a dedicated, reusable assistant utility.
- Ensure every classifier output path uses the parser and returns either a validated parse result or a clear invalid-response error.
- Keep retry behavior deterministic: parse attempt(s) then bounded retry with stronger profile, then explicit failure.
- Add focused tests for invalid JSON, malformed wrappers, and retry behavior.

**Non-Goals:**
- Changing model routing policy except where necessary to preserve existing behavior.
- Expanding the assistant capability matrix (no new user-facing intents/tools).
- Adding retries for non-classifier stages beyond this response-contract requirement.

## Decisions

1) Create a dedicated parser module under `vnalpha/src/vnalpha/assistant/` (e.g. `response_json.py`) that provides:
   - `parse_json_response(raw: str, *, strict: bool = True) -> dict`
   - `extract_json_from_text(raw: str) -> str | None`
   - `parse_classifier_response(raw: str, *, user_prompt: str = "") -> IntentResult`
   - `parse_synthesis_response(raw: str) -> AssistantAnswer`
   
   Rationale: explicit module boundary for parsing keeps all parse-recovery behavior testable and reusable without scattering response-shape logic.

2) Keep `parse_intent_response` behavior compatibility:
   - strip markdown fences,
   - extract embedded JSON,
   - sanitize unexpected values.

   Rationale: avoids regressions on existing prompt patterns observed in tests/production logs.

3) Make retry semantics explicit in `IntentClassifier.classify`:
   - first classifier call → parse via shared parser,
   - on parse error retry LLM call with `ModelProfile.DEFAULT`,
   - parse retry response with the same parser,
   - if still invalid, raise `IntentClassificationError` with a clear invalid-response message.
   
   Rationale: matches current intent routing behavior while making the parse boundary explicit and deterministic.

4) Reuse parser in synthesizer path where feasible (`parse_synthesis_response`) with the same parse-error contract and clear invalid-response error wording.

## Risks / Trade-offs

- [Risk] Retrying only on parse failure may still leave non-parseable repeated model output.  
  → Mitigation: return explicit `IntentClassificationError` with sanitized raw-response preview and traceable stage for user-facing handling.

- [Risk] Centralizing parser logic can be seen as large change for a narrow bug.  
  → Mitigation: preserve current normalization semantics (aliases, defaulting) and only relocate behavior into dedicated utility functions.

- [Risk] More strict parse checks could reduce tolerance to loosely formatted responses.  
  → Mitigation: keep extraction helpers (`strip_markdown_fence`, embedded JSON extraction) and only error fast when no valid parse is possible.

## Migration Plan

1. Add new parser module and migrate classifier parse call sites.
2. Keep public helper names stable (`parse_intent_response`/`parse_synthesis_response`) by adapting imports to the new module so downstream callers are unaffected.
3. Add/update tests for parse edge cases and classifier retry path.
4. Run relevant test subset and then full `vnalpha` test/linters for confidence.
5. No DB or schema migration required; rollback is limited to reverting parser-module changes and test updates.

## Open Questions

- No blocking open questions identified for first-pass implementation.
