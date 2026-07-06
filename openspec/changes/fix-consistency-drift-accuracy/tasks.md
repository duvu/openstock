# Tasks: Fix Consistency, Data Drift, and Accuracy

## 1. Feature snapshot date semantics

- [ ] 1.1 Add `as_of_bar_date` to `feature_snapshot`.
- [ ] 1.2 Add `benchmark_as_of_bar_date` to `feature_snapshot`.
- [ ] 1.3 Add `source_row_count` and `benchmark_row_count` to `feature_snapshot`.
- [ ] 1.4 Add `feature_data_status` to `feature_snapshot`.
- [ ] 1.5 Add `feature_build_version` and `feature_generated_at`.
- [ ] 1.6 Update `build_features()` to persist actual source bar dates.
- [ ] 1.7 Mark stale feature rows as `STALE_DATE` when actual bar date is before target date.
- [ ] 1.8 Add tests for exact-date, stale-date, missing benchmark, and insufficient history cases.

## 2. Lineage propagation

- [ ] 2.1 Add source lineage fields to `feature_snapshot` or `feature_snapshot.lineage_json`.
- [ ] 2.2 Populate provider, ingestion run, source quality, and as-of bar date from canonical OHLCV.
- [ ] 2.3 Update `score_universe()` to read feature lineage fields.
- [ ] 2.4 Update `save_candidate_score()` to persist lineage with explicit `lineage_status`.
- [ ] 2.5 Add warnings/tests when provider or ingestion run is missing.
- [ ] 2.6 Ensure `daily_watchlist.lineage_json` carries complete candidate score lineage.

## 3. Historical quality lookup

- [ ] 3.1 Add shared quality service for as-of quality lookup.
- [ ] 3.2 Update `get_watchlist_rich()` to use quality rows where `canonical_ohlcv.time <= daily_watchlist.date`.
- [ ] 3.3 Update `quality.get_status(symbol, date)` to honor date.
- [ ] 3.4 Add `quality.get_many_status(symbols, date)`.
- [ ] 3.5 Attach rejected records to symbol quality outputs when available.
- [ ] 3.6 Add tests proving future quality rows are not used for historical review.

## 4. Rejected-symbol semantics

- [ ] 4.1 Add `bar_date` and `detected_at` to `rejected_symbol`, or document/migrate `date` as bar date.
- [ ] 4.2 Add provider and ingestion_run_id to rejected rows when available.
- [ ] 4.3 Update canonical validation to write the affected data/bar date, not only job run date.
- [ ] 4.4 Add tests for invalid OHLCV rejection date semantics.

## 5. Shared filter validation

- [ ] 5.1 Create shared filter validation module.
- [ ] 5.2 Move supported field allowlist to shared module.
- [ ] 5.3 Validate filters in `watchlist.filter` tool, not only in `/filter` handler.
- [ ] 5.4 Update `/filter` handler to call shared validator.
- [ ] 5.5 Update assistant filter plan execution to use the same validation path.
- [ ] 5.6 Add tests for unsupported fields, malformed numeric comparisons, aliases, and risk flag contains/not_contains filters.

## 6. Assistant compare-quality consistency

- [ ] 6.1 Add `quality.get_many_status` to LocalToolRegistry and assistant allowlist, or implement executor expansion into per-symbol quality calls.
- [ ] 6.2 Update compare plan to call the correct quality tool.
- [ ] 6.3 Ensure compare answer includes quality for each compared symbol.
- [ ] 6.4 Add tests for compare workflows with 2+ symbols.

## 7. Tool trace parent semantics

- [ ] 7.1 Update assistant tool executor to set `session_id = NULL` for assistant traces.
- [ ] 7.2 Keep `assistant_session_id` populated for assistant traces.
- [ ] 7.3 Keep `session_id` populated and `assistant_session_id = NULL` for command traces.
- [ ] 7.4 Add repository validation or tests for ambiguous parent rows.
- [ ] 7.5 Add migration safety for existing ambiguous rows if needed.

## 8. Remove production direct-tool fallback

- [ ] 8.1 Remove direct tool-call fallback from production command handlers.
- [ ] 8.2 Make missing `tool_executor` a failed command result or explicit test-only path.
- [ ] 8.3 Add tests that CLI/TUI commands always create tool_trace.
- [ ] 8.4 Add source test or architecture test that command handlers do not import tool implementations directly for production execution.

## 9. Outcome evaluation versioning

- [ ] 9.1 Add `outcome_evaluation_run` table.
- [ ] 9.2 Add `evaluation_run_id` to candidate and aggregate outcome tables.
- [ ] 9.3 Add `evaluator_version` and `metric_policy_version` to candidate outcome.
- [ ] 9.4 Add symbol/benchmark data snapshot metadata.
- [ ] 9.5 Update `evaluate_watchlist_date()` and range evaluation to create and finish an evaluation run.
- [ ] 9.6 Add tests that recomputation creates a traceable evaluation run.

## 10. Outcome metric policy

- [ ] 10.1 Define `CLOSE_ONLY_V1` and `OHLC_HIGH_LOW_V1` metric policies.
- [ ] 10.2 Update OHLCV loading to include high and low when policy requires it.
- [ ] 10.3 Use high for max gain and low for max drawdown under `OHLC_HIGH_LOW_V1`.
- [ ] 10.4 Keep close-only metrics explicitly labeled when used.
- [ ] 10.5 Persist metric policy on outcome records.
- [ ] 10.6 Add unit tests for both metric policies.

## 11. Trading-calendar date resolver

- [ ] 11.1 Add Vietnam trading-calendar-aware date resolver.
- [ ] 11.2 Use Asia/Ho_Chi_Minh timezone for `today`.
- [ ] 11.3 Resolve no-data/weekend dates to latest available research date where appropriate.
- [ ] 11.4 Preserve explicit ISO date override behavior.
- [ ] 11.5 Update CLI, TUI, command executor, assistant, and outcome paths to use the shared resolver.
- [ ] 11.6 Add tests for weekday, weekend, no-data, and explicit-date cases.

## 12. Regression and safety tests

- [ ] 12.1 Add drift tests for historical watchlist quality.
- [ ] 12.2 Add lineage tests for candidate score and daily watchlist.
- [ ] 12.3 Add assistant compare quality tests.
- [ ] 12.4 Add filter validation tests across CLI and assistant paths.
- [ ] 12.5 Add outcome versioning tests.
- [ ] 12.6 Run Phase 5 E2E fixture tests.
- [ ] 12.7 Run Phase 5.8 command tests.
- [ ] 12.8 Run Phase 5.9 assistant tests.
- [ ] 12.9 Run Phase 6 outcome tests.
- [ ] 12.10 Run `cd vnalpha && pytest -q`.
