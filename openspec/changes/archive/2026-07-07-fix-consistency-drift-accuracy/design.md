# Design: Consistency, Data Drift, and Accuracy Fixes

## Design principles

### One source of truth per concept

Validation, date resolution, quality lookup, lineage propagation, and outcome metric definitions must live in shared modules. CLI handlers, TUI screens, assistant tools, and reports should call the same shared logic.

### Historical views must be time-aware

Historical review must use data available as of the requested date.

Default rule:

```text
for target date D, choose the latest valid row with source_bar_date <= D
```

A current/latest view may exist, but it must be explicit.

### Every derived artifact must be auditable

Every feature, score, watchlist, assistant answer, and outcome record should tell us:

```text
what input data was used
what date it represents
what code/model/rule version generated it
when it was generated
whether inputs were exact, stale, partial, or missing
```

### Avoid silent fallback behavior

Production paths should not silently bypass the traced tool registry. Test-only shortcuts must be explicit and isolated.

## Proposed changes

## 1. Feature snapshot as-of metadata

### Problem

`build_features()` currently selects the last canonical OHLCV row at or before the target date, but persists the feature row under `feature_snapshot.date = target_date` without storing the actual source bar date.

### Design

Extend `feature_snapshot` with source-date metadata:

```text
as_of_bar_date                DATE
benchmark_as_of_bar_date      DATE
source_row_count              INTEGER
benchmark_row_count           INTEGER
feature_data_status           VARCHAR
feature_build_version         VARCHAR
feature_generated_at          TIMESTAMPTZ
```

Allowed `feature_data_status` values:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

Rules:

```text
EXACT_DATE      as_of_bar_date == feature_snapshot.date
STALE_DATE      as_of_bar_date < feature_snapshot.date
MISSING_BENCHMARK rs fields are null because VNINDEX data is unavailable
PARTIAL_BENCHMARK benchmark exists but benchmark_as_of_bar_date < feature date
```

## 2. Lineage propagation

### Problem

`candidate_score.lineage_json` expects provider and ingestion_run_id, but scoring currently reads `feature_snapshot` only and may not carry canonical lineage.

### Design

Propagate lineage forward:

```text
canonical_ohlcv
  selected_provider
  ingestion_run_id
  quality_status
  time
    ↓
feature_snapshot
  selected_provider
  ingestion_run_id
  source_quality_status
  as_of_bar_date
    ↓
candidate_score.lineage_json
  scoring_version
  feature_build_version
  feature_date
  as_of_bar_date
  selected_provider
  ingestion_run_id
  source_quality_status
  lineage_status
```

Allowed `lineage_status` values:

```text
COMPLETE
PARTIAL
MISSING_PROVIDER
MISSING_INGESTION_RUN
MISSING_FEATURE_SOURCE
```

If provider or ingestion_run_id cannot be populated, the system must not silently write null-only lineage. It must set an explicit lineage status and warning.

## 3. Historical quality lookup

### Problem

Quality lookup and `get_watchlist_rich()` can use the latest canonical quality row, which may be after the watchlist date.

### Design

Create a shared quality repository/service:

```text
vnalpha/quality/service.py
```

Required functions:

```text
get_symbol_quality_as_of(symbol, target_date)
get_many_quality_as_of(symbols, target_date)
get_watchlist_quality_as_of(watchlist_date)
get_rejected_records_as_of(symbol, target_date)
```

Rules:

```text
- symbol quality must choose latest canonical_ohlcv row where time <= target_date.
- watchlist quality must choose latest canonical_ohlcv row per symbol where time <= daily_watchlist.date.
- no quality view may default to latest overall row unless the caller asks for latest explicitly.
- rejected records must be attached when available.
```

## 4. Rejected symbol date semantics

### Problem

`rejected_symbol.date` may represent the job detection date instead of the affected data date.

### Design

Clarify and extend rejected-symbol schema:

```text
bar_date       DATE      # affected data/bar date
reported_date  DATE      # backward-compatible date or detection date if retained
detected_at    TIMESTAMPTZ
ingestion_run_id VARCHAR
provider       VARCHAR
```

Preferred semantic:

```text
rejected_symbol.date = bar_date
created_at/detected_at = detection timestamp
```

If backward compatibility requires keeping `date` as-is, add explicit `bar_date` and migrate all new writes to populate it.

## 5. Shared filter validation

### Problem

`/filter` validates fields in the command handler, while the underlying `watchlist.filter` tool can still receive arbitrary fields from assistant plans or future callers.

### Design

Move validation into a shared module:

```text
vnalpha/filters/validation.py
```

Required API:

```text
normalize_filter_key(key) -> canonical_key
validate_filter(field, operator, value) -> ValidatedFilter
validate_filters(filters) -> list[ValidatedFilter]
```

Allowed canonical fields:

```text
symbol
score
candidate_class
setup_type
rank
risk_flags
data_quality_status
```

Aliases:

```text
class -> candidate_class
setup -> setup_type
quality -> data_quality_status
```

All callers must use this validator:

```text
/filter command handler
watchlist.filter tool
assistant plan execution
future command/assistant tests
```

## 6. Multi-symbol quality support

### Problem

Assistant compare plan passes `symbols`, but the quality tool registry accepts only `symbol`.

### Design

Add one of the following:

Preferred:

```text
quality.get_many_status(symbols, date)
```

Alternative:

```text
AssistantExecutor expands symbols into repeated quality.get_status(symbol=...)
```

Preferred tool registry entries:

```text
quality.get_status       # one symbol or watchlist
quality.get_many_status  # many symbols
```

Both must use the shared historical quality service.

## 7. Assistant tool trace parent semantics

### Problem

Assistant traces may set both `session_id` and `assistant_session_id` to the assistant session id.

### Design

Enforce parent semantics:

```text
command tool trace:
  session_id = research_session_id
  assistant_session_id = NULL
  trace_parent_type = command

assistant tool trace:
  session_id = NULL
  assistant_session_id = assistant_session_id
  trace_parent_type = assistant
```

Add repository assertions or tests to reject ambiguous trace rows.

## 8. Remove or isolate direct tool-call fallback

### Problem

Some command handlers still fallback to direct tool implementation calls when `tool_executor` is absent.

### Design

Production handler paths must require a tool executor.

Allowed approaches:

```text
A. handler returns FAILED if tool_executor is missing.
B. registry injects a non-tracing test executor in explicit unit tests only.
```

Do not silently bypass permission checks and trace persistence.

## 9. Outcome evaluation versioning

### Problem

Outcome records are recomputed from mutable canonical data. Backfills can change historical outcome results without an evaluation run identifier or input snapshot metadata.

### Design

Add an outcome evaluation run table:

```text
outcome_evaluation_run
  evaluation_run_id      VARCHAR PRIMARY KEY
  started_at             TIMESTAMPTZ
  finished_at            TIMESTAMPTZ
  status                 VARCHAR
  watchlist_date_from     DATE
  watchlist_date_to       DATE
  horizons_json           VARCHAR
  evaluator_version       VARCHAR
  metric_policy_version   VARCHAR
  canonical_snapshot_json VARCHAR
  benchmark_snapshot_json VARCHAR
  result_summary_json     VARCHAR
  error_json              VARCHAR
```

Extend outcome tables:

```text
candidate_outcome.evaluation_run_id
candidate_outcome.evaluator_version
candidate_outcome.metric_policy_version
candidate_outcome.symbol_data_max_time
candidate_outcome.benchmark_data_max_time
watchlist_outcome.evaluation_run_id
score_bucket_performance.evaluation_run_id
setup_type_performance.evaluation_run_id
risk_flag_performance.evaluation_run_id
```

## 10. Outcome metric policy

### Problem

Max gain/drawdown currently use close-only windows. That is valid for MVP only if explicitly labeled.

### Design

Introduce metric policy:

```text
CLOSE_ONLY_V1
OHLC_HIGH_LOW_V1
```

Default recommendation:

```text
OHLC_HIGH_LOW_V1 for max_gain and max_drawdown when high/low are available.
CLOSE_ONLY_V1 only when explicitly configured or high/low is unavailable.
```

Persist `metric_policy_version` on outcome records.

## 11. Vietnam trading-calendar date resolver

### Problem

`resolve_date(None)` uses system local date and does not account for Vietnamese market calendar or data availability.

### Design

Add:

```text
vnalpha/calendar/trading_calendar.py
```

Required behavior:

```text
resolve_research_date(value, conn=None, market='VN')
```

Rules:

```text
- explicit ISO date returns that date after validation.
- today resolves using Asia/Ho_Chi_Minh timezone.
- if today has no available canonical bar/watchlist context, resolve to latest trading/data date <= today when used for research commands.
- CLI must allow explicit --date to override.
```

## 12. Tests

Add tests for each finding:

```text
feature actual_bar_date is preserved
stale feature date is marked STALE_DATE
candidate lineage includes provider/ingestion or explicit lineage_status
historical watchlist quality uses time <= watchlist date
quality.get_status(symbol, date) does not return future quality rows
rejected_symbol stores affected bar_date
filter validation rejects unknown fields at tool level
assistant compare calls quality for every symbol
assistant traces use assistant_session_id only
command handlers do not bypass tool executor in production
outcome evaluation run metadata is persisted
outcome metric policy is persisted
trading-calendar resolver handles weekend/no-data dates
```
