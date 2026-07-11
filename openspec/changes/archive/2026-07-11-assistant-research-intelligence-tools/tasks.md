# Tasks: Assistant Research Intelligence Tools

## 0. Governance

- [x] 0.1 Keep assistant outputs research-only.
- [x] 0.2 Do not add broker/order/account/portfolio/margin/trading execution tools.
- [x] 0.3 Do not allow raw SQL, filesystem, or unrestricted code execution from assistant tools.
- [x] 0.4 Require policy and groundedness checks for scenario and shortlist answers.

## 1. Intent taxonomy

- [x] 1.1 Add `deep_analyze_symbol`.
- [x] 1.2 Add `review_market_regime`.
- [x] 1.3 Add `review_sector_strength`.
- [x] 1.4 Add `summarize_watchlist_deep`.
- [x] 1.5 Add `generate_shortlist`.
- [x] 1.6 Add `generate_research_scenario`.
- [x] 1.7 Add `review_setup_evidence`.

## 2. Tool contracts

- [x] 2.1 Add `analysis.deep_symbol`.
- [x] 2.2 Add `market.get_regime`.
- [x] 2.3 Add `sector.get_strength`.
- [x] 2.4 Add `watchlist.summarize_deep`.
- [x] 2.5 Add `shortlist.generate`.
- [x] 2.6 Add `scenario.generate_research_plan`.
- [x] 2.7 Add `evidence.get_setup_history`.

## 3. Planning and execution

- [x] 3.1 Add deterministic plan builders.
- [x] 3.2 Use one central assistant tool policy.
- [x] 3.3 Add execution-mode tests.
- [x] 3.4 Ensure tools return structured payloads.

## 4. Synthesis and audit

- [x] 4.1 Add templates per intent and inject them into synthesis context.
- [x] 4.2 Add pre- and post-synthesis groundedness validation.
- [x] 4.3 Add research answer audit schema, writer, runtime integration, and lookup.
- [x] 4.4 Require missing-data disclosure.
- [x] 4.5 Require caveats and research-language policy validation.
- [x] 4.6 Add deterministic fail-closed fallback for ungrounded or policy-invalid model output.
- [x] 4.7 Persist groundedness, policy, freshness, tools, artifacts, caveats, and correlation ID.

## 5. Tests

- [x] 5.1 Test every new intent classification.
- [x] 5.2 Test every plan builder.
- [x] 5.3 Test tool allowlist denies unsafe tools.
- [x] 5.4 Test scenario/shortlist policy wording and deterministic rewrite.
- [x] 5.5 Test answer audit migration and persistence through `AssistantApp`.
- [x] 5.6 Test template/source-reference injection and unsupported claim rewrite.
- [x] 5.7 Test missing tool output fails before the model call.

## 6. Documentation and validation

- [x] 6.1 Add implementation review and operator documentation.
- [ ] 6.2 Run focused assistant-research-intelligence tests.
- [ ] 6.3 Run `make test-vnalpha`.
- [ ] 6.4 Run `make lint-vnalpha`.
- [ ] 6.5 Run `make verify-r4`.
- [ ] 6.6 Run `packaging/scripts/openstock-verify --ci`.

Validation tasks remain unchecked until command output is attached in `validation.md`.
