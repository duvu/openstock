# Specification: Outcome Tracking and Feedback Loop

## ADDED Requirements

### Requirement: Outcome tracking shall evaluate persisted watchlist candidates

`vnalpha` SHALL evaluate outcomes from persisted `daily_watchlist` rows.

The evaluator SHALL use the watchlist rows that were actually generated on the watchlist date. It SHALL NOT recompute historical watchlists from current scoring rules.

#### Scenario: Evaluate persisted watchlist

- **GIVEN** `daily_watchlist` contains candidates for `2026-07-06`
- **WHEN** the evaluator runs for `2026-07-06`
- **THEN** it SHALL evaluate those persisted candidates
- **AND** it SHALL not regenerate the watchlist using current scoring code

#### Scenario: No watchlist exists

- **GIVEN** no `daily_watchlist` rows exist for `2026-07-06`
- **WHEN** the evaluator runs for that date
- **THEN** it SHALL return a clear no-data result
- **AND** it SHALL not fabricate candidate outcomes

---

### Requirement: Candidate outcomes shall be persisted by horizon

`vnalpha` SHALL persist candidate outcomes for fixed forward horizons.

Default horizons SHALL be:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

Each candidate outcome SHALL be keyed by:

```text
symbol
watchlist_date
horizon_sessions
```

#### Scenario: Persist 20-session candidate outcome

- **GIVEN** FPT appears in `daily_watchlist` on `2026-07-06`
- **AND** at least 20 future bars exist in `canonical_ohlcv`
- **WHEN** outcome evaluation runs for horizon 20
- **THEN** a `candidate_outcome` row SHALL be persisted for FPT, `2026-07-06`, horizon 20
- **AND** status SHALL be `COMPLETE`

#### Scenario: Pending horizon

- **GIVEN** FPT appears in `daily_watchlist` on `2026-07-06`
- **AND** fewer than 20 future bars exist
- **WHEN** outcome evaluation runs for horizon 20
- **THEN** a `candidate_outcome` row SHALL be persisted or updated with status `PENDING`
- **AND** bars_available and required_bars SHALL be recorded

---

### Requirement: Outcome evaluator shall calculate forward return

For each complete candidate outcome, the evaluator SHALL calculate:

```text
forward_return = exit_close / entry_close - 1
```

The entry close SHALL be the close at the watchlist date, or latest close at or before the watchlist date if policy allows.

The exit close SHALL be the close at the Nth available trading bar after the watchlist date.

#### Scenario: Calculate forward return

- **GIVEN** entry_close is 100
- **AND** 20-session exit_close is 110
- **WHEN** the evaluator calculates forward_return
- **THEN** forward_return SHALL equal 0.10

#### Scenario: Missing entry close

- **GIVEN** no valid entry close exists for FPT on or before the watchlist date
- **WHEN** outcome evaluation runs
- **THEN** candidate outcome status SHALL be `MISSING_DATA`
- **AND** forward_return SHALL not be fabricated

---

### Requirement: Outcome evaluator shall calculate benchmark-relative return

For each complete candidate outcome, the evaluator SHALL calculate benchmark return versus VNINDEX when benchmark data exists.

```text
benchmark_return = benchmark_exit_close / benchmark_entry_close - 1
excess_return_vs_vnindex = forward_return - benchmark_return
```

#### Scenario: Calculate excess return

- **GIVEN** candidate forward_return is 0.10
- **AND** VNINDEX benchmark_return is 0.03
- **WHEN** the evaluator calculates excess return
- **THEN** excess_return_vs_vnindex SHALL equal 0.07

#### Scenario: Missing benchmark data

- **GIVEN** candidate data is complete
- **AND** VNINDEX benchmark data is missing
- **WHEN** evaluation runs
- **THEN** candidate outcome SHALL keep raw forward_return where possible
- **AND** benchmark_return and excess_return_vs_vnindex SHALL be null
- **AND** outcome status SHALL be `PARTIAL` or `MISSING_DATA` according to policy

---

### Requirement: Outcome evaluator shall calculate max gain and max drawdown

For each complete candidate outcome, the evaluator SHALL calculate max gain and max drawdown over the forward window.

MVP may use close-only metrics if high/low quality is not reliable.

```text
max_gain = max(window_price / entry_close - 1)
max_drawdown = min(window_price / entry_close - 1)
```

#### Scenario: Calculate max gain and drawdown

- **GIVEN** entry_close is 100
- **AND** forward window closes are 102, 95, 108, 104
- **WHEN** outcome metrics are calculated
- **THEN** max_gain SHALL equal 0.08
- **AND** max_drawdown SHALL equal -0.05

---

### Requirement: Outcome evaluator shall classify hit and failure

Candidate outcomes SHALL include hit and failure flags.

Default MVP rules:

```text
hit = excess_return_vs_vnindex > 0
failure = forward_return < 0 and excess_return_vs_vnindex < 0
```

#### Scenario: Candidate is hit

- **GIVEN** excess_return_vs_vnindex is 0.04
- **WHEN** hit/failure rules run
- **THEN** hit SHALL be true

#### Scenario: Candidate is failure

- **GIVEN** forward_return is -0.03
- **AND** excess_return_vs_vnindex is -0.02
- **WHEN** hit/failure rules run
- **THEN** failure SHALL be true

---

### Requirement: Watchlist outcomes shall aggregate candidate outcomes

`vnalpha` SHALL aggregate candidate outcomes by watchlist date and horizon into `watchlist_outcome`.

Aggregates SHALL include:

```text
candidate_count
complete_count
pending_count
missing_data_count
avg_forward_return
median_forward_return
avg_excess_return
median_excess_return
avg_max_gain
avg_max_drawdown
hit_rate
failure_rate
```

#### Scenario: Aggregate watchlist outcome

- **GIVEN** candidate outcomes exist for `2026-07-06` and horizon 20
- **WHEN** watchlist aggregation runs
- **THEN** a `watchlist_outcome` row SHALL be persisted
- **AND** it SHALL include complete, pending, and missing-data counts

---

### Requirement: Score bucket performance shall aggregate outcomes by score bucket

`vnalpha` SHALL aggregate complete candidate outcomes by score bucket and horizon.

Default buckets SHALL include:

```text
0.00-0.40
0.40-0.50
0.50-0.60
0.60-0.70
0.70-0.80
0.80-0.90
0.90-1.00
```

#### Scenario: Aggregate score bucket performance

- **GIVEN** complete candidate outcomes exist across score ranges
- **WHEN** score bucket aggregation runs
- **THEN** `score_bucket_performance` rows SHALL be persisted
- **AND** each row SHALL include candidate_count, average/median returns, hit rate, failure rate, and average drawdown

#### Scenario: Empty score bucket

- **GIVEN** no complete outcomes exist in bucket `0.90-1.00`
- **WHEN** aggregation runs
- **THEN** the system MAY omit the bucket or persist zero-count data
- **AND** it SHALL not fabricate performance metrics

---

### Requirement: Setup type performance shall aggregate outcomes by setup type

`vnalpha` SHALL aggregate complete candidate outcomes by setup type and horizon.

#### Scenario: Aggregate setup performance

- **GIVEN** complete outcomes exist for `ACCUMULATION_BASE` and `BREAKOUT_ATTEMPT`
- **WHEN** setup aggregation runs
- **THEN** `setup_type_performance` rows SHALL be persisted
- **AND** each row SHALL include candidate_count, average/median returns, hit rate, failure rate, and average drawdown

---

### Requirement: Risk flag performance shall aggregate outcomes by risk flag

`vnalpha` SHALL expand persisted `risk_flags_json` and aggregate complete candidate outcomes by risk flag and horizon.

#### Scenario: Aggregate risk flag performance

- **GIVEN** candidate outcomes include risk flag `THIN_VOLUME`
- **WHEN** risk flag aggregation runs
- **THEN** `risk_flag_performance` SHALL include a row for `THIN_VOLUME`
- **AND** the row SHALL summarize realized performance for candidates carrying that flag

#### Scenario: Candidate has multiple risk flags

- **GIVEN** one candidate has risk flags `THIN_VOLUME` and `WEAK_RS`
- **WHEN** risk flag aggregation runs
- **THEN** the candidate SHALL contribute to both risk flag aggregates

---

### Requirement: Outcome commands shall expose evaluation and review surfaces

`vnalpha` SHALL expose CLI commands for outcome evaluation and review.

Required commands:

```bash
vnalpha outcome evaluate --date <date>
vnalpha outcome evaluate --from <date> --to <date>
vnalpha outcome candidates --date <date> --horizon <n>
vnalpha outcome watchlist --date <date> --horizon <n>
vnalpha outcome buckets --horizon <n>
vnalpha outcome setups --horizon <n>
vnalpha outcome risks --horizon <n>
vnalpha outcome report --horizon <n>
```

#### Scenario: Evaluate one watchlist date

- **GIVEN** a watchlist exists for `2026-07-06`
- **WHEN** the user runs `vnalpha outcome evaluate --date 2026-07-06`
- **THEN** candidate and aggregate outcomes SHALL be generated for configured horizons

#### Scenario: Show candidate outcomes

- **GIVEN** candidate outcomes exist for `2026-07-06` horizon 20
- **WHEN** the user runs `vnalpha outcome candidates --date 2026-07-06 --horizon 20`
- **THEN** the CLI SHALL render candidate outcome rows

---

### Requirement: TUI shall expose Outcome Review screen

The TUI SHALL provide an Outcome Review screen.

The screen SHALL include:

```text
watchlist outcome summary
candidate outcome table
score bucket performance
setup type performance
risk flag performance
pending/missing data panel
```

#### Scenario: Open outcome review

- **GIVEN** outcome data exists
- **WHEN** the user opens Outcome Review in TUI
- **THEN** the TUI SHALL show aggregate and candidate-level outcome metrics

#### Scenario: Outcome screen handles no data

- **GIVEN** no outcome data exists
- **WHEN** the user opens Outcome Review
- **THEN** the TUI SHALL show a no-data message
- **AND** the TUI SHALL remain usable

---

### Requirement: Calibration report shall summarize feedback loop quality

`vnalpha` SHALL produce a deterministic calibration report from aggregate outcome tables.

The report SHALL answer:

```text
Are higher score buckets associated with better outcomes?
Which candidate classes work best?
Which setup types are weak?
Which risk flags correlate with poor outcomes?
How much data is pending or missing?
```

#### Scenario: Generate calibration report

- **GIVEN** aggregate outcome tables exist for horizon 20
- **WHEN** the user runs `vnalpha outcome report --horizon 20`
- **THEN** the report SHALL summarize score bucket, setup type, and risk flag performance
- **AND** it SHALL include pending and missing-data counts

---

### Requirement: Outcome tracking shall preserve research-only boundary

Outcome tracking SHALL remain retrospective research evaluation.

It SHALL NOT:

```text
- place orders
- connect to broker execution APIs
- manage accounts
- manage portfolios
- produce buy/sell instructions
- guarantee future performance
- mutate scoring rules automatically
```

#### Scenario: Outcome report uses research language

- **GIVEN** an outcome report is rendered
- **WHEN** the user reads it
- **THEN** it SHALL use research/evaluation terms such as `forward return`, `hit rate`, `failure rate`, and `calibration`
- **AND** it SHALL not use order execution or portfolio action terms

#### Scenario: Outcome tracking does not mutate scoring

- **GIVEN** weak setup performance is detected
- **WHEN** calibration report is generated
- **THEN** the system MAY flag the setup type for review
- **BUT** it SHALL NOT automatically change scoring weights or candidate class thresholds

---

### Requirement: Phase 6 shall not break Phase 5 artifacts

Phase 6 SHALL be additive and SHALL NOT alter Phase 5 table semantics.

Existing Phase 5 tables SHALL remain compatible:

```text
ingestion_run
symbol_master
market_ohlcv_raw
canonical_ohlcv
feature_snapshot
candidate_score
daily_watchlist
rejected_symbol
```

#### Scenario: Phase 5 E2E still passes

- **GIVEN** Phase 6 outcome tables and commands are added
- **WHEN** Phase 5 E2E fixture tests run
- **THEN** they SHALL pass without requiring outcome data
