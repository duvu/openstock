# Tasks: Close Phase 5 Alpha Discovery TUI MVP

## 0. Closure Rule

- [ ] Do not mark Phase 5 closed until the end-to-end workflow is executable and test-backed.
- [ ] Reconcile existing checked tasks from `phase-5-alpha-discovery-tui-mvp` with actual implementation status.
- [ ] Uncheck or annotate tasks that are not backed by tests, commands, or working code paths.

## 1. Repo Boundary

- [ ] Decide whether `vnalpha` implementation lives in `duvu/vnalpha` or is vendored under `openstock/vnalpha`.
- [ ] If separate repo, move/commit implementation to `duvu/vnalpha` and keep `openstock` as orchestration/source-of-truth.
- [ ] If vendored, update roadmap/runbook/Makefile docs to state that `openstock/vnalpha` is the implementation location.
- [ ] Ensure future Phase 5 implementation PRs target the correct repository.

## 2. Wire CLI Commands

- [ ] Replace placeholder behavior in `vnalpha build features` with a real feature builder.
- [ ] Replace placeholder behavior in `vnalpha score` with real scoring and watchlist generation.
- [ ] Replace placeholder behavior in `vnalpha watchlist` with a DuckDB query and Rich table renderer.
- [ ] Replace placeholder behavior in `vnalpha tui` with `VnAlphaApp().run()`.
- [ ] Ensure unsupported states return explicit user-facing messages instead of silent success.
- [ ] Add regression tests proving Phase 5 CLI commands are not stubs.

## 3. Warehouse and Canonical Data

- [ ] Verify `vnalpha init` creates the expected DuckDB schema.
- [ ] Verify `symbol_master` is populated by `vnalpha sync symbols`.
- [ ] Verify `market_ohlcv_raw` is populated by `vnalpha sync ohlcv` or fixture mode.
- [ ] Implement or verify `vnalpha build canonical`.
- [ ] Enforce one canonical OHLCV row per symbol/date.
- [ ] Add quality flags for missing, duplicate, stale, or invalid OHLCV rows.

## 4. Feature Store v1

- [ ] Build `feature_snapshot` from `canonical_ohlcv`.
- [ ] Include trend features.
- [ ] Include relative strength features.
- [ ] Include volume/liquidity features.
- [ ] Include base/range features.
- [ ] Include breakout/proximity features.
- [ ] Include data-quality and provider-lineage fields.
- [ ] Add unit tests for feature calculations.

## 5. Scoring and Watchlist

- [ ] Generate component scores from latest feature snapshots.
- [ ] Generate composite score.
- [ ] Map final score to canonical `candidate_class`.
- [ ] Map observed pattern to canonical `setup_type`.
- [ ] Write `candidate_score` rows.
- [ ] Generate ranked `daily_watchlist` rows.
- [ ] Add evidence summary, score breakdown, risk flags, provider lineage, and data quality status.
- [ ] Add tests for score mapping and watchlist generation.

## 6. Ontology Alignment

- [ ] Standardize `candidate_class` values:
  - [ ] `STRONG_CANDIDATE`
  - [ ] `WATCH_CANDIDATE`
  - [ ] `WEAK_CANDIDATE`
  - [ ] `IGNORE`
- [ ] Standardize `setup_type` values:
  - [ ] `ACCUMULATION_BASE`
  - [ ] `BREAKOUT_ATTEMPT`
  - [ ] `MOMENTUM_CONTINUATION`
  - [ ] `PULLBACK_TO_TREND`
  - [ ] `MEAN_REVERSION`
  - [ ] `UNCLASSIFIED`
- [ ] Remove or map old labels such as `STAGE1`, `STAGE2`, `BREAKOUT`, `MOMENTUM`, and `MEAN_REVERT` so they are not used as `candidate_class`.

## 7. CLI/TUI Review Surface

- [ ] Render latest watchlist as a Rich table from `daily_watchlist`.
- [ ] Support date selection or clearly document latest-only behavior.
- [ ] Launch Textual app from `vnalpha tui`.
- [ ] Wire Watchlist screen to DuckDB query service.
- [ ] Wire Symbol Detail screen to candidate detail query service.
- [ ] Display score breakdown, evidence, risk flags, lineage, and data quality in detail view.
- [ ] Add Rejected Symbols screen or explicit placeholder.
- [ ] Add Data Quality screen or explicit placeholder.
- [ ] Add empty-state behavior when no warehouse or no watchlist exists.
- [ ] Add TUI construction/smoke test.

## 8. End-to-End Tests

- [ ] Create fixture OHLCV dataset for at least 3 symbols.
- [ ] Use isolated temporary DuckDB database in tests.
- [ ] Test full pipeline:
  - [ ] init
  - [ ] load fixture symbols
  - [ ] load fixture OHLCV
  - [ ] build canonical
  - [ ] build features
  - [ ] score
  - [ ] generate watchlist
  - [ ] query watchlist
- [ ] Assert expected tables are populated.
- [ ] Assert at least one non-`IGNORE` candidate is generated.
- [ ] Assert severe data-quality issue creates a risk flag or rejection.
- [ ] Add regression guard that CLI commands are not stubs.

## 9. Safety and Public Language Guard

- [ ] Scan CLI help text, TUI labels, docs, prompts, and tests for execution-oriented product language.
- [ ] Ensure product copy uses research/watchlist/candidate language.
- [ ] Ensure Phase 5 exposes no brokerage execution command path.
- [ ] Add a static check for prohibited public-facing terms where practical.

## 10. Documentation and Runbook

- [ ] Update Phase 5 runbook with exact local commands.
- [ ] Document expected `.env` variables.
- [ ] Document how to run with fixture data.
- [ ] Document how to run with local `vnstock-service`.
- [ ] Document candidate class and setup type ontology.
- [ ] Document known limitations of Phase 5.
- [ ] Document Phase 5.8/5.9 as deferred MCP/LLM work if needed.

## 11. Final Closure Verification

- [ ] `make install-vnalpha` passes.
- [ ] `make lint-vnalpha` passes.
- [ ] `make test-vnalpha` passes.
- [ ] `make up-vnstock` starts local service.
- [ ] `make sync` completes, or fixture mode completes in CI.
- [ ] `make features` creates feature snapshots.
- [ ] `make score` creates candidate scores and daily watchlist.
- [ ] `make tui` launches TUI.
- [ ] Manual smoke test confirms watchlist and detail screens show real data.
- [ ] OpenSpec task list is updated to reflect verified completion.
- [ ] Phase 5 is marked closed only after all required checks pass.
