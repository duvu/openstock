# Tasks: Complete Phase 5 Alpha Discovery MVP

## 0. Review Baseline

- [ ] Treat current codebase as partial implementation, not skeleton-only.
- [ ] Confirm `vnalpha` package is the implementation target for Phase 5.
- [ ] Keep `vnstock` data-only and do not move research logic into `vnstock`.

## 1. CLI and Makefile Contract

- [ ] Fix `make sync` command contract.
- [ ] Support `vnalpha sync ohlcv --universe VN30 --start 2024-01-01`, or change Makefile to supported CLI options.
- [ ] Add `--symbols` for explicit comma-separated symbols.
- [ ] Add `--universe` for named universe resolution.
- [ ] Add clear error for unknown universe.
- [ ] Add CLI contract tests for `sync ohlcv` options.
- [ ] Ensure `make sync`, `make features`, `make score`, and `make tui` match documented commands.

## 2. Universe Resolution

- [ ] Implement named universe resolver.
- [ ] Support at least `VN30` for Phase 5.
- [ ] Decide whether `VN30` comes from static config, symbol metadata, or vnstock endpoint.
- [ ] Add tests for `VN30` resolution.
- [ ] Add tests for explicit `--symbols` overriding `--universe`.

## 3. Benchmark Sync and Relative Strength

- [ ] Add explicit benchmark/index sync path.
- [ ] Implement one of:
  - [ ] `vnalpha sync index --symbol VNINDEX --start 2024-01-01`
  - [ ] `vnalpha sync ohlcv --benchmark VNINDEX --start 2024-01-01`
- [ ] Use `VnstockClient.get_index_ohlcv()` for benchmark data.
- [ ] Store benchmark OHLCV in `market_ohlcv_raw` with provider lineage.
- [ ] Promote benchmark data to `canonical_ohlcv`.
- [ ] Ensure `build_features --benchmark VNINDEX` produces non-null relative strength fields when benchmark data exists.
- [ ] Add test for missing benchmark producing a warning/risk flag rather than silent degradation.

## 4. Canonical OHLCV and Data Quality

- [ ] Verify canonical builder deduplicates by `(symbol, time, interval)`.
- [ ] Add validation for invalid OHLCV rows:
  - [ ] missing close
  - [ ] high < low
  - [ ] negative price
  - [ ] negative volume
  - [ ] stale latest bar
- [ ] Persist or derive data-quality status for watchlist review.
- [ ] Insert severe failures into `rejected_symbol`, or add `POOR_DATA_QUALITY` risk flag.
- [ ] Add tests for data-quality pass/warn/fail cases.

## 5. Feature Store Completion

- [ ] Ensure `build_features` handles insufficient history explicitly.
- [ ] Ensure skipped symbols are counted with reason.
- [ ] Add optional rejected rows for insufficient feature history.
- [ ] Confirm feature snapshots include all Phase 5 scoring inputs.
- [ ] Add feature-builder tests using fixture OHLCV and VNINDEX.
- [ ] Assert relative strength is computed when benchmark data exists.

## 6. Scoring and Ontology Enforcement

- [ ] Define explicit canonical candidate class set:
  - [ ] `STRONG_CANDIDATE`
  - [ ] `WATCH_CANDIDATE`
  - [ ] `WEAK_CANDIDATE`
  - [ ] `IGNORE`
- [ ] Define explicit canonical setup type set:
  - [ ] `ACCUMULATION_BASE`
  - [ ] `BREAKOUT_ATTEMPT`
  - [ ] `MOMENTUM_CONTINUATION`
  - [ ] `PULLBACK_TO_TREND`
  - [ ] `MEAN_REVERSION`
  - [ ] `UNCLASSIFIED`
- [ ] Add persistence guard before writing `candidate_score`.
- [ ] Add persistence guard before writing `daily_watchlist`.
- [ ] Update tests so legacy enum aliases are not accepted as persisted Phase 5 values.
- [ ] Align score scale between docs and code: either `0.0-1.0` or `0-100`, not both.

## 7. Watchlist Artifact Completion

- [ ] Add rich watchlist query joining `daily_watchlist` and `candidate_score`.
- [ ] Expose watchlist view fields:
  - [ ] rank
  - [ ] symbol
  - [ ] score
  - [ ] candidate_class
  - [ ] setup_type
  - [ ] evidence_json
  - [ ] risk_flags_json
  - [ ] lineage_json
  - [ ] data_quality_status
- [ ] Update CLI `vnalpha watchlist` to show a useful subset and reference detail view for full evidence.
- [ ] Ensure TUI detail screen shows score breakdown, evidence, risk flags, lineage, and quality status.
- [ ] Add tests for watchlist query output.

## 8. TUI Completion

- [ ] Import and wire `HomeScreen` in `VnAlphaApp`.
- [ ] Import and wire `RejectedScreen` in `VnAlphaApp`.
- [ ] Import and wire `QualityScreen` in `VnAlphaApp`.
- [ ] Fix `action_show_home` so it does not push an unregistered string screen.
- [ ] Fix `action_show_rejected` so it opens the rejected symbols screen.
- [ ] Fix `action_show_quality` so it opens the data quality screen.
- [ ] Confirm Watchlist screen can open Symbol Detail.
- [ ] Add TUI smoke tests for screen construction and navigation actions.

## 9. Fixture-backed Phase 5 E2E Test

- [ ] Create deterministic OHLCV fixture generator.
- [ ] Include benchmark `VNINDEX`.
- [ ] Include one strong candidate.
- [ ] Include one weak/ignored candidate.
- [ ] Include one poor-quality candidate.
- [ ] Run full pipeline in an isolated DuckDB connection:
  - [ ] migrations
  - [ ] symbol load
  - [ ] raw OHLCV load
  - [ ] canonical build
  - [ ] feature build
  - [ ] score
  - [ ] watchlist generation
  - [ ] watchlist query
- [ ] Assert `feature_snapshot` rows exist.
- [ ] Assert `candidate_score` rows exist.
- [ ] Assert `daily_watchlist` rows exist.
- [ ] Assert at least one non-`IGNORE` candidate exists.
- [ ] Assert poor-quality candidate is flagged or rejected.
- [ ] Ensure E2E test does not require network access.

## 10. Research-only Safety Guard

- [ ] Add static scan for execution-oriented public language in CLI/TUI labels and docs.
- [ ] Confirm no Phase 5 command places orders.
- [ ] Confirm no Phase 5 command connects to broker account/order/portfolio APIs.
- [ ] Confirm output language uses candidate/watchlist/research terminology.

## 11. Runbook and Documentation

- [ ] Update Phase 5 runbook with exact working commands.
- [ ] Document fixture-mode E2E test.
- [ ] Document service-backed local smoke test.
- [ ] Document VN30 universe behavior.
- [ ] Document benchmark/VNINDEX behavior.
- [ ] Document score scale and thresholds.
- [ ] Document candidate class and setup type ontology.
- [ ] Document known limitations and deferred Phase 5.8+ work.

## 12. Final Validation

- [ ] `make install-vnalpha` passes.
- [ ] `make lint-vnalpha` passes.
- [ ] `make test-vnalpha` passes.
- [ ] `make sync` either passes locally or has a CI-safe fixture equivalent.
- [ ] `make features` creates feature snapshots.
- [ ] `make score` creates candidate scores and daily watchlist.
- [ ] `make tui` launches TUI.
- [ ] Manual smoke test confirms watchlist/detail/rejected/quality screens work.
- [ ] OpenSpec Phase 5 task status is updated only after validation.
