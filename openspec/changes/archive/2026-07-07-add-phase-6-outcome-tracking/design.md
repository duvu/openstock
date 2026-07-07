# Design: Phase 6 Outcome Tracking and Feedback Loop

## Context

Phase 5 creates deterministic candidates and a daily watchlist. Phase 6 evaluates those candidates after fixed forward horizons.

The pipeline becomes:

```text
daily_watchlist
→ outcome evaluator
→ candidate_outcome
→ aggregate performance tables
→ calibration report
→ CLI/TUI outcome review
```

Outcome tracking must be deterministic, reproducible, and grounded in `canonical_ohlcv` plus persisted Phase 5 artifacts.

## Design principles

### Retrospective evaluation only

Outcome tracking measures what happened after a candidate was selected. It must not produce buy/sell instructions.

### Use persisted watchlists as the source of truth

The evaluator should evaluate what the system actually selected, not recompute historical watchlists from today's code.

### Avoid look-ahead leakage

For a watchlist date `D`, only OHLCV bars after `D` may be used for forward outcomes. Feature and score values must come from persisted `candidate_score` and `daily_watchlist` at `D`.

### Handle incomplete horizons explicitly

If the future window is not complete, the evaluator must mark the outcome as pending or partial instead of fabricating results.

### Benchmark-relative by default

Every candidate outcome should include raw forward return and excess return versus VNINDEX where benchmark data exists.

## Proposed module layout

```text
vnalpha/src/vnalpha/outcomes/
├── __init__.py
├── models.py
├── evaluator.py
├── horizons.py
├── metrics.py
├── aggregations.py
├── calibration.py
├── repositories.py
├── renderers.py
└── errors.py

vnalpha/src/vnalpha/tui/screens/outcomes.py
```

## Data model

### `candidate_outcome`

One row per candidate, watchlist date, and horizon.

Suggested fields:

```text
symbol                     VARCHAR NOT NULL
watchlist_date             DATE NOT NULL
horizon_sessions           INTEGER NOT NULL
rank                       INTEGER
score                      DOUBLE
candidate_class            VARCHAR
setup_type                 VARCHAR
risk_flags_json            VARCHAR
entry_close                DOUBLE
exit_close                 DOUBLE
benchmark_entry_close      DOUBLE
benchmark_exit_close       DOUBLE
forward_return             DOUBLE
benchmark_return           DOUBLE
excess_return_vs_vnindex   DOUBLE
max_gain                   DOUBLE
max_drawdown               DOUBLE
hit                        BOOLEAN
failure                    BOOLEAN
outcome_status             VARCHAR NOT NULL  # COMPLETE | PENDING | PARTIAL | MISSING_DATA | ERROR
bars_available             INTEGER
required_bars              INTEGER
computed_at                TIMESTAMPTZ
error_json                 VARCHAR
PRIMARY KEY (symbol, watchlist_date, horizon_sessions)
```

### `watchlist_outcome`

Aggregate outcome for one watchlist date and horizon.

Suggested fields:

```text
watchlist_date             DATE NOT NULL
horizon_sessions           INTEGER NOT NULL
candidate_count            INTEGER
complete_count             INTEGER
pending_count              INTEGER
missing_data_count         INTEGER
avg_forward_return         DOUBLE
median_forward_return      DOUBLE
avg_excess_return          DOUBLE
median_excess_return       DOUBLE
avg_max_gain               DOUBLE
avg_max_drawdown           DOUBLE
hit_rate                   DOUBLE
failure_rate               DOUBLE
computed_at                TIMESTAMPTZ
PRIMARY KEY (watchlist_date, horizon_sessions)
```

### `score_bucket_performance`

Aggregate performance by score bucket and horizon.

Suggested fields:

```text
as_of_date                 DATE NOT NULL
horizon_sessions           INTEGER NOT NULL
score_bucket               VARCHAR NOT NULL
candidate_count            INTEGER
avg_forward_return         DOUBLE
median_forward_return      DOUBLE
avg_excess_return          DOUBLE
hit_rate                   DOUBLE
failure_rate               DOUBLE
avg_max_drawdown           DOUBLE
computed_at                TIMESTAMPTZ
PRIMARY KEY (as_of_date, horizon_sessions, score_bucket)
```

Suggested buckets:

```text
0.00-0.40
0.40-0.50
0.50-0.60
0.60-0.70
0.70-0.80
0.80-0.90
0.90-1.00
```

### `setup_type_performance`

Aggregate performance by setup type and horizon.

Suggested fields:

```text
as_of_date                 DATE NOT NULL
horizon_sessions           INTEGER NOT NULL
setup_type                 VARCHAR NOT NULL
candidate_count            INTEGER
avg_forward_return         DOUBLE
median_forward_return      DOUBLE
avg_excess_return          DOUBLE
hit_rate                   DOUBLE
failure_rate               DOUBLE
avg_max_drawdown           DOUBLE
computed_at                TIMESTAMPTZ
PRIMARY KEY (as_of_date, horizon_sessions, setup_type)
```

### `risk_flag_performance`

Aggregate performance by risk flag and horizon.

Suggested fields:

```text
as_of_date                 DATE NOT NULL
horizon_sessions           INTEGER NOT NULL
risk_flag                  VARCHAR NOT NULL
candidate_count            INTEGER
avg_forward_return         DOUBLE
median_forward_return      DOUBLE
avg_excess_return          DOUBLE
hit_rate                   DOUBLE
failure_rate               DOUBLE
avg_max_drawdown           DOUBLE
computed_at                TIMESTAMPTZ
PRIMARY KEY (as_of_date, horizon_sessions, risk_flag)
```

## Horizon model

Default horizons:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

A horizon is measured in available trading bars from `canonical_ohlcv`, not calendar days.

For a symbol and watchlist date `D`:

```text
entry_close = close on D, or latest close <= D if exact D missing and policy allows.
exit_close = close at the Nth available trading bar after D.
window = bars after D through exit bar, inclusive.
```

Recommended MVP policy:

```text
- require an entry close at or before watchlist_date.
- require at least N future bars for COMPLETE.
- mark PENDING if future bars are not yet available.
- mark MISSING_DATA if entry or benchmark data is absent.
```

## Metrics

### Candidate metrics

```text
forward_return = exit_close / entry_close - 1
benchmark_return = benchmark_exit_close / benchmark_entry_close - 1
excess_return_vs_vnindex = forward_return - benchmark_return
max_gain = max(high_or_close_in_window / entry_close - 1)
max_drawdown = min(low_or_close_in_window / entry_close - 1)
```

MVP can use close-only window metrics if high/low quality is unreliable:

```text
max_gain_close_only = max(close / entry_close - 1)
max_drawdown_close_only = min(close / entry_close - 1)
```

### Hit and failure rules

Initial default thresholds:

```text
hit = excess_return_vs_vnindex > 0
failure = forward_return < 0 and excess_return_vs_vnindex < 0
```

Thresholds should be configurable later.

## Evaluator flow

```text
1. Select daily_watchlist rows for target watchlist dates.
2. Join candidate_score for score, class, setup, risk flags, and lineage.
3. For each candidate and horizon:
   3.1 locate entry close.
   3.2 locate exit close after N future bars.
   3.3 locate VNINDEX entry/exit close.
   3.4 calculate forward and benchmark-relative metrics.
   3.5 calculate max gain/drawdown.
   3.6 mark outcome status.
   3.7 upsert candidate_outcome.
4. Aggregate into watchlist_outcome.
5. Aggregate into score_bucket_performance.
6. Aggregate into setup_type_performance.
7. Aggregate into risk_flag_performance.
```

## CLI integration

Add commands:

```bash
vnalpha outcome evaluate --date 2026-07-06
vnalpha outcome evaluate --from 2026-01-01 --to 2026-06-30
vnalpha outcome candidates --date 2026-07-06 --horizon 20
vnalpha outcome watchlist --date 2026-07-06 --horizon 20
vnalpha outcome buckets --horizon 20
vnalpha outcome setups --horizon 20
vnalpha outcome risks --horizon 20
vnalpha outcome report --horizon 20
```

## TUI integration

Add an Outcome Review screen.

Minimum panels:

```text
Watchlist outcome summary
Candidate outcome table
Score bucket performance
Setup type performance
Risk flag performance
Pending/missing data panel
```

Minimum navigation:

```text
from watchlist date → outcome detail
from candidate → symbol detail
from score bucket/setup/risk aggregate → filtered candidates
```

## Calibration report

The calibration report should answer:

```text
Are higher scores associated with better outcomes?
Which candidate classes work best?
Which setup types are weak?
Which risk flags correlate with poor outcomes?
Are there many pending or missing outcomes?
```

The report should be deterministic and generated from aggregate tables, not an AI-only narrative.

## Missing data and pending outcomes

Outcome status values:

```text
COMPLETE
PENDING
PARTIAL
MISSING_DATA
ERROR
```

Examples:

```text
PENDING       horizon not yet complete
MISSING_DATA  symbol or benchmark close is unavailable
PARTIAL       candidate data exists but benchmark data is incomplete
ERROR         evaluator error captured with error_json
```

## Testing strategy

### Unit tests

```text
horizon bar selection
entry/exit close selection
forward return calculation
benchmark return calculation
excess return calculation
max gain/drawdown calculation
hit/failure classification
score bucket assignment
risk flag expansion
missing data status
pending horizon status
```

### Integration tests

Use fixture OHLCV and fixture watchlists:

```text
migrations create outcome tables
candidate_outcome is produced for complete horizons
PENDING is produced for incomplete horizons
MISSING_DATA is produced for absent benchmark/symbol data
watchlist_outcome aggregates candidate outcomes
score_bucket_performance aggregates by score range
setup_type_performance aggregates by setup type
risk_flag_performance aggregates by risk flag
```

### Regression tests

Phase 6 must not break:

```text
Phase 5 pipeline fixture tests
Phase 5.8 command-layer tests
Phase 5.9 assistant tests if present
```

## Safety boundaries

Outcome views must use research/evaluation language only.

Forbidden output terms in outcome code/docs/tests:

```text
buy signal
sell signal
place order
execute order
portfolio action
investment advice
```

Allowed output terms:

```text
candidate outcome
forward return
excess return
hit rate
failure rate
setup performance
risk flag performance
calibration
```

## Compatibility

Phase 6 is additive.

It must not change existing Phase 5 tables:

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

It adds outcome tables and commands without changing watchlist generation.
