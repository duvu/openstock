# Tasks: Phase 5.9 Natural-Language Research Assistant

## 1. Assistant core models

- [ ] 1.1 Add `vnalpha.assistant.models` with assistant session, intent result, tool plan, plan step, assistant answer, and refusal models.
- [ ] 1.2 Add `vnalpha.assistant.errors` with typed assistant errors.
- [ ] 1.3 Add status enums for assistant sessions and LLM traces.
- [ ] 1.4 Add serialization helpers for plan and answer JSON.
- [ ] 1.5 Add unit tests for model serialization and validation.

## 2. LLM gateway client boundary

- [ ] 2.1 Add configurable LLM Gateway client for assistant-only calls.
- [ ] 2.2 Configure model, endpoint, timeout, retry, and max output limits through settings/env.
- [ ] 2.3 Ensure raw prompt/response storage is configurable and disabled by default if sensitive.
- [ ] 2.4 Add redaction hooks for prompt/response trace summaries.
- [ ] 2.5 Add tests using a fake/stub model client.

## 3. Intent classifier

- [ ] 3.1 Add intent taxonomy:
  - [ ] `scan_candidates`
  - [ ] `filter_candidates`
  - [ ] `compare_symbols`
  - [ ] `explain_symbol`
  - [ ] `review_quality`
  - [ ] `show_lineage`
  - [ ] `summarize_watchlist`
  - [ ] `create_research_note`
  - [ ] `show_history`
  - [ ] `unsupported_or_unsafe`
- [ ] 3.2 Implement classifier prompt and schema-constrained output.
- [ ] 3.3 Add deterministic pre-rules for obvious unsafe requests.
- [ ] 3.4 Add confidence and clarification handling.
- [ ] 3.5 Add classification fixture tests.

## 4. Plan builder

- [ ] 4.1 Implement plan builder from `IntentResult` to `AssistantPlan`.
- [ ] 4.2 Build plans only from allowlisted Phase 5.8 tools.
- [ ] 4.3 Add argument extraction for symbols, dates, universes, filters, and note text.
- [ ] 4.4 Add plan validation against tool schemas.
- [ ] 4.5 Add plan preview output for CLI/TUI.
- [ ] 4.6 Add tests for plan generation by intent.

## 5. Tool allowlist and executor

- [ ] 5.1 Reuse Phase 5.8 local tool registry.
- [ ] 5.2 Add assistant executor that calls only allowlisted local tools.
- [ ] 5.3 Forbid network, web fetch/search, Python execution, MCP, raw SQL, filesystem, code mutation, broker/account/order/portfolio tools.
- [ ] 5.4 Persist every executed tool call in `tool_trace`.
- [ ] 5.5 Add tests proving unsafe/unavailable tool plans fail closed.

## 6. Assistant persistence

- [ ] 6.1 Add `assistant_session` table.
- [ ] 6.2 Add `llm_trace` table.
- [ ] 6.3 Optionally extend `tool_trace` with nullable `assistant_session_id`.
- [ ] 6.4 Add repository helpers:
  - [ ] `create_assistant_session`
  - [ ] `finish_assistant_session`
  - [ ] `create_llm_trace`
  - [ ] `finish_llm_trace`
  - [ ] `list_assistant_sessions`
- [ ] 6.5 Add migration tests for additive tables.

## 7. Grounded answer synthesizer

- [ ] 7.1 Implement synthesizer that uses tool outputs only.
- [ ] 7.2 Include basis/evidence, risks/caveats, missing data, and tool trace summary.
- [ ] 7.3 Prevent model from overriding candidate score, candidate class, setup type, or data-quality state.
- [ ] 7.4 Add missing-data response templates.
- [ ] 7.5 Add tests for hallucination prevention using fake tool outputs.

## 8. CLI integration

- [ ] 8.1 Add `vnalpha ask "<question>"`.
- [ ] 8.2 Add CLI flags:
  - [ ] `--date`
  - [ ] `--show-plan`
  - [ ] `--trace`
  - [ ] `--no-execute` for plan preview only
- [ ] 8.3 Render final answer with Rich.
- [ ] 8.4 Render plan and trace summary when requested.
- [ ] 8.5 Return non-zero exit code for refused, validation-error, or failed sessions when appropriate.
- [ ] 8.6 Add CLI tests with a fake LLM client.

## 9. TUI integration

- [ ] 9.1 Add natural-language assistant input surface or mode.
- [ ] 9.2 Add assistant answer panel.
- [ ] 9.3 Add expandable plan view.
- [ ] 9.4 Add expandable tool trace view.
- [ ] 9.5 Show refusal and missing-data messages without crashing the TUI.
- [ ] 9.6 Add TUI smoke tests for assistant prompt and answer rendering.

## 10. Safety and refusal policy

- [ ] 10.1 Implement deterministic precheck for trading execution/account/portfolio/broker requests.
- [ ] 10.2 Refuse buy/sell instruction and guaranteed prediction requests.
- [ ] 10.3 Refuse requests requiring unavailable web, Python, MCP, or code mutation tools.
- [ ] 10.4 Refuse requests to hide trace, bypass tool policy, or fabricate missing data.
- [ ] 10.5 Add safety fixture tests for unsafe prompts.

## 11. Documentation

- [ ] 11.1 Document `vnalpha ask` usage.
- [ ] 11.2 Document supported natural-language intent families.
- [ ] 11.3 Document assistant plan and trace output.
- [ ] 11.4 Document refusal policy and limitations.
- [ ] 11.5 Document how Phase 5.9 depends on Phase 5.8 tool contracts.

## 12. Validation

- [ ] 12.1 Run `cd vnalpha && pytest -q`.
- [ ] 12.2 Run assistant targeted tests.
- [ ] 12.3 Run Phase 5.8 command-layer tests to prove no regression.
- [ ] 12.4 Run Phase 5 E2E fixture tests to prove no regression.
- [ ] 12.5 Manually smoke-test:

```bash
vnalpha ask "Show strongest candidates today" --show-plan --trace
vnalpha ask "Why is FPT in the watchlist?"
vnalpha ask "Compare FPT, VNM, and MWG"
vnalpha ask "Which candidates have weak data quality?"
vnalpha ask "Buy FPT now"
```

The last command must be refused.
