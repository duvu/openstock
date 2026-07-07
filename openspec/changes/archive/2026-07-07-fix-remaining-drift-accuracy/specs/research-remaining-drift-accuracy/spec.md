# Specification: Remaining Research Drift and Accuracy Fixes

## ADDED Requirements

### Requirement: Migrations shall upgrade existing DuckDB warehouses

The migration runner SHALL add all newly introduced columns to existing DuckDB tables.

It SHALL NOT rely on `CREATE TABLE IF NOT EXISTS` alone for existing tables.

Required migrated tables include:

```text
feature_snapshot
rejected_symbol
candidate_outcome
watchlist_outcome
score_bucket_performance
setup_type_performance
risk_flag_performance
```

Repository writes to migrated tables SHALL use explicit column lists and SHALL NOT rely on positional `INSERT INTO table VALUES (...)` when the table has additive migration columns.

#### Scenario: Old warehouse receives feature metadata columns

- **GIVEN** an existing warehouse has an old `feature_snapshot` table without `as_of_bar_date`
- **WHEN** migrations run
- **THEN** `feature_snapshot.as_of_bar_date` SHALL exist
- **AND** the migration SHALL be idempotent.

#### Scenario: Old warehouse receives outcome version columns

- **GIVEN** an existing warehouse has old outcome tables without evaluation metadata
- **WHEN** migrations run
- **THEN** candidate and aggregate outcome tables SHALL have evaluation/version metadata columns.

#### Scenario: Repository writes remain stable after additive migration

- **GIVEN** additive columns have been added to `candidate_outcome` and aggregate outcome tables
- **WHEN** repository upsert helpers write rows
- **THEN** writes SHALL succeed through explicit column lists
- **AND** they SHALL NOT depend on positional table column order.

---

### Requirement: Feature data status shall use approved taxonomy

Persisted `feature_snapshot.feature_data_status` SHALL use approved persisted values only:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
```

Diagnostic skipped-symbol values SHALL be reported in build summary/skipped reasons, not persisted in `feature_snapshot` during MVP:

```text
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

The system SHALL NOT persist `CURRENT` or `STALE`.

When multiple conditions apply, status precedence SHALL be:

```text
MISSING_CANONICAL
> INSUFFICIENT_HISTORY
> MISSING_BENCHMARK
> PARTIAL_BENCHMARK
> STALE_DATE
> EXACT_DATE
```

#### Scenario: Exact source bar status

- **GIVEN** feature date is `2026-07-06`
- **AND** the source bar date is also `2026-07-06`
- **WHEN** features are persisted
- **THEN** `feature_data_status` SHALL be `EXACT_DATE`.

#### Scenario: Stale source bar status

- **GIVEN** feature date is `2026-07-06`
- **AND** the latest source bar date is `2026-07-03`
- **WHEN** features are persisted
- **THEN** `feature_data_status` SHALL be `STALE_DATE`.

#### Scenario: Skipped symbol is not persisted as null feature row

- **GIVEN** symbol XYZ has no canonical OHLCV rows
- **WHEN** features are built for XYZ
- **THEN** no null `feature_snapshot` row SHALL be persisted for XYZ
- **AND** build summary or skipped reasons SHALL include `MISSING_CANONICAL`.

#### Scenario: Missing benchmark takes precedence over stale date

- **GIVEN** symbol data exists but is stale
- **AND** required benchmark data is missing
- **WHEN** features are built
- **THEN** persisted `feature_data_status` SHALL be `MISSING_BENCHMARK` if a feature row is persisted.

---

### Requirement: Candidate lineage shall include complete feature lineage

Candidate score lineage SHALL include lineage propagated from feature snapshots.

Required fields in `candidate_score.lineage_json`:

```text
scoring_version
feature_build_version
feature_date
as_of_bar_date
selected_provider
ingestion_run_id
source_quality_status
lineage_status
generated_at
```

Missing lineage SHALL be explicit through `lineage_status` and warnings.

Allowed `lineage_status` values:

```text
COMPLETE
PARTIAL
MISSING_PROVIDER
MISSING_INGESTION_RUN
MISSING_FEATURE_SOURCE
```

#### Scenario: Feature lineage is propagated to candidate score

- **GIVEN** `feature_snapshot.lineage_json` contains `feature_build_version`, `as_of_bar_date`, and `source_quality_status`
- **WHEN** candidate score is saved
- **THEN** `candidate_score.lineage_json` SHALL contain those fields.

#### Scenario: Watchlist preserves candidate lineage

- **GIVEN** candidate score lineage is complete
- **WHEN** the daily watchlist is generated
- **THEN** `daily_watchlist.lineage_json` SHALL preserve the candidate lineage.

#### Scenario: Missing lineage is visible

- **GIVEN** feature lineage is missing ingestion run id
- **WHEN** candidate score and watchlist rows are generated
- **THEN** lineage SHALL include `lineage_status = MISSING_INGESTION_RUN`
- **AND** `/lineage` or `/explain` SHALL surface the missing-lineage warning.

---

### Requirement: Watchlist quality shall use true as-of-date lookup

Historical watchlist quality SHALL use the latest canonical row at or before the watchlist date.

It SHALL NOT use a future canonical row.

#### Scenario: Future quality row is ignored

- **GIVEN** a watchlist row for FPT exists on `2026-07-06`
- **AND** FPT has canonical quality rows on `2026-07-05` and `2026-07-10`
- **WHEN** the watchlist for `2026-07-06` is rendered
- **THEN** quality SHALL be selected from `2026-07-05`
- **AND** the `2026-07-10` quality row SHALL NOT affect the result.

#### Scenario: Watchlist quality does not become unknown when older valid row exists

- **GIVEN** FPT latest canonical row is after the watchlist date
- **AND** an older valid canonical row exists before the watchlist date
- **WHEN** watchlist-level quality is queried
- **THEN** the older valid canonical row SHALL be used
- **AND** quality SHALL NOT incorrectly become `unknown`.

---

### Requirement: Invalid filter input shall fail closed

The `watchlist.filter` tool SHALL reject invalid filters by raising an error.

Invalid filter input SHALL NOT be returned as a successful empty or warning-only result.

Filter validation failures SHALL be treated as validation errors at user-facing command and assistant layers.

#### Scenario: Tool rejects unsupported filter field

- **GIVEN** a caller invokes `watchlist.filter` with field `raw_sql`
- **WHEN** filter validation runs
- **THEN** the tool SHALL fail
- **AND** a failed `tool_trace` row SHALL be persisted when called through traced execution.

#### Scenario: Command maps invalid filter to validation error

- **GIVEN** the user runs `/filter raw_sql=abc`
- **WHEN** the command executes
- **THEN** the command result SHALL be `VALIDATION_ERROR`
- **AND** it SHALL NOT be treated as a valid empty result
- **AND** it SHALL NOT be treated as a runtime `FAILED` unless a non-validation error occurs.

#### Scenario: Assistant maps invalid filter to validation error

- **GIVEN** an assistant plan attempts to call `watchlist.filter` with unsupported field `raw_sql`
- **WHEN** the assistant executes the plan
- **THEN** the assistant session SHALL be marked `VALIDATION_ERROR` or refused before tool execution according to policy
- **AND** the final answer SHALL NOT present the result as a valid empty candidate set.

---

### Requirement: Assistant explain workflow shall pass date to quality tool

The assistant explain-symbol plan SHALL call quality lookup with the same target date used for candidate explain and lineage.

#### Scenario: Explain quality is date-bounded

- **GIVEN** the user asks `Why is FPT in the watchlist on 2026-07-06?`
- **WHEN** the assistant builds the tool plan
- **THEN** `candidate.explain`, `lineage.get_symbol_lineage`, and `quality.get_status` SHALL all receive date `2026-07-06`.

---

### Requirement: Assistant CLI shall use DB-aware date resolution

`vnalpha ask` SHALL open the database and run migrations before resolving implicit dates.

It SHALL call date resolution with the database connection.

#### Scenario: Ask command resolves to latest research date

- **GIVEN** today has no watchlist data
- **AND** the latest watchlist date is `2026-07-03`
- **WHEN** the user runs `vnalpha ask "Show strongest candidates"` without an explicit date
- **THEN** the assistant SHALL use `2026-07-03` as the resolved research date.

---

### Requirement: Outcome aggregate tables shall be versioned and preserve history

Aggregate outcome tables SHALL include the same evaluation/version metadata used by candidate outcomes.

Required aggregate metadata:

```text
evaluation_run_id
evaluator_version
metric_policy_version
```

Affected tables:

```text
watchlist_outcome
score_bucket_performance
setup_type_performance
risk_flag_performance
```

Preferred key policy:

```text
watchlist_outcome: evaluation_run_id + watchlist_date + horizon_sessions
score_bucket_performance: evaluation_run_id + as_of_date + horizon_sessions + score_bucket
setup_type_performance: evaluation_run_id + as_of_date + horizon_sessions + setup_type
risk_flag_performance: evaluation_run_id + as_of_date + horizon_sessions + risk_flag
```

If latest-only aggregate tables are retained, a separate historical aggregate snapshot table SHALL preserve run-linked aggregate history.

#### Scenario: Aggregate rows reference evaluation run

- **GIVEN** `vnalpha outcome evaluate --date 2026-07-06` creates evaluation run `R`
- **WHEN** aggregate outcome rows are written
- **THEN** every aggregate row created by that command SHALL reference `R`.

#### Scenario: Recomputed aggregate is auditable

- **GIVEN** outcome evaluation is re-run after canonical data changes
- **WHEN** aggregate rows are inspected
- **THEN** the rows SHALL expose evaluation run and metric policy metadata
- **AND** the previous aggregate history SHALL remain auditable either through aggregate primary keys including `evaluation_run_id` or through a separate historical aggregate snapshot table.

#### Scenario: Manual aggregate recompute creates run context

- **GIVEN** aggregates are recomputed outside normal `outcome evaluate`
- **WHEN** recompute runs
- **THEN** a new evaluation run context SHALL be created with reason `MANUAL_RECOMPUTE` or equivalent.

---

### Requirement: Outcome evaluator shall support configurable metric policy

Outcome evaluation SHALL support both metric policies:

```text
CLOSE_ONLY_V1
OHLC_HIGH_LOW_V1
```

When `OHLC_HIGH_LOW_V1` is used:

```text
max_gain = max(high / entry_close - 1)
max_drawdown = min(low / entry_close - 1)
```

When `CLOSE_ONLY_V1` is used:

```text
max_gain = max(close / entry_close - 1)
max_drawdown = min(close / entry_close - 1)
```

The selected metric policy SHALL be persisted on candidate and aggregate outcome rows.

#### Scenario: OHLC policy uses high and low

- **GIVEN** entry close is 100
- **AND** forward window high is 112
- **AND** forward window low is 94
- **WHEN** metric policy is `OHLC_HIGH_LOW_V1`
- **THEN** max gain SHALL be 0.12
- **AND** max drawdown SHALL be -0.06.

#### Scenario: Close-only policy uses closes

- **GIVEN** entry close is 100
- **AND** forward window closes are 102, 95, 108
- **WHEN** metric policy is `CLOSE_ONLY_V1`
- **THEN** max gain SHALL be 0.08
- **AND** max drawdown SHALL be -0.05.

#### Scenario: OHLC policy handles missing high or low explicitly

- **GIVEN** metric policy is `OHLC_HIGH_LOW_V1`
- **AND** one or more bars in the forward window lack high or low
- **WHEN** outcome evaluation runs
- **THEN** the evaluator SHALL either mark the outcome `PARTIAL` with a warning or use explicit close-only fallback
- **AND** the effective metric policy or fallback warning SHALL be persisted.

---

### Requirement: Range outcome evaluation shall expose run semantics

Range evaluation SHALL use explicit run semantics.

MVP behavior:

```text
evaluate_date_range(from_date, to_date) creates one evaluation_run per watchlist date.
```

#### Scenario: Range evaluation reports per-date run ids

- **GIVEN** watchlists exist for `2026-07-01` and `2026-07-02`
- **WHEN** the user runs `vnalpha outcome evaluate --from 2026-07-01 --to 2026-07-02`
- **THEN** the command SHALL create one evaluation run per date
- **AND** CLI output SHALL show the evaluation_run_id for each date.

---

### Requirement: Regression tests shall prove remaining drift fixes

The codebase SHALL include targeted tests for the remaining drift and accuracy fixes.

Required test coverage:

```text
old-schema migrations
explicit repository write column lists where schema is additive
feature status taxonomy and precedence
skipped-symbol behavior
lineage propagation
historical watchlist quality
watchlist-level quality as-of bug
filter fail-closed behavior and validation-error mapping
assistant explain date propagation
assistant DB-aware date resolution
outcome aggregate versioning and history preservation
metric policy execution and missing high/low fallback
range evaluation run semantics
```

#### Scenario: Full targeted suite passes

- **GIVEN** the remaining fixes are implemented
- **WHEN** `cd vnalpha && pytest -q` runs
- **THEN** all targeted drift, lineage, quality, assistant, and outcome tests SHALL pass.
