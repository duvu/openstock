# Tasks: Complete Phase 5 Alpha Discovery MVP

## 0. Review Baseline

- [x] Treat current codebase as partial implementation, not skeleton-only.
- [x] Confirm `vnalpha` package is the implementation target for Phase 5.
- [x] Keep `vnstock` data-only and do not move research logic into `vnstock`.

## 1. CLI and Makefile Contract

- [x] Fix `make sync` command contract.
- [x] Support `vnalpha sync ohlcv --universe VN30 --start 2024-01-01`, or change Makefile to supported CLI options.
- [x] Add `--symbols` for explicit comma-separated symbols.
- [x] Add `--universe` for named universe resolution.
- [x] Add clear error for unknown universe.
- [x] Add CLI contract tests for `sync ohlcv` options.
- [x] Ensure `make sync`, `make features`, `make score`, and `make tui` match documented commands.

## 2. Universe Resolution

- [x] Implement named universe resolver.
- [x] Support at least `VN30` for Phase 5.
- [x] Decide whether `VN30` comes from static config, symbol metadata, or vnstock endpoint.
- [x] Add tests for `VN30` resolution.
- [x] Add tests for explicit `--symbols` overriding `--universe`.

## 3. Benchmark Sync and Relative Strength

- [x] Add explicit benchmark/index sync path.
- [x] Implement one of:
  - [x] `vnalpha sync index --symbol VNINDEX --start 2024-01-01`
  - [x] `vnalpha sync ohlcv --benchmark VNINDEX --start 2024-01-01`
- [x] Use `VnstockClient.get_index_ohlcv()` for benchmark data.
- [x] Store benchmark OHLCV in `market_ohlcv_raw` with provider lineage.
- [x] Promote benchmark data to `canonical_ohlcv`.
- [x] Ensure `build_features --benchmark VNINDEX` produces non-null relative strength fields when benchmark data exists.
- [x] Add test for missing benchmark producing a warning/risk flag rather than silent degradation.

## 4. Canonical OHLCV and Data Quality

- [x] Verify canonical builder deduplicates by `(symbol, time, interval)`.
- [x] Add validation for invalid OHLCV rows:
  - [x] missing close
  - [x] high < low
  - [x] negative price
  - [x] negative volume
  - [x] stale latest bar
- [x] Persist or derive data-quality status for watchlist review.
- [x] Insert severe failures into `rejected_symbol`, or add `POOR_DATA_QUALITY` risk flag.
- [x] Add tests for data-quality pass/warn/fail cases.

## 5. Feature Store Completion

- [x] Ensure `build_features` handles insufficient history explicitly.
- [x] Ensure skipped symbols are counted with reason.
- [x] Add optional rejected rows for insufficient feature history.
- [x] Confirm feature snapshots include all Phase 5 scoring inputs.
- [x] Add feature-builder tests using fixture OHLCV and VNINDEX.
- [x] Assert relative strength is computed when benchmark data exists.

## 6. Scoring and Ontology Enforcement

- [x] Define explicit canonical candidate class set:
  - [x] `STRONG_CANDIDATE`
  - [x] `WATCH_CANDIDATE`
  - [x] `WEAK_CANDIDATE`
  - [x] `IGNORE`
- [x] Define explicit canonical setup type set:
  - [x] `ACCUMULATION_BASE`
  - [x] `BREAKOUT_ATTEMPT`
  - [x] `MOMENTUM_CONTINUATION`
  - [x] `PULLBACK_TO_TREND`
  - [x] `MEAN_REVERSION`
  - [x] `UNCLASSIFIED`
- [x] Add persistence guard before writing `candidate_score`.
- [x] Add persistence guard before writing `daily_watchlist`.
- [x] Update tests so legacy enum aliases are not accepted as persisted Phase 5 values.
- [x] Align score scale between docs and code: either `0.0-1.0` or `0-100`, not both.

## 7. Watchlist Artifact Completion

- [x] Add rich watchlist query joining `daily_watchlist` and `candidate_score`.
- [x] Expose watchlist view fields:
  - [x] rank
  - [x] symbol
  - [x] score
  - [x] candidate_class
  - [x] setup_type
  - [x] evidence_json
  - [x] risk_flags_json
  - [x] lineage_json
  - [x] data_quality_status
- [x] Update CLI `vnalpha watchlist` to show a useful subset and reference detail view for full evidence.
- [x] Ensure TUI detail screen shows score breakdown, evidence, risk flags, lineage, and quality status.
- [x] Add tests for watchlist query output.

## 8. TUI Completion

- [x] Import and wire `HomeScreen` in `VnAlphaApp`.
- [x] Import and wire `RejectedScreen` in `VnAlphaApp`.
- [x] Import and wire `QualityScreen` in `VnAlphaApp`.
- [x] Fix `action_show_home` so it does not push an unregistered string screen.
- [x] Fix `action_show_rejected` so it opens the rejected symbols screen.
- [x] Fix `action_show_quality` so it opens the data quality screen.
- [x] Confirm Watchlist screen can open Symbol Detail.
- [x] Add TUI smoke tests for screen construction and navigation actions.

## 9. Fixture-backed Phase 5 E2E Test

- [x] Create deterministic OHLCV fixture generator.
- [x] Include benchmark `VNINDEX`.
- [x] Include one strong candidate.
- [x] Include one weak/ignored candidate.
- [x] Include one poor-quality candidate.
- [x] Run full pipeline in an isolated DuckDB connection:
  - [x] migrations
  - [x] symbol load
  - [x] raw OHLCV load
  - [x] canonical build
  - [x] feature build
  - [x] score
  - [x] watchlist generation
  - [x] watchlist query
- [x] Assert `feature_snapshot` rows exist.
- [x] Assert `candidate_score` rows exist.
- [x] Assert `daily_watchlist` rows exist.
- [x] Assert at least one non-`IGNORE` candidate exists.
- [x] Assert poor-quality candidate is flagged or rejected.
- [x] Ensure E2E test does not require network access.

## 10. Research-only Safety Guard

- [x] Add static scan for execution-oriented public language in CLI/TUI labels and docs.
- [x] Confirm no Phase 5 command places orders.
- [x] Confirm no Phase 5 command connects to broker account/order/portfolio APIs.
- [x] Confirm output language uses candidate/watchlist/research terminology.

## 11. Runbook and Documentation

- [x] Update Phase 5 runbook with exact working commands.
- [x] Document fixture-mode E2E test.
- [x] Document service-backed local smoke test.
- [x] Document VN30 universe behavior.
- [x] Document benchmark/VNINDEX behavior.
- [x] Document score scale and thresholds.
- [x] Document candidate class and setup type ontology.
- [x] Document known limitations and deferred Phase 5.8+ work.

## 12. Final Validation

- [x] `make install-vnalpha` passes.
- [x] `make lint-vnalpha` passes.
- [x] `make test-vnalpha` passes.
- [x] `make sync` either passes locally or has a CI-safe fixture equivalent.
- [x] `make features` creates feature snapshots.
- [x] `make score` creates candidate scores and daily watchlist.
- [x] `make tui` launches TUI.
- [x] Manual smoke test confirms watchlist/detail/rejected/quality screens work.
- [x] OpenSpec Phase 5 task status is updated only after validation.
