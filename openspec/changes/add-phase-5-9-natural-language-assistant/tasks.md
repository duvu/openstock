# Tasks: Phase 5.9 Natural-Language Research Assistant

## 1. Assistant core models

- [x] 1.1 Add `vnalpha.assistant.models` with assistant session, intent result, tool plan, plan step, assistant answer, and refusal models.
- [x] 1.2 Add `vnalpha.assistant.errors` with typed assistant errors.
- [x] 1.3 Add status enums for assistant sessions and LLM traces.
- [x] 1.4 Add serialization helpers for plan and answer JSON.
- [x] 1.5 Add unit tests for model serialization and validation.

## 2. LLM gateway client boundary

- [x] 2.1 Add configurable LLM Gateway client for assistant-only calls.
- [x] 2.2 Configure model, endpoint, timeout, retry, and max output limits through settings/env.
- [x] 2.3 Ensure raw prompt/response storage is configurable and disabled by default if sensitive.
- [x] 2.4 Add redaction hooks for prompt/response trace summaries.
- [x] 2.5 Add tests using a fake/stub model client.

## 3. Intent classifier

- [x] 3.1 Add intent taxonomy:
  - [x] `scan_candidates`
  - [x] `filter_candidates`
  - [x] `compare_symbols`
  - [x] `explain_symbol`
  - [x] `review_quality`
  - [x] `show_lineage`
  - [x] `summarize_watchlist`
  - [x] `create_research_note`
  - [x] `show_history`
  - [x] `unsupported_or_unsafe`
- [x] 3.2 Implement classifier prompt and schema-constrained output.
- [x] 3.3 Add deterministic pre-rules for obvious unsafe requests.
- [x] 3.4 Add confidence and clarification handling.
- [x] 3.5 Add classification fixture tests.

## 4. Plan builder

- [x] 4.1 Implement plan builder from `IntentResult` to `AssistantPlan`.
- [x] 4.2 Build plans only from allowlisted Phase 5.8 tools.
- [x] 4.3 Add argument extraction for symbols, dates, universes, filters, and note text.
- [x] 4.4 Add plan validation against tool schemas.
- [x] 4.5 Add plan preview output for CLI/TUI.
- [x] 4.6 Add tests for plan generation by intent.

## 5. Tool allowlist and executor

- [x] 5.1 Reuse Phase 5.8 local tool registry.
- [x] 5.2 Add assistant executor that calls only allowlisted local tools.
- [x] 5.3 Forbid network, web fetch/search, Python execution, MCP, raw SQL, filesystem, code mutation, broker/account/order/portfolio tools.
- [x] 5.4 Persist every executed tool call in `tool_trace`.
- [x] 5.5 Add tests proving unsafe/unavailable tool plans fail closed.

## 6. Assistant persistence

- [x] 6.1 Add `assistant_session` table.
- [x] 6.2 Add `llm_trace` table.
- [x] 6.3 Optionally extend `tool_trace` with nullable `assistant_session_id`.
- [x] 6.4 Add repository helpers:
  - [x] `create_assistant_session`
  - [x] `finish_assistant_session`
  - [x] `create_llm_trace`
  - [x] `finish_llm_trace`
  - [x] `list_assistant_sessions`
- [x] 6.5 Add migration tests for additive tables.

## 7. Grounded answer synthesizer

- [x] 7.1 Implement synthesizer that uses tool outputs only.
- [x] 7.2 Include basis/evidence, risks/caveats, missing data, and tool trace summary.
- [x] 7.3 Prevent model from overriding candidate score, candidate class, setup type, or data-quality state.
- [x] 7.4 Add missing-data response templates.
- [x] 7.5 Add tests for hallucination prevention using fake tool outputs.

## 8. CLI integration

- [x] 8.1 Add `vnalpha ask "<question>"`.
- [x] 8.2 Add CLI flags:
  - [x] `--date`
  - [x] `--show-plan`
  - [x] `--trace`
  - [x] `--no-execute` for plan preview only
- [x] 8.3 Render final answer with Rich.
- [x] 8.4 Render plan and trace summary when requested.
- [x] 8.5 Return non-zero exit code for refused, validation-error, or failed sessions when appropriate.
- [x] 8.6 Add CLI tests with a fake LLM client.

## 9. TUI integration

- [x] 9.1 Add natural-language assistant input surface or mode.
- [x] 9.2 Add assistant answer panel.
- [x] 9.3 Add expandable plan view.
- [x] 9.4 Add expandable tool trace view.
- [x] 9.5 Show refusal and missing-data messages without crashing the TUI.
- [x] 9.6 Add TUI smoke tests for assistant prompt and answer rendering.

## 10. Safety and refusal policy

- [x] 10.1 Implement deterministic precheck for trading execution/account/portfolio/broker requests.
- [x] 10.2 Refuse buy/sell instruction and guaranteed prediction requests.
- [x] 10.3 Refuse requests requiring unavailable web, Python, MCP, or code mutation tools.
- [x] 10.4 Refuse requests to hide trace, bypass tool policy, or fabricate missing data.
- [x] 10.5 Add safety fixture tests for unsafe prompts.

## 11. Documentation

- [x] 11.1 Document `vnalpha ask` usage.
- [x] 11.2 Document supported natural-language intent families.
- [x] 11.3 Document assistant plan and trace output.
- [x] 11.4 Document refusal policy and limitations.
- [x] 11.5 Document how Phase 5.9 depends on Phase 5.8 tool contracts.

## 12. Validation

- [x] 12.1 Run `cd vnalpha && pytest -q`.
- [x] 12.2 Run assistant targeted tests.
- [x] 12.3 Run Phase 5.8 command-layer tests to prove no regression.
- [x] 12.4 Run Phase 5 E2E fixture tests to prove no regression.
- [x] 12.5 Manually smoke-test:

```bash
vnalpha ask "Show strongest candidates today" --show-plan --trace
vnalpha ask "Why is FPT in the watchlist?"
vnalpha ask "Compare FPT, VNM, and MWG"
vnalpha ask "Which candidates have weak data quality?"
vnalpha ask "Buy FPT now"
```

The last command must be refused.
