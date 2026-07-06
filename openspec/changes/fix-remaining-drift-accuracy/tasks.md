# Tasks: Fix Remaining Drift and Accuracy Gaps

## 1. Migration safety

- [ ] 1.1 Add migration helper for new `feature_snapshot` columns.
- [ ] 1.2 Add migration helper for new `rejected_symbol` metadata columns.
- [ ] 1.3 Add migration helper for new `candidate_outcome` version columns.
- [ ] 1.4 Add migration helper for aggregate outcome version columns.
- [ ] 1.5 Ensure `outcome_evaluation_run` is created for old DBs.
- [ ] 1.6 Add old-schema migration test using in-memory DuckDB.
- [ ] 1.7 Verify migration is idempotent.
- [ ] 1.8 Replace positional `INSERT INTO ... VALUES (...)` writes on migrated tables with explicit column lists.
- [ ] 1.9 Add regression test proving repository upserts still work after additive columns are present.

## 2. Feature status taxonomy and skipped-symbol policy

- [ ] 2.1 Replace `CURRENT` with `EXACT_DATE`.
- [ ] 2.2 Replace `STALE` with `STALE_DATE`.
- [ ] 2.3 Add benchmark-aware statuses: `MISSING_BENCHMARK` and `PARTIAL_BENCHMARK`.
- [ ] 2.4 Implement status precedence: `MISSING_CANONICAL > INSUFFICIENT_HISTORY > MISSING_BENCHMARK > PARTIAL_BENCHMARK > STALE_DATE > EXACT_DATE`.
- [ ] 2.5 Document MVP policy that skipped symbols are reported in build summary/skipped reasons, not persisted as null feature rows.
- [ ] 2.6 Ensure persisted `feature_snapshot` rows use only `EXACT_DATE`, `STALE_DATE`, `MISSING_BENCHMARK`, or `PARTIAL_BENCHMARK`.
- [ ] 2.7 Add tests for exact date, stale date, missing benchmark, partial benchmark, missing canonical, and insufficient history.

## 3. Complete lineage propagation

- [ ] 3.1 Propagate `feature_build_version` from feature lineage to scored result.
- [ ] 3.2 Propagate `as_of_bar_date` from feature lineage to scored result.
- [ ] 3.3 Propagate `source_quality_status` from feature lineage to scored result.
- [ ] 3.4 Ensure `candidate_score.lineage_json` contains all propagated fields.
- [ ] 3.5 Ensure `daily_watchlist.lineage_json` copies candidate score lineage unchanged.
- [ ] 3.6 Add `lineage_status` and `lineage_warnings` for missing lineage.
- [ ] 3.7 Ensure `/lineage` and `/explain` expose missing-lineage warnings.
- [ ] 3.8 Add tests for complete and partial lineage.

## 4. Historical quality as-of-date correctness

- [ ] 4.1 Rewrite `get_watchlist_rich()` quality join to use `time <= daily_watchlist.date` before ranking/selection.
- [ ] 4.2 Rewrite watchlist-level `quality.get_status()` to use the same as-of semantics.
- [ ] 4.3 Ensure symbol-level quality returns the latest row at or before target date.
- [ ] 4.4 Ensure rejected records are bounded by affected bar date.
- [ ] 4.5 Add tests proving future quality rows do not affect historical watchlist review.
- [ ] 4.6 Add test proving quality does not become `unknown` when latest row is after target date but older valid row exists.

## 5. Fail-closed filter validation

- [ ] 5.1 Change `watchlist.filter` so invalid filters raise an error instead of returning warning output.
- [ ] 5.2 Ensure `TracedLocalToolExecutor` records failed tool trace on invalid filters.
- [ ] 5.3 Map filter validation failure to `VALIDATION_ERROR` in CLI/TUI command path.
- [ ] 5.4 Map filter validation failure to assistant `VALIDATION_ERROR`, unless refused earlier by policy.
- [ ] 5.5 Add assistant-path test proving invalid filters are not treated as empty results.
- [ ] 5.6 Add command-path test proving invalid filters are not treated as runtime `FAILED` unless a non-validation error occurs.

## 6. Assistant explain date consistency

- [ ] 6.1 Add target date to `quality.get_status` step in explain-symbol plan.
- [ ] 6.2 Ensure assistant planning receives resolved date consistently.
- [ ] 6.3 Change `vnalpha ask` to open DB before resolving date.
- [ ] 6.4 Add test for weekend/no-data date resolution in `vnalpha ask`.
- [ ] 6.5 Add test proving explain quality is date-bounded.

## 7. Outcome aggregate versioning and history

- [ ] 7.1 Add `evaluation_run_id` to `watchlist_outcome`.
- [ ] 7.2 Add `evaluator_version` and `metric_policy_version` to `watchlist_outcome`.
- [ ] 7.3 Add the same three fields to `score_bucket_performance`.
- [ ] 7.4 Add the same three fields to `setup_type_performance`.
- [ ] 7.5 Add the same three fields to `risk_flag_performance`.
- [ ] 7.6 Update dataclasses.
- [ ] 7.7 Update repository upserts and selects.
- [ ] 7.8 Update `aggregate_all()` to accept and persist version metadata.
- [ ] 7.9 Add `evaluation_run_id` to aggregate primary keys, or implement separate historical aggregate snapshot tables if latest-only aggregates are retained.
- [ ] 7.10 Add tests that aggregates reference the evaluation run that generated them.
- [ ] 7.11 Add test proving re-evaluation does not silently destroy the only auditable aggregate history.
- [ ] 7.12 Add MANUAL_RECOMPUTE evaluation-run behavior for manual aggregate recompute paths.

## 8. Metric policy execution

- [ ] 8.1 Add metric policy parameter to `evaluate_watchlist_date()`.
- [ ] 8.2 Add metric policy parameter to `evaluate_date_range()`.
- [ ] 8.3 Add CLI option `--metric-policy` to `vnalpha outcome evaluate`.
- [ ] 8.4 Implement `OHLC_HIGH_LOW_V1` using high for max gain and low for max drawdown.
- [ ] 8.5 Keep `CLOSE_ONLY_V1` behavior explicitly available.
- [ ] 8.6 Persist selected metric policy on candidate and aggregate outcomes.
- [ ] 8.7 Implement and document missing high/low behavior: strict partial status or explicit close-only fallback.
- [ ] 8.8 Add tests for both metric policies and missing high/low fallback.

## 9. Range evaluation semantics

- [ ] 9.1 Document MVP behavior: one `evaluation_run_id` per watchlist date in `evaluate_date_range()`.
- [ ] 9.2 Ensure range CLI output lists every date and evaluation run id.
- [ ] 9.3 Add tests for range evaluation run id reporting.
- [ ] 9.4 If parent batch runs are implemented later, add parent/child run schema and tests.

## 10. Documentation and user-facing output

- [ ] 10.1 Document approved `feature_data_status` values and precedence.
- [ ] 10.2 Document skipped-symbol behavior for missing canonical and insufficient history.
- [ ] 10.3 Document lineage status and missing-lineage behavior.
- [ ] 10.4 Document outcome metric policy semantics and fallback behavior.
- [ ] 10.5 Document one-run-per-date evaluation behavior or batch run support.
- [ ] 10.6 Ensure CLI report includes evaluation run id and metric policy where relevant.

## 11. Validation

- [ ] 11.1 Run `cd vnalpha && pytest -q`.
- [ ] 11.2 Run targeted migration tests.
- [ ] 11.3 Run targeted lineage tests.
- [ ] 11.4 Run targeted quality-as-of tests.
- [ ] 11.5 Run targeted assistant date/quality tests.
- [ ] 11.6 Run targeted outcome versioning and metric policy tests.
- [ ] 11.7 Run targeted range-evaluation tests.
- [ ] 11.8 Run Phase 5 E2E regression tests.
- [ ] 11.9 Run Phase 5.8/5.9/6 regression tests.
