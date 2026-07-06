# Design: Remaining Drift and Accuracy Fixes

## Overview

This change closes the final gap between the current implementation and the drift/accuracy hardening requirements.

The design focuses on practical completion, not new features.

```text
migrations
explicit repository writes
feature status taxonomy and precedence
skipped feature-row policy
lineage propagation
historical quality as-of lookup
filter fail-closed semantics
assistant date consistency
outcome aggregate versioning and history policy
metric policy selection and fallback
range evaluation semantics
regression tests
```

## 1. Migration safety for existing DuckDB databases

### Problem

New columns were added to schema DDL, but existing DuckDB files are not altered by `CREATE TABLE IF NOT EXISTS`.

### Design

Add migration helpers:

```text
_migrate_feature_snapshot_columns(conn)
_migrate_rejected_symbol_columns(conn)
_migrate_candidate_outcome_columns(conn)
_migrate_outcome_aggregate_columns(conn)
_migrate_outcome_evaluation_run_table(conn)
```

Minimum required `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements:

```text
feature_snapshot.as_of_bar_date DATE
feature_snapshot.benchmark_as_of_bar_date DATE
feature_snapshot.source_row_count INTEGER
feature_snapshot.benchmark_row_count INTEGER
feature_snapshot.feature_data_status VARCHAR
feature_snapshot.feature_build_version VARCHAR
feature_snapshot.feature_generated_at TIMESTAMPTZ
feature_snapshot.lineage_json VARCHAR

rejected_symbol.ingestion_run_id VARCHAR
rejected_symbol.provider VARCHAR

candidate_outcome.evaluation_run_id VARCHAR
candidate_outcome.evaluator_version VARCHAR
candidate_outcome.metric_policy_version VARCHAR
candidate_outcome.symbol_bar_count INTEGER
candidate_outcome.benchmark_bar_count INTEGER

watchlist_outcome.evaluation_run_id VARCHAR
watchlist_outcome.evaluator_version VARCHAR
watchlist_outcome.metric_policy_version VARCHAR

score_bucket_performance.evaluation_run_id VARCHAR
score_bucket_performance.evaluator_version VARCHAR
score_bucket_performance.metric_policy_version VARCHAR

setup_type_performance.evaluation_run_id VARCHAR
setup_type_performance.evaluator_version VARCHAR
setup_type_performance.metric_policy_version VARCHAR

risk_flag_performance.evaluation_run_id VARCHAR
risk_flag_performance.evaluator_version VARCHAR
risk_flag_performance.metric_policy_version VARCHAR
```

`outcome_evaluation_run` should be created through normal DDL and should also be safe when introduced to an old DB.

### Repository write rule

All repository writes to migrated tables SHALL use explicit column lists.

Do not use:

```sql
INSERT INTO candidate_outcome VALUES (...)
```

Use:

```sql
INSERT INTO candidate_outcome (
  symbol,
  watchlist_date,
  horizon_sessions,
  ...
) VALUES (...)
```

This applies to:

```text
feature_snapshot
rejected_symbol
candidate_score
daily_watchlist
candidate_outcome
watchlist_outcome
score_bucket_performance
setup_type_performance
risk_flag_performance
outcome_evaluation_run
```

### Migration test

Create an old-schema in-memory DuckDB, run migrations, and verify all columns exist. Run migrations twice to prove idempotency.

## 2. Feature status taxonomy

### Problem

Current code writes `CURRENT` and `STALE`; the target taxonomy uses `EXACT_DATE` and `STALE_DATE` plus benchmark/missing states.

### Design

Replace status values:

```text
CURRENT -> EXACT_DATE
STALE   -> STALE_DATE
```

Approved persisted `feature_data_status` values:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
```

Diagnostic statuses for skipped symbols:

```text
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

### Status precedence

When multiple conditions apply, use this precedence:

```text
MISSING_CANONICAL
> INSUFFICIENT_HISTORY
> MISSING_BENCHMARK
> PARTIAL_BENCHMARK
> STALE_DATE
> EXACT_DATE
```

MVP persistence policy:

```text
- feature_snapshot SHALL persist only successfully built feature rows.
- MISSING_CANONICAL and INSUFFICIENT_HISTORY SHALL be reported in build summary/skipped reasons, not persisted as null feature rows.
- If a future implementation persists skipped rows, it must add a dedicated nullable-feature schema and tests before enabling that behavior.
```

Persisted feature rows therefore use one of:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
```

Skipped rows may report:

```text
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

but they are not written to `feature_snapshot` in the MVP.

## 3. Complete lineage propagation

### Problem

Feature `lineage_json` has enough metadata, but scoring only forwards provider and ingestion run id.

### Design

In `score_universe()` parse `feature_snapshot.lineage_json` and set:

```text
scored.provider
scored.ingestion_run_id
scored.feature_build_version
scored.as_of_bar_date
scored.source_quality_status
```

`save_candidate_score()` already expects these fields and should persist them in `candidate_score.lineage_json`.

`daily_watchlist.lineage_json` should copy the candidate score lineage unchanged.

### Missing lineage behavior

If lineage is missing, include:

```text
lineage_status
lineage_warnings
```

Allowed `lineage_status` values:

```text
COMPLETE
PARTIAL
MISSING_PROVIDER
MISSING_INGESTION_RUN
MISSING_FEATURE_SOURCE
```

`/lineage` and `/explain` must surface missing lineage warnings.

## 4. True as-of-date quality lookup

### Problem

Two quality paths are still incorrect:

```text
get_watchlist_rich(): latest quality row overall per symbol.
quality.get_status(): ranks latest row before applying watchlist date bound.
```

### Design

Implement a shared query pattern based on lateral/as-of lookup.

For one symbol:

```sql
SELECT symbol, time, quality_status, selected_provider
FROM canonical_ohlcv
WHERE symbol = ?
  AND interval = '1D'
  AND CAST(time AS DATE) <= ?
ORDER BY time DESC
LIMIT 1
```

For watchlist quality:

```sql
SELECT dw.symbol, co.quality_status, co.selected_provider
FROM daily_watchlist dw
LEFT JOIN LATERAL (
  SELECT quality_status, selected_provider
  FROM canonical_ohlcv co
  WHERE co.symbol = dw.symbol
    AND co.interval = '1D'
    AND CAST(co.time AS DATE) <= dw.date
  ORDER BY co.time DESC
  LIMIT 1
) co ON TRUE
WHERE dw.date = ?
ORDER BY dw.rank
```

If DuckDB compatibility makes lateral joins awkward, use a correlated subquery or join against a CTE that ranks after applying `time <= dw.date`.

`get_watchlist_rich()` and `quality.get_status()` must use the same as-of semantics.

## 5. Fail-closed filter validation

### Problem

`watchlist.filter` returns `ToolOutput(data=None, warnings=[...])` when validation fails.

### Design

Make invalid filters raise a tool-layer error.

Recommended behavior:

```text
validate_filters(...) raises FilterValidationError
watchlist.filter does not catch it, or wraps it as ToolExecutionError
TracedLocalToolExecutor records tool_trace.status = FAILED
CommandExecutor maps FilterValidationError to VALIDATION_ERROR
Assistant marks assistant_session as VALIDATION_ERROR or REFUSED according to policy
Assistant answer must not present invalid-filter output as an empty valid result
```

The tool must not silently return an empty result for invalid fields.

### Mapping rule

Filter validation failures are user/input validation failures, not runtime failures.

```text
CLI/TUI command result: VALIDATION_ERROR
assistant_session status: VALIDATION_ERROR, or REFUSED if policy classifies the prompt as unsafe before tool execution
tool_trace status: FAILED
```

## 6. Assistant explain date consistency

### Problem

`explain_symbol` plan passes date to score and lineage tools, but not to quality.

### Design

When building the explain plan:

```text
quality.get_status arguments = {symbol, date}
```

If date is missing, AssistantApp should inject the resolved target date before planning or normalize entities consistently.

## 7. Outcome aggregate versioning and history policy

### Problem

Candidate outcome rows have evaluation/version metadata; aggregate rows do not.

### Design

Add version fields to aggregate tables:

```text
evaluation_run_id
evaluator_version
metric_policy_version
```

Update aggregate dataclasses, repository upserts, and `aggregate_all()` to accept and persist these fields.

When `evaluate_watchlist_date()` calls `aggregate_all()`, pass:

```text
evaluation_run_id
evaluator_version
metric_policy_version
```

### History policy

Preferred policy: preserve aggregate history.

```text
watchlist_outcome primary key:
  evaluation_run_id, watchlist_date, horizon_sessions

score_bucket_performance primary key:
  evaluation_run_id, as_of_date, horizon_sessions, score_bucket

setup_type_performance primary key:
  evaluation_run_id, as_of_date, horizon_sessions, setup_type

risk_flag_performance primary key:
  evaluation_run_id, as_of_date, horizon_sessions, risk_flag
```

If the implementation keeps latest-only aggregate tables with existing keys, it must add separate historical aggregate snapshot tables and document the latest-only behavior. It must not silently overwrite the only copy of aggregate results without preserving a run-linked history.

Manual aggregate recompute outside an evaluation run must create a new evaluation run with reason `MANUAL_RECOMPUTE` or equivalent.

## 8. Configurable outcome metric policy

### Problem

`CLOSE_ONLY_V1` and `OHLC_HIGH_LOW_V1` are defined, but evaluator is hardcoded to `CLOSE_ONLY_V1`.

### Design

Add a metric policy parameter:

```python
evaluate_watchlist_date(conn, watchlist_date, horizons=None, metric_policy=CLOSE_ONLY_V1)
```

CLI:

```bash
vnalpha outcome evaluate --date 2026-07-06 --metric-policy OHLC_HIGH_LOW_V1
```

Behavior:

```text
CLOSE_ONLY_V1:
  max_gain = max(close / entry_close - 1)
  max_drawdown = min(close / entry_close - 1)

OHLC_HIGH_LOW_V1:
  max_gain = max(high / entry_close - 1)
  max_drawdown = min(low / entry_close - 1)
```

If high/low is missing under `OHLC_HIGH_LOW_V1`, fallback must be explicit.

Allowed policies:

```text
OHLC_HIGH_LOW_V1_STRICT:
  missing high/low => outcome_status = PARTIAL and warning persisted

OHLC_HIGH_LOW_V1_FALLBACK:
  missing high/low => use close-only for affected metric and persist metric_policy_effective = CLOSE_ONLY_V1_FALLBACK
```

MVP recommended behavior:

```text
Use OHLC_HIGH_LOW_V1_FALLBACK as the CLI default only if high/low coverage is incomplete.
Otherwise keep CLOSE_ONLY_V1 as default and require explicit --metric-policy OHLC_HIGH_LOW_V1.
```

The selected behavior must be documented and tested.

## 9. DB-aware assistant CLI date resolution

### Problem

`vnalpha ask` resolves date before opening DuckDB, so it cannot resolve to latest available research date.

### Design

Change flow:

```text
conn = get_connection()
run_migrations(conn=conn)
resolved_date = resolve_date(date, conn=conn)
assistant.ask(..., date=resolved_date)
```

This makes `ask` consistent with `build features`, `score`, and `watchlist` commands.

## 10. Range evaluation semantics

### Problem

Range evaluation can be represented either as multiple single-date runs or as a parent batch run. The current code path appears closer to multiple single-date runs.

### Design

MVP policy:

```text
evaluate_date_range(from_date, to_date) SHALL create one evaluation_run per watchlist date.
```

CLI output must list the run ids:

```text
2026-07-01 -> evaluation_run_id A
2026-07-02 -> evaluation_run_id B
...
```

If a future parent batch run is added, it must add:

```text
outcome_evaluation_batch_run
batch_run_id
child evaluation_run_id references
```

The range behavior must be documented and tested.

## 11. Tests

Add tests for each completion requirement.

Minimum test files:

```text
tests/test_migrations_drift_columns.py
tests/test_feature_snapshot_metadata.py
tests/test_lineage_propagation.py
tests/test_quality_as_of.py
tests/test_filter_fail_closed.py
tests/test_assistant_date_and_quality.py
tests/test_outcome_versioning.py
tests/test_metric_policy.py
tests/test_outcome_range_runs.py
```

Each test should use in-memory DuckDB fixtures and fake/stub dependencies where needed.

## Completion rule

This change is complete only when:

```text
cd vnalpha && pytest -q
```

passes and the targeted tests above prove the drift/accuracy fixes.
