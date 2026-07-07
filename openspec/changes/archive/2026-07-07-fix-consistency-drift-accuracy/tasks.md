# Tasks: Fix Consistency, Data Drift, and Accuracy

## 1. Feature snapshot date semantics

- [x] 1.1 Add `as_of_bar_date` to `feature_snapshot`.
- [x] 1.2 Add `benchmark_as_of_bar_date` to `feature_snapshot`.
- [x] 1.3 Add `source_row_count` and `benchmark_row_count` to `feature_snapshot`.
- [x] 1.4 Add `feature_data_status` to `feature_snapshot`.
- [x] 1.5 Add `feature_build_version` and `feature_generated_at`.
- [x] 1.6 Update `build_features()` to persist actual source bar dates.
- [x] 1.7 Mark stale feature rows as `STALE_DATE` when actual bar date is before target date.
- [x] 1.8 Add tests for exact-date, stale-date, missing benchmark, and insufficient history cases.

## 2. Lineage propagation

- [x] 2.1 Add source lineage fields to `feature_snapshot` or `feature_snapshot.lineage_json`.
- [x] 2.2 Populate provider, ingestion run, source quality, and as-of bar date from canonical OHLCV.
- [x] 2.3 Update `score_universe()` to read feature lineage fields.
- [x] 2.4 Update `save_candidate_score()` to persist lineage with explicit `lineage_status`.
- [x] 2.5 Add warnings/tests when provider or ingestion run is missing.
- [x] 2.6 Ensure `daily_watchlist.lineage_json` carries complete candidate score lineage.

## 3. Historical quality lookup

- [x] 3.1 Add shared quality service for as-of quality lookup.
- [x] 3.2 Update `get_watchlist_rich()` to use quality rows where `canonical_ohlcv.time <= daily_watchlist.date`.
- [x] 3.3 Update `quality.get_status(symbol, date)` to honor date.
- [x] 3.4 Add `quality.get_many_status(symbols, date)`.
- [x] 3.5 Attach rejected records to symbol quality outputs when available.
- [x] 3.6 Add tests proving future quality rows are not used for historical review.

## 4. Rejected-symbol semantics

- [x] 4.1 Add `bar_date` and `detected_at` to `rejected_symbol`, or document/migrate `date` as bar date.
- [x] 4.2 Add provider and ingestion_run_id to rejected rows when available.
- [x] 4.3 Update canonical validation to write the affected data/bar date, not only job run date.
- [x] 4.4 Add tests for invalid OHLCV rejection date semantics.

## 5. Shared filter validation

- [x] 5.1 Create shared filter validation module.
- [x] 5.2 Move supported field allowlist to shared module.
- [x] 5.3 Validate filters in `watchlist.filter` tool, not only in `/filter` handler.
- [x] 5.4 Update `/filter` handler to call shared validator.
- [x] 5.5 Update assistant filter plan execution to use the same validation path.
- [x] 5.6 Add tests for unsupported fields, malformed numeric comparisons, aliases, and risk flag contains/not_contains filters.

## 6. Assistant compare-quality consistency

- [x] 6.1 Add `quality.get_many_status` to LocalToolRegistry and assistant allowlist, or implement executor expansion into per-symbol quality calls.
- [x] 6.2 Update compare plan to call the correct quality tool.
- [x] 6.3 Ensure compare answer includes quality for each compared symbol.
- [x] 6.4 Add tests for compare workflows with 2+ symbols.

## 7. Tool trace parent semantics

- [x] 7.1 Update assistant tool executor to set `session_id = NULL` for assistant traces.
- [x] 7.2 Keep `assistant_session_id` populated for assistant traces.
- [x] 7.3 Keep `session_id` populated and `assistant_session_id = NULL` for command traces.
- [x] 7.4 Add repository validation or tests for ambiguous parent rows.
- [x] 7.5 Add migration safety for existing ambiguous rows if needed.

## 8. Remove production direct-tool fallback

- [x] 8.1 Remove direct tool-call fallback from production command handlers.
- [x] 8.2 Make missing `tool_executor` a failed command result or explicit test-only path.
- [x] 8.3 Add tests that CLI/TUI commands always create tool_trace.
- [x] 8.4 Add source test or architecture test that command handlers do not import tool implementations directly for production execution.

## 9. Outcome evaluation versioning

- [x] 9.1 Add `outcome_evaluation_run` table.
- [x] 9.2 Add `evaluation_run_id` to candidate and aggregate outcome tables.
- [x] 9.3 Add `evaluator_version` and `metric_policy_version` to candidate outcome.
- [x] 9.4 Add symbol/benchmark data snapshot metadata.
- [x] 9.5 Update `evaluate_watchlist_date()` and range evaluation to create and finish an evaluation run.
- [x] 9.6 Add tests that recomputation creates a traceable evaluation run.

## 10. Outcome metric policy

- [x] 10.1 Define `CLOSE_ONLY_V1` and `OHLC_HIGH_LOW_V1` metric policies.
- [x] 10.2 Update OHLCV loading to include high and low when policy requires it.
- [x] 10.3 Use high for max gain and low for max drawdown under `OHLC_HIGH_LOW_V1`.
- [x] 10.4 Keep close-only metrics explicitly labeled when used.
- [x] 10.5 Persist metric policy on outcome records.
- [x] 10.6 Add unit tests for both metric policies.

## 11. Trading-calendar date resolver

- [x] 11.1 Add Vietnam trading-calendar-aware date resolver.
- [x] 11.2 Use Asia/Ho_Chi_Minh timezone for `today`.
- [x] 11.3 Resolve no-data/weekend dates to latest available research date where appropriate.
- [x] 11.4 Preserve explicit ISO date override behavior.
- [x] 11.5 Update CLI, TUI, command executor, assistant, and outcome paths to use the shared resolver.
- [x] 11.6 Add tests for weekday, weekend, no-data, and explicit-date cases.

## 12. Regression and safety tests

- [x] 12.1 Add drift tests for historical watchlist quality.
- [x] 12.2 Add lineage tests for candidate score and daily watchlist.
- [x] 12.3 Add assistant compare quality tests.
- [x] 12.4 Add filter validation tests across CLI and assistant paths.
- [x] 12.5 Add outcome versioning tests.
- [x] 12.6 Run Phase 5 E2E fixture tests.
- [x] 12.7 Run Phase 5.8 command tests.
- [x] 12.8 Run Phase 5.9 assistant tests.
- [x] 12.9 Run Phase 6 outcome tests.
- [x] 12.10 Run `cd vnalpha && pytest -q`.
