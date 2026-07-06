# Fix Remaining Drift and Accuracy Gaps

## Summary

Add an OpenSpec change for the remaining issues found after the latest implementation pass.

The codebase now includes many of the intended hardening features: feature as-of metadata, candidate outcome version fields, assistant parent traces, quality.get_many_status, shared command execution, and outcome evaluation runs. However, several gaps still prevent us from calling the consistency/data-drift/accuracy work complete.

This change specifies the remaining implementation work and tightens the acceptance criteria so implementation cannot introduce new ambiguity around migration, historical data, lineage, aggregate versioning, and metric policy.

## Remaining problems

### 1. Database migrations are incomplete

Schema definitions contain new columns, but existing DuckDB databases will not receive those columns because `CREATE TABLE IF NOT EXISTS` does not modify existing tables.

The migration runner currently adds only `tool_trace` parent columns. It must also add columns for feature metadata, rejected-symbol metadata, candidate outcome versioning, aggregate outcome versioning, and outcome evaluation tables.

Repository insert/upsert statements must also be updated to use explicit column lists. Otherwise, adding columns can break code paths that use positional `INSERT INTO table VALUES (...)`.

### 2. Feature status taxonomy is inconsistent

`feature_data_status` is currently written as `CURRENT` or `STALE`, but the contract requires explicit statuses such as `EXACT_DATE` and `STALE_DATE`.

The status policy also needs a precedence rule so the system behaves deterministically when multiple conditions apply, such as stale symbol data and missing benchmark data.

### 3. Skipped feature rows need explicit policy

`MISSING_CANONICAL` and `INSUFFICIENT_HISTORY` are useful diagnostic states, but the current MVP may skip symbols instead of persisting null feature rows. The spec must decide whether these states are persisted in `feature_snapshot` or reported only in build summary/skipped reasons.

### 4. Candidate lineage is still partial

Feature lineage includes provider, ingestion run id, source quality, bar date, and feature build version, but scoring currently propagates only provider and ingestion run id. Candidate score lineage therefore still misses important audit fields.

### 5. Historical watchlist quality still drifts

`get_watchlist_rich()` still uses the latest canonical quality row per symbol instead of quality as of the watchlist date.

Watchlist-level `quality.get_status()` also ranks latest rows before applying the watchlist date condition, which can incorrectly return `unknown` even when older valid quality data exists.

### 6. Tool-level filter validation does not fail closed

The `watchlist.filter` tool validates filters, but returns a warning-style `ToolOutput` on validation failure instead of raising an execution error. This allows command and assistant paths to interpret invalid filters as empty results.

The mapping must be explicit: validation failures should become `VALIDATION_ERROR` in command/assistant user-facing surfaces, while the underlying failed tool call should still create a failed `tool_trace`.

### 7. Assistant explain quality misses date

The assistant compare workflow has been improved, but the explain-symbol workflow still calls `quality.get_status` without the target date.

### 8. Outcome aggregate tables are not versioned

Candidate outcome rows include `evaluation_run_id`, `evaluator_version`, and `metric_policy_version`, but aggregate tables do not. Re-evaluation after data backfill can overwrite aggregate results without an auditable run/version link.

The aggregate history policy must be explicit. The preferred policy is to preserve evaluation history by including `evaluation_run_id` in aggregate primary keys. If latest-only aggregate tables are retained, historical aggregate snapshots must be stored elsewhere and the latest-only behavior must be documented and tested.

### 9. Metric policy is not configurable

Metric policy constants exist, but outcome evaluation is hardcoded to `CLOSE_ONLY_V1`. `OHLC_HIGH_LOW_V1` is defined but not executed.

The fallback behavior when high/low data is missing under `OHLC_HIGH_LOW_V1` must also be specified and tested.

### 10. Range evaluation semantics are not explicit

`evaluate_date_range()` currently behaves like repeated single-date evaluations. That can be acceptable, but the spec must require either one run per date or a parent batch run with child date runs, and CLI output must expose the selected behavior.

### 11. Assistant CLI date resolution is not DB-aware

`vnalpha ask` resolves date before opening the database connection, so it cannot use latest available research date when today has no data.

### 12. Test evidence is insufficient

Regression tests must prove the above behavior, especially migration safety, as-of quality, lineage propagation, fail-closed filters, metric policy selection, aggregate history policy, and assistant date handling.

## Goals

- Make migrations safe for existing DuckDB warehouses.
- Make repository writes robust against additive schema changes by using explicit column lists.
- Align feature status taxonomy with the spec.
- Decide and test skipped-feature-row behavior.
- Complete lineage propagation from canonical data to feature snapshots and candidate scores.
- Make all watchlist/quality review as-of-date correct.
- Make invalid filters fail closed in tool execution and map to validation errors in user-facing surfaces.
- Make assistant explain workflows date-aware.
- Version candidate and aggregate outcome records consistently.
- Make outcome aggregate history policy explicit and auditable.
- Implement configurable outcome metric policy with explicit missing high/low fallback.
- Resolve assistant CLI dates using the same DB-aware resolver as other CLI commands.
- Define range evaluation run semantics.
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
- repository insert/upsert statements for migrated tables use explicit column lists.
- feature_data_status uses the approved taxonomy and documented precedence.
- skipped symbols follow the selected persisted-row or build-summary policy.
- candidate_score.lineage_json includes feature_build_version, as_of_bar_date, and source_quality_status.
- get_watchlist_rich and quality.get_status use true as-of-date quality lookup.
- invalid filter input raises a tool error, creates failed tool_trace, and maps to VALIDATION_ERROR at command/assistant surfaces.
- assistant explain calls quality with the target date.
- outcome aggregate tables include evaluation/version metadata and follow an explicit history policy.
- outcome evaluator supports both CLOSE_ONLY_V1 and OHLC_HIGH_LOW_V1, including explicit fallback when high/low is missing.
- vnalpha ask resolves dates with a database connection.
- range evaluation run semantics are documented and visible in CLI output.
- targeted drift/accuracy regression tests pass.
```
