# Fix Remaining Drift and Accuracy Gaps

## Summary

Add an OpenSpec change for the remaining issues found after the latest implementation pass.

The codebase now includes many of the intended hardening features: feature as-of metadata, candidate outcome version fields, assistant parent traces, quality.get_many_status, shared command execution, and outcome evaluation runs. However, several gaps still prevent us from calling the consistency/data-drift/accuracy work complete.

This change specifies the remaining implementation work.

## Remaining problems

### 1. Database migrations are incomplete

Schema definitions contain new columns, but existing DuckDB databases will not receive those columns because `CREATE TABLE IF NOT EXISTS` does not modify existing tables.

The migration runner currently adds only `tool_trace` parent columns. It must also add columns for feature metadata, rejected-symbol metadata, candidate outcome versioning, and outcome evaluation tables.

### 2. Feature status taxonomy is inconsistent

`feature_data_status` is currently written as `CURRENT` or `STALE`, but the contract requires explicit statuses such as `EXACT_DATE` and `STALE_DATE`.

### 3. Candidate lineage is still partial

Feature lineage includes provider, ingestion run id, source quality, bar date, and feature build version, but scoring currently propagates only provider and ingestion run id. Candidate score lineage therefore still misses important audit fields.

### 4. Historical watchlist quality still drifts

`get_watchlist_rich()` still uses the latest canonical quality row per symbol instead of quality as of the watchlist date.

Watchlist-level `quality.get_status()` also ranks latest rows before applying the watchlist date condition, which can incorrectly return `unknown` even when older valid quality data exists.

### 5. Tool-level filter validation does not fail closed

The `watchlist.filter` tool validates filters, but returns a warning-style `ToolOutput` on validation failure instead of raising an execution error. This allows command and assistant paths to interpret invalid filters as empty results.

### 6. Assistant explain quality misses date

The assistant compare workflow has been improved, but the explain-symbol workflow still calls `quality.get_status` without the target date.

### 7. Outcome aggregate tables are not versioned

Candidate outcome rows include `evaluation_run_id`, `evaluator_version`, and `metric_policy_version`, but aggregate tables do not. Re-evaluation after data backfill can overwrite aggregate results without an auditable run/version link.

### 8. Metric policy is not configurable

Metric policy constants exist, but outcome evaluation is hardcoded to `CLOSE_ONLY_V1`. `OHLC_HIGH_LOW_V1` is defined but not executed.

### 9. Assistant CLI date resolution is not DB-aware

`vnalpha ask` resolves date before opening the database connection, so it cannot use latest available research date when today has no data.

### 10. Test evidence is insufficient

Regression tests must prove the above behavior, especially migration safety, as-of quality, lineage propagation, fail-closed filters, metric policy selection, and assistant date handling.

## Goals

- Make migrations safe for existing DuckDB warehouses.
- Align feature status taxonomy with the spec.
- Complete lineage propagation from canonical data to feature snapshots and candidate scores.
- Make all watchlist/quality review as-of-date correct.
- Make invalid filters fail closed in tool execution.
- Make assistant explain workflows date-aware.
- Version candidate and aggregate outcome records consistently.
- Implement configurable outcome metric policy.
- Resolve assistant CLI dates using the same DB-aware resolver as other CLI commands.
- Add targeted regression tests.

## Non-goals

- No new trading execution features.
- No broker/account/order/portfolio integration.
- No web retrieval or Python sandbox.
- No change to scoring weights.
- No ML ranking or backtest lab.

## Acceptance summary

This change is complete when:

```text
- existing DuckDB databases are migrated with all required new columns.
- feature_data_status uses the approved taxonomy.
- candidate_score.lineage_json includes feature_build_version, as_of_bar_date, and source_quality_status.
- get_watchlist_rich and quality.get_status use true as-of-date quality lookup.
- invalid filter input raises a tool error and creates failed tool_trace.
- assistant explain calls quality with the target date.
- outcome aggregate tables include evaluation/version metadata or a documented equivalent.
- outcome evaluator supports both CLOSE_ONLY_V1 and OHLC_HIGH_LOW_V1.
- vnalpha ask resolves dates with a database connection.
- targeted drift/accuracy regression tests pass.
```
