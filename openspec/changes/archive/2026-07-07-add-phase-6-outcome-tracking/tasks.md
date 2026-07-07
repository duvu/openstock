# Tasks: Phase 6 Outcome Tracking and Feedback Loop

## 1. Outcome schema

- [x] 1.1 Add `candidate_outcome` table.
- [x] 1.2 Add `watchlist_outcome` table.
- [x] 1.3 Add `score_bucket_performance` table.
- [x] 1.4 Add `setup_type_performance` table.
- [x] 1.5 Add `risk_flag_performance` table.
- [x] 1.6 Add migration tests confirming all outcome tables are created.
- [x] 1.7 Ensure Phase 5 tables remain unchanged and existing migrations still pass.

## 2. Outcome models and repository helpers

- [x] 2.1 Add `vnalpha.outcomes.models` with candidate outcome, aggregate outcome, horizon, and status models.
- [x] 2.2 Add `OutcomeStatus` values: `COMPLETE`, `PENDING`, `PARTIAL`, `MISSING_DATA`, `ERROR`.
- [x] 2.3 Add repository helpers to upsert/list candidate outcomes.
- [x] 2.4 Add repository helpers to upsert/list watchlist outcomes.
- [x] 2.5 Add repository helpers to upsert/list score bucket performance.
- [x] 2.6 Add repository helpers to upsert/list setup type performance.
- [x] 2.7 Add repository helpers to upsert/list risk flag performance.

## 3. Horizon and bar selection

- [x] 3.1 Add default horizons: 5, 10, 20, 60 sessions.
- [x] 3.2 Implement entry close selection for watchlist date.
- [x] 3.3 Implement N-session future exit close selection.
- [x] 3.4 Implement benchmark entry/exit selection using VNINDEX.
- [x] 3.5 Mark incomplete horizons as `PENDING`.
- [x] 3.6 Mark absent symbol or benchmark data as `MISSING_DATA` or `PARTIAL`.
- [x] 3.7 Add unit tests for trading-bar horizon selection.

## 4. Candidate metrics

- [x] 4.1 Implement `forward_return`.
- [x] 4.2 Implement `benchmark_return`.
- [x] 4.3 Implement `excess_return_vs_vnindex`.
- [x] 4.4 Implement `max_gain`.
- [x] 4.5 Implement `max_drawdown`.
- [x] 4.6 Implement hit/failure classification.
- [x] 4.7 Add unit tests for all metric calculations.

## 5. Candidate outcome evaluator

- [x] 5.1 Select persisted `daily_watchlist` rows by date or date range.
- [x] 5.2 Join persisted `candidate_score` for score, class, setup, risk flags, and lineage.
- [x] 5.3 Evaluate every candidate for every configured horizon.
- [x] 5.4 Upsert `candidate_outcome` rows.
- [x] 5.5 Store bars available and required bars.
- [x] 5.6 Store evaluator errors in `error_json` without crashing the whole batch.
- [x] 5.7 Add integration tests with fixture watchlists and OHLCV data.

## 6. Aggregate performance

- [x] 6.1 Aggregate `watchlist_outcome` by watchlist date and horizon.
- [x] 6.2 Aggregate `score_bucket_performance` by score bucket and horizon.
- [x] 6.3 Aggregate `setup_type_performance` by setup type and horizon.
- [x] 6.4 Aggregate `risk_flag_performance` by risk flag and horizon.
- [x] 6.5 Add tests for aggregate counts, averages, medians, hit rates, and failure rates.
- [x] 6.6 Add tests for ignoring or separately counting pending/missing outcomes.

## 7. CLI integration

- [x] 7.1 Add `vnalpha outcome evaluate --date <date>`.
- [x] 7.2 Add `vnalpha outcome evaluate --from <date> --to <date>`.
- [x] 7.3 Add `vnalpha outcome candidates --date <date> --horizon <n>`.
- [x] 7.4 Add `vnalpha outcome watchlist --date <date> --horizon <n>`.
- [x] 7.5 Add `vnalpha outcome buckets --horizon <n>`.
- [x] 7.6 Add `vnalpha outcome setups --horizon <n>`.
- [x] 7.7 Add `vnalpha outcome risks --horizon <n>`.
- [x] 7.8 Add `vnalpha outcome report --horizon <n>`.
- [x] 7.9 Render CLI output with Rich tables/panels.
- [x] 7.10 Add CLI contract tests for outcome commands.

## 8. TUI integration

- [x] 8.1 Add Outcome Review screen.
- [x] 8.2 Add watchlist outcome summary panel.
- [x] 8.3 Add candidate outcome table.
- [x] 8.4 Add score bucket performance panel.
- [x] 8.5 Add setup type performance panel.
- [x] 8.6 Add risk flag performance panel.
- [x] 8.7 Add pending/missing data panel.
- [x] 8.8 Add TUI smoke tests for outcome screen.

## 9. Calibration report

- [x] 9.1 Add deterministic calibration report generator.
- [x] 9.2 Report whether higher score buckets outperform lower buckets.
- [x] 9.3 Report candidate class performance.
- [x] 9.4 Report setup type performance.
- [x] 9.5 Report risk flag performance.
- [x] 9.6 Report pending/missing-data counts.
- [x] 9.7 Add tests for report generation from fixture aggregates.

## 10. Safety and product boundary

- [x] 10.1 Ensure outcome code and rendered text use research/evaluation language only.
- [x] 10.2 Add tests banning order/account/portfolio/execution wording in outcome views.
- [x] 10.3 Ensure outcome metrics are not rendered as buy/sell advice.
- [x] 10.4 Ensure outcome commands cannot mutate scoring rules automatically.
- [x] 10.5 Ensure evaluator does not recompute historical watchlists from current scoring code.

## 11. Documentation

- [x] 11.1 Document outcome tables.
- [x] 11.2 Document horizon definitions.
- [x] 11.3 Document forward return and excess return formulas.
- [x] 11.4 Document hit/failure rule defaults.
- [x] 11.5 Document CLI outcome commands.
- [x] 11.6 Document TUI Outcome Review screen.
- [x] 11.7 Document interpretation caveats and research-only boundary.

## 12. Validation

- [x] 12.1 Run `cd vnalpha && pytest -q`.
- [x] 12.2 Run outcome targeted tests.
- [x] 12.3 Run Phase 5 E2E fixture tests.
- [x] 12.4 Run Phase 5.8 command-layer tests if present.
- [x] 12.5 Run Phase 5.9 assistant tests if present.
- [x] 12.6 Manually smoke-test:

```bash
vnalpha outcome evaluate --date 2026-07-06
vnalpha outcome candidates --date 2026-07-06 --horizon 20
vnalpha outcome watchlist --date 2026-07-06 --horizon 20
vnalpha outcome buckets --horizon 20
vnalpha outcome setups --horizon 20
vnalpha outcome risks --horizon 20
vnalpha outcome report --horizon 20
```
