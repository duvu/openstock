# Specification: Research Consistency, Data Drift, and Accuracy

## ADDED Requirements

### Requirement: Feature snapshots shall preserve actual source bar date

`vnalpha` SHALL store the actual canonical OHLCV bar date used to build each feature snapshot.

Feature snapshots SHALL distinguish the requested feature date from the actual source data date.

Required metadata:

```text
as_of_bar_date
benchmark_as_of_bar_date
source_row_count
benchmark_row_count
feature_data_status
feature_build_version
feature_generated_at
```

Allowed `feature_data_status` values SHALL include:

```text
EXACT_DATE
STALE_DATE
MISSING_BENCHMARK
PARTIAL_BENCHMARK
INSUFFICIENT_HISTORY
MISSING_CANONICAL
```

#### Scenario: Exact-date feature snapshot

- **GIVEN** target date is `2026-07-06`
- **AND** the symbol has canonical OHLCV for `2026-07-06`
- **WHEN** features are built
- **THEN** `feature_snapshot.date` SHALL be `2026-07-06`
- **AND** `as_of_bar_date` SHALL be `2026-07-06`
- **AND** `feature_data_status` SHALL be `EXACT_DATE`.

#### Scenario: Stale-date feature snapshot

- **GIVEN** target date is `2026-07-06`
- **AND** the latest available symbol bar is `2026-07-03`
- **WHEN** features are built using that latest available row
- **THEN** `feature_snapshot.date` SHALL remain `2026-07-06`
- **AND** `as_of_bar_date` SHALL be `2026-07-03`
- **AND** `feature_data_status` SHALL be `STALE_DATE`.

---

### Requirement: Candidate score lineage shall be complete or explicitly partial

`candidate_score.lineage_json` SHALL include source lineage propagated from canonical OHLCV and feature snapshot.

Required lineage fields:

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

Allowed `lineage_status` values SHALL include:

```text
COMPLETE
PARTIAL
MISSING_PROVIDER
MISSING_INGESTION_RUN
MISSING_FEATURE_SOURCE
```

The system SHALL NOT silently write null-only provider or ingestion lineage.

#### Scenario: Complete lineage

- **GIVEN** canonical OHLCV has selected provider and ingestion run id
- **WHEN** features and scores are generated
- **THEN** candidate score lineage SHALL include selected provider and ingestion run id
- **AND** `lineage_status` SHALL be `COMPLETE`.

#### Scenario: Missing ingestion lineage

- **GIVEN** canonical OHLCV lacks ingestion run id
- **WHEN** candidate score is saved
- **THEN** lineage SHALL include `lineage_status = MISSING_INGESTION_RUN`
- **AND** the missing lineage SHALL be visible in explain/lineage outputs.

---

### Requirement: Historical quality lookup shall be as-of-date aware

Quality lookup SHALL use the requested target date instead of blindly using the latest available canonical row.

For target date `D`, symbol quality SHALL use the latest canonical OHLCV row satisfying:

```text
time <= D
```

Watchlist quality SHALL use each watchlist row's date as the target date.

#### Scenario: Historical watchlist quality does not use future row

- **GIVEN** a watchlist exists for `2026-07-06`
- **AND** canonical quality for FPT changes on `2026-07-10`
- **WHEN** the user reviews watchlist quality for `2026-07-06`
- **THEN** the quality status SHALL come from canonical data at or before `2026-07-06`
- **AND** the `2026-07-10` row SHALL NOT affect the historical result.

#### Scenario: Symbol quality honors date

- **GIVEN** the user asks `/quality FPT --date 2026-07-06`
- **WHEN** the quality tool runs
- **THEN** it SHALL return FPT quality as of `2026-07-06`
- **AND** not the latest overall FPT quality row.

---

### Requirement: Quality output shall include rejected data records

Symbol-level quality output SHALL include rejected data records when available.

Rejected data records SHALL distinguish affected data date from detection timestamp.

Required semantics:

```text
bar_date or equivalent = affected data/bar date
detected_at or created_at = detection timestamp
```

#### Scenario: Rejected OHLCV is visible in quality output

- **GIVEN** FPT has a rejected canonical OHLCV record for `2026-07-06`
- **WHEN** the user asks `/quality FPT --date 2026-07-06`
- **THEN** the quality output SHALL include the rejected record
- **AND** the record SHALL identify the affected bar date and reason.

---

### Requirement: Filter validation shall be enforced at tool level

Filter validation SHALL be shared across CLI, TUI, assistant, and tool calls.

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

Allowed aliases:

```text
class -> candidate_class
setup -> setup_type
quality -> data_quality_status
```

The `watchlist.filter` tool SHALL reject unsupported fields even when invoked directly by the assistant.

#### Scenario: Unsupported filter field is rejected by tool

- **GIVEN** assistant plan calls `watchlist.filter` with field `raw_sql`
- **WHEN** the tool executes
- **THEN** the tool SHALL fail validation
- **AND** no filtering result SHALL be returned.

#### Scenario: Malformed numeric comparison is rejected consistently

- **GIVEN** the user enters `/filter score>>0.70`
- **WHEN** parsing and validation run
- **THEN** the command SHALL fail validation
- **AND** no tool SHALL execute.

---

### Requirement: Assistant compare workflow shall retrieve quality for each symbol

The assistant compare workflow SHALL retrieve data quality for every compared symbol.

It SHALL either:

```text
- call quality.get_many_status(symbols, date), or
- expand the quality step into one quality.get_status call per symbol.
```

#### Scenario: Compare three symbols retrieves three quality states

- **GIVEN** the user asks `Compare FPT, VNM, and MWG`
- **WHEN** the assistant executes the compare plan
- **THEN** the tool trace SHALL show quality lookup for FPT, VNM, and MWG
- **AND** the final answer SHALL include quality caveats for each symbol when available.

---

### Requirement: Tool traces shall have unambiguous parent sessions

Tool traces SHALL identify exactly one parent context.

For command-originated tool calls:

```text
session_id = research_session_id
assistant_session_id = NULL
trace_parent_type = command
```

For assistant-originated tool calls:

```text
session_id = NULL
assistant_session_id = assistant_session_id
trace_parent_type = assistant
```

#### Scenario: Assistant trace has assistant parent only

- **GIVEN** an assistant prompt executes `candidate.explain`
- **WHEN** the tool_trace row is written
- **THEN** `assistant_session_id` SHALL be populated
- **AND** `session_id` SHALL be null
- **AND** `trace_parent_type` SHALL be `assistant`.

#### Scenario: Command trace has research session parent only

- **GIVEN** `vnalpha cmd "/scan"` executes `watchlist.scan`
- **WHEN** the tool_trace row is written
- **THEN** `session_id` SHALL be populated
- **AND** `assistant_session_id` SHALL be null
- **AND** `trace_parent_type` SHALL be `command`.

---

### Requirement: Production command handlers shall not bypass traced tool execution

Production command handlers SHALL require the traced tool execution path.

Handlers SHALL NOT silently import and call tool implementations directly when `tool_executor` is missing.

#### Scenario: Missing tool executor fails closed

- **GIVEN** a production command handler is invoked without a tool executor
- **WHEN** it attempts to execute a local tool
- **THEN** it SHALL fail with a clear command error
- **AND** it SHALL NOT call the tool implementation directly.

---

### Requirement: Outcome evaluation shall create a versioned evaluation run

Every outcome evaluation SHALL create an `outcome_evaluation_run` record.

The evaluation run SHALL include:

```text
evaluation_run_id
started_at
finished_at
status
watchlist_date_from
watchlist_date_to
horizons_json
evaluator_version
metric_policy_version
canonical_snapshot_json
benchmark_snapshot_json
result_summary_json
error_json
```

Candidate and aggregate outcome records SHALL reference `evaluation_run_id`.

#### Scenario: Single-date evaluation creates run

- **GIVEN** a watchlist exists for `2026-07-06`
- **WHEN** the user runs `vnalpha outcome evaluate --date 2026-07-06`
- **THEN** one outcome evaluation run SHALL be created
- **AND** all candidate and aggregate outcomes created in that execution SHALL reference the run id.

#### Scenario: Re-evaluation is auditable

- **GIVEN** outcome evaluation is run twice after canonical data has changed
- **WHEN** the user inspects the outcome records
- **THEN** the records SHALL show which evaluation run and snapshot metadata generated each result.

---

### Requirement: Outcome max gain and max drawdown policy shall be explicit

Outcome evaluation SHALL use an explicit metric policy.

Allowed initial policies:

```text
CLOSE_ONLY_V1
OHLC_HIGH_LOW_V1
```

If `OHLC_HIGH_LOW_V1` is active:

```text
max_gain = max(high / entry_close - 1)
max_drawdown = min(low / entry_close - 1)
```

If `CLOSE_ONLY_V1` is active:

```text
max_gain_close_only = max(close / entry_close - 1)
max_drawdown_close_only = min(close / entry_close - 1)
```

Metric policy SHALL be persisted with outcome records.

#### Scenario: High-low policy uses high and low

- **GIVEN** entry close is 100
- **AND** forward window has high 112 and low 94
- **WHEN** metric policy is `OHLC_HIGH_LOW_V1`
- **THEN** max gain SHALL be 0.12
- **AND** max drawdown SHALL be -0.06.

---

### Requirement: Research date resolution shall be Vietnam trading-calendar aware

Research date resolution SHALL use Vietnam market timezone and data availability.

Rules:

```text
- explicit ISO date SHALL be preserved after validation.
- `today` and missing date SHALL resolve using Asia/Ho_Chi_Minh timezone.
- for research workflows, if today has no data, the resolver SHALL use the latest available data date at or before today when a database context is available.
```

#### Scenario: Weekend date resolves to latest available research date

- **GIVEN** today is a weekend in Vietnam
- **AND** latest canonical/watchlist date is the preceding Friday
- **WHEN** the user runs a research command without explicit date
- **THEN** the command SHALL use the preceding Friday as research date
- **AND** the resolved date SHALL be visible in the output or trace.

#### Scenario: Explicit date is preserved

- **GIVEN** the user passes `--date 2026-07-04`
- **WHEN** the resolver runs
- **THEN** it SHALL preserve `2026-07-04` after validation
- **AND** it SHALL not silently change the explicit date.

---

### Requirement: Drift and accuracy fixes shall be covered by regression tests

The system SHALL include targeted tests preventing recurrence of the reviewed findings.

Required test groups:

```text
feature as-of-date tests
lineage propagation tests
historical quality tests
rejected-symbol date semantics tests
tool-level filter validation tests
assistant compare quality tests
tool trace parent tests
no direct production tool fallback tests
outcome evaluation run/version tests
metric policy tests
trading calendar resolver tests
```

#### Scenario: Full regression suite passes

- **GIVEN** the fixes are implemented
- **WHEN** `cd vnalpha && pytest -q` runs
- **THEN** all Phase 5, 5.8, 5.9, and 6 regression tests SHALL pass.
