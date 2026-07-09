# Tasks: Assistant Research Intelligence Tools

## 0. Governance

- [ ] 0.1 Keep assistant outputs research-only.
- [ ] 0.2 Do not add broker/order/account/portfolio/margin/trading execution tools.
- [ ] 0.3 Do not allow raw SQL, filesystem, or unrestricted code execution from assistant tools.
- [ ] 0.4 Require policy and groundedness checks for scenario and shortlist answers.

## 1. Intent taxonomy

- [ ] 1.1 Add `deep_analyze_symbol`.
- [ ] 1.2 Add `review_market_regime`.
- [ ] 1.3 Add `review_sector_strength`.
- [ ] 1.4 Add `summarize_watchlist_deep`.
- [ ] 1.5 Add `generate_shortlist`.
- [ ] 1.6 Add `generate_research_scenario`.
- [ ] 1.7 Add `review_setup_evidence`.

## 2. Tool contracts

- [ ] 2.1 Add `analysis.deep_symbol`.
- [ ] 2.2 Add `market.get_regime`.
- [ ] 2.3 Add `sector.get_strength`.
- [ ] 2.4 Add `watchlist.summarize_deep`.
- [ ] 2.5 Add `shortlist.generate`.
- [ ] 2.6 Add `scenario.generate_research_plan`.
- [ ] 2.7 Add `evidence.get_setup_history`.

## 3. Planning and execution

- [ ] 3.1 Add deterministic plan builders.
- [ ] 3.2 Use one central assistant tool policy.
- [ ] 3.3 Add execution-mode tests.
- [ ] 3.4 Ensure tools return structured payloads.

## 4. Synthesis and audit

- [ ] 4.1 Add templates per intent.
- [ ] 4.2 Add groundedness validator.
- [ ] 4.3 Add research answer audit writer.
- [ ] 4.4 Require missing-data disclosure.
- [ ] 4.5 Require caveats.

## 5. Tests

- [ ] 5.1 Test every new intent classification.
- [ ] 5.2 Test every plan builder.
- [ ] 5.3 Test tool allowlist denies unsafe tools.
- [ ] 5.4 Test scenario/shortlist policy wording.
- [ ] 5.5 Test answer audit persistence.

## 6. Validation

- [ ] 6.1 Run standard validation commands and attach evidence.
