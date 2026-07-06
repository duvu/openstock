# Tasks: Close Phase 5 Alpha Discovery TUI MVP

## 0. Closure Rule

- [x] Do not mark Phase 5 closed until the end-to-end workflow is executable and test-backed.
- [x] Reconcile existing checked tasks from `phase-5-alpha-discovery-tui-mvp` with actual implementation status.
- [x] Uncheck or annotate tasks that are not backed by tests, commands, or working code paths.

## 1. Repo Boundary

- [x] Decide whether `vnalpha` implementation lives in `duvu/vnalpha` or is vendored under `openstock/vnalpha`.
- [x] If separate repo, move/commit implementation to `duvu/vnalpha` and keep `openstock` as orchestration/source-of-truth.
- [x] If vendored, update roadmap/runbook/Makefile docs to state that `openstock/vnalpha` is the implementation location.
- [x] Ensure future Phase 5 implementation PRs target the correct repository.

## 2. Wire CLI Commands

- [x] Replace placeholder behavior in `vnalpha build features` with a real feature builder.
- [x] Replace placeholder behavior in `vnalpha score` with real scoring and watchlist generation.
- [x] Replace placeholder behavior in `vnalpha watchlist` with a DuckDB query and Rich table renderer.
- [x] Replace placeholder behavior in `vnalpha tui` with `VnAlphaApp().run()`.
- [x] Ensure unsupported states return explicit user-facing messages instead of silent success.
- [x] Add regression tests proving Phase 5 CLI commands are not stubs.

## 3. Warehouse and Canonical Data

- [x] Verify `vnalpha init` creates the expected DuckDB schema.
- [x] Verify `symbol_master` is populated by `vnalpha sync symbols`.
- [x] Verify `market_ohlcv_raw` is populated by `vnalpha sync ohlcv` or fixture mode.
- [x] Implement or verify `vnalpha build canonical`.
- [x] Enforce one canonical OHLCV row per symbol/date.
- [x] Add quality flags for missing, duplicate, stale, or invalid OHLCV rows.

## 4. Feature Store v1

- [x] Build `feature_snapshot` from `canonical_ohlcv`.
- [x] Include trend features.
- [x] Include relative strength features.
- [x] Include volume/liquidity features.
- [x] Include base/range features.
- [x] Include breakout/proximity features.
- [x] Include data-quality and provider-lineage fields.
- [x] Add unit tests for feature calculations.

## 5. Scoring and Watchlist

- [x] Generate component scores from latest feature snapshots.
- [x] Generate composite score.
- [x] Map final score to canonical `candidate_class`.
- [x] Map observed pattern to canonical `setup_type`.
- [x] Write `candidate_score` rows.
- [x] Generate ranked `daily_watchlist` rows.
- [x] Add evidence summary, score breakdown, risk flags, provider lineage, and data quality status.
- [x] Add tests for score mapping and watchlist generation.

## 6. Ontology Alignment

- [x] Standardize `candidate_class` values:
  - [x] `STRONG_CANDIDATE`
  - [x] `WATCH_CANDIDATE`
  - [x] `WEAK_CANDIDATE`
  - [x] `IGNORE`
- [x] Standardize `setup_type` values:
  - [x] `ACCUMULATION_BASE`
  - [x] `BREAKOUT_ATTEMPT`
  - [x] `MOMENTUM_CONTINUATION`
  - [x] `PULLBACK_TO_TREND`
  - [x] `MEAN_REVERSION`
  - [x] `UNCLASSIFIED`
- [x] Remove or map old labels such as `STAGE1`, `STAGE2`, `BREAKOUT`, `MOMENTUM`, and `MEAN_REVERT` so they are not used as `candidate_class`.

## 7. CLI/TUI Review Surface

- [x] Render latest watchlist as a Rich table from `daily_watchlist`.
- [x] Support date selection or clearly document latest-only behavior.
- [x] Launch Textual app from `vnalpha tui`.
- [x] Wire Watchlist screen to DuckDB query service.
- [x] Wire Symbol Detail screen to candidate detail query service.
- [x] Display score breakdown, evidence, risk flags, lineage, and data quality in detail view.
- [x] Add Rejected Symbols screen or explicit placeholder.
- [x] Add Data Quality screen or explicit placeholder.
- [x] Add empty-state behavior when no warehouse or no watchlist exists.
- [x] Add TUI construction/smoke test.

## 8. End-to-End Tests

- [x] Create fixture OHLCV dataset for at least 3 symbols.
- [x] Use isolated temporary DuckDB database in tests.
- [x] Test full pipeline:
  - [x] init
  - [x] load fixture symbols
  - [x] load fixture OHLCV
  - [x] build canonical
  - [x] build features
  - [x] score
  - [x] generate watchlist
  - [x] query watchlist
- [x] Assert expected tables are populated.
- [x] Assert at least one non-`IGNORE` candidate is generated.
- [x] Assert severe data-quality issue creates a risk flag or rejection.
- [x] Add regression guard that CLI commands are not stubs.

## 9. Safety and Public Language Guard

- [x] Scan CLI help text, TUI labels, docs, prompts, and tests for execution-oriented product language.
- [x] Ensure product copy uses research/watchlist/candidate language.
- [x] Ensure Phase 5 exposes no brokerage execution command path.
- [x] Add a static check for prohibited public-facing terms where practical.

## 10. Documentation and Runbook

- [x] Update Phase 5 runbook with exact local commands.
- [x] Document expected `.env` variables.
- [x] Document how to run with fixture data.
- [x] Document how to run with local `vnstock-service`.
- [x] Document candidate class and setup type ontology.
- [x] Document known limitations of Phase 5.
- [x] Document Phase 5.8/5.9 as deferred MCP/LLM work if needed.

## 11. Final Closure Verification

- [x] `make install-vnalpha` passes.
- [x] `make lint-vnalpha` passes.
- [x] `make test-vnalpha` passes.
- [x] `make up-vnstock` starts local service.
- [x] `make sync` completes, or fixture mode completes in CI.
- [x] `make features` creates feature snapshots.
- [x] `make score` creates candidate scores and daily watchlist.
- [x] `make tui` launches TUI.
- [x] Manual smoke test confirms watchlist and detail screens show real data.
- [x] OpenSpec task list is updated to reflect verified completion.
- [x] Phase 5 is marked closed only after all required checks pass.
