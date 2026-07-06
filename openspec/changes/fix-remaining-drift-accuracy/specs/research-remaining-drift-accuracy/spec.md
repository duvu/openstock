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

#### Scenario: Old warehouse receives feature metadata columns

- **GIVEN** an existing warehouse has an old `feature_snapshot` table without `as_of_bar_date`
- **WHEN** migrations run
- **THEN** `feature_snapshot.as_of_bar_date` SHALL exist
- **AND** the migration SHALL be idempotent.

#### Scenario: Old warehouse receives outcome version columns

- **GIVEN** an existing warehouse has old outcome tables without evaluation metadata
- **WHEN** migrations run
- **THEN** candidate and aggregate outcome tables SHALL have evaluation/version metadata columns.

---

### Requirement: Feature data status shall use approved taxonomy

Persisted `feature_snapshot.feature_data_status` SHALL use approved values only:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

The system SHALL NOT persist `CURRENT` or `STALE`.

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

#### Scenario: Feature lineage is propagated to candidate score

- **GIVEN** `feature_snapshot.lineage_json` contains `feature_build_version`, `as_of_bar_date`, and `source_quality_status`
- **WHEN** candidate score is saved
- **THEN** `candidate_score.lineage_json` SHALL contain those fields.

#### Scenario: Watchlist preserves candidate lineage

- **GIVEN** candidate score lineage is complete
- **WHEN** the daily watchlist is generated
- **THEN** `daily_watchlist.lineage_json` SHALL preserve the candidate lineage.

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

#### Scenario: Tool rejects unsupported filter field

- **GIVEN** a caller invokes `watchlist.filter` with field `raw_sql`
- **WHEN** filter validation runs
- **THEN** the tool SHALL fail
- **AND** a failed `tool_trace` row SHALL be persisted when called through traced execution.

#### Scenario: Command maps invalid filter to validation error

- **GIVEN** the user runs `/filter raw_sql=abc`
- **WHEN** the command executes
- **THEN** the command result SHALL be `VALIDATION_ERROR`
- **AND** it SHALL NOT be treated as a valid empty result.

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

### Requirement: Outcome aggregate tables shall be versioned

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

#### Scenario: Aggregate rows reference evaluation run

- **GIVEN** `vnalpha outcome evaluate --date 2026-07-06` creates evaluation run `R`
- **WHEN** aggregate outcome rows are written
- **THEN** every aggregate row created by that command SHALL reference `R`.

#### Scenario: Recomputed aggregate is auditable

- **GIVEN** outcome evaluation is re-run after canonical data changes
- **WHEN** aggregate rows are inspected
- **THEN** the rows SHALL expose evaluation run and metric policy metadata.

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

---

### Requirement: Regression tests shall prove remaining drift fixes

The codebase SHALL include targeted tests for the remaining drift and accuracy fixes.

Required test coverage:

```text
old-schema migrations
feature status taxonomy
lineage propagation
historical watchlist quality
watchlist-level quality as-of bug
filter fail-closed behavior
assistant explain date propagation
assistant DB-aware date resolution
outcome aggregate versioning
metric policy execution
```

#### Scenario: Full targeted suite passes

- **GIVEN** the remaining fixes are implemented
- **WHEN** `cd vnalpha && pytest -q` runs
- **THEN** all targeted drift, lineage, quality, assistant, and outcome tests SHALL pass.
