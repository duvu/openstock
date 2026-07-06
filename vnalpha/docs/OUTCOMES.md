# Phase 6: Outcome Tracking and Feedback Loop

## Overview

Phase 6 evaluates whether Phase 5 candidates performed well after selection. It measures realized outcomes against fixed forward horizons and aggregates performance by score bucket, candidate class, setup type, and risk flag.

This module is retrospective research evaluation only. It does not produce buy/sell instructions, connect to brokers, manage accounts, or guarantee future performance.

## Outcome Tables

| Table | Description |
|---|---|
| `candidate_outcome` | One row per symbol, watchlist date, and horizon |
| `watchlist_outcome` | Aggregate outcome per watchlist date and horizon |
| `score_bucket_performance` | Aggregated by score bucket and horizon |
| `setup_type_performance` | Aggregated by setup type and horizon |
| `risk_flag_performance` | Aggregated by risk flag and horizon |

## Horizon Definitions

Horizons are measured in available trading bars from `canonical_ohlcv`, not calendar days.

Default horizons: **5, 10, 20, 60 sessions**

For each candidate on watchlist date `D`:
- **Entry close**: close at `D`, or latest close at or before `D`
- **Exit close**: close at the Nth available bar after `D`
- **Forward window**: bars from `D+1` through the exit bar (inclusive)

## Outcome Status Values

| Status | Meaning |
|---|---|
| `COMPLETE` | Entry and exit closes found; all metrics calculated |
| `PENDING` | Not enough future bars yet |
| `PARTIAL` | Candidate data OK but benchmark data is incomplete |
| `MISSING_DATA` | Entry or benchmark close is absent |
| `ERROR` | Evaluator error; see `error_json` |

## Forward Return and Excess Return Formulas

```text
forward_return = exit_close / entry_close - 1

benchmark_return = benchmark_exit_close / benchmark_entry_close - 1

excess_return_vs_vnindex = forward_return - benchmark_return
```

**Benchmark**: VNINDEX (`canonical_ohlcv` where `symbol = 'VNINDEX'`)

## Max Gain and Max Drawdown

Calculated over the forward window using the active metric policy (see [Metric Policy](#metric-policy)).

**CLOSE_ONLY_V1** (default):

```text
max_gain = max(window_close / entry_close - 1)

max_drawdown = min(window_close / entry_close - 1)
```

**OHLC_HIGH_LOW_V1**:

```text
max_gain = max(window_high / entry_close - 1)

max_drawdown = min(window_low / entry_close - 1)
```

Max drawdown is typically negative (e.g., -0.05 = 5% loss).

## Hit and Failure Rules

Default classification:

```text
hit     = excess_return_vs_vnindex > 0
failure = forward_return < 0 AND excess_return_vs_vnindex < 0
```

Both are `null` when benchmark data is unavailable.

## CLI Outcome Commands

### Evaluate outcomes

```bash
# Single date
vnalpha outcome evaluate --date 2026-07-06

# Date range
vnalpha outcome evaluate --from 2026-01-01 --to 2026-06-30
```

### Review results

```bash
# Candidate outcomes for a date and horizon
vnalpha outcome candidates --date 2026-07-06 --horizon 20

# Watchlist aggregate summary
vnalpha outcome watchlist --date 2026-07-06 --horizon 20

# Score bucket performance
vnalpha outcome buckets --horizon 20

# Setup type performance
vnalpha outcome setups --horizon 20

# Risk flag performance
vnalpha outcome risks --horizon 20

# Calibration report
vnalpha outcome report --horizon 20
```

## TUI Outcome Review Screen

Press `o` in the TUI to open the Outcome Review screen.

The screen includes:
- Watchlist outcome summary (aggregate stats)
- Candidate outcome table (per-symbol rows)
- Score bucket performance
- Setup type performance
- Risk flag performance
- Pending/missing data panel

## Calibration Report

`vnalpha outcome report --horizon 20` generates a deterministic calibration report from aggregate tables. It answers:

- Are higher score buckets associated with better realized outcomes?
- Which candidate class or setup type has the best research performance?
- Which risk flags correlate with weak realized outcomes?
- How much data is still pending or missing?

## Interpretation Caveats

- **Outcome metrics are retrospective**: they show what happened, not what will happen.
- **No forward guarantee**: past research performance does not imply future results.
- **Outcomes do not change scoring**: the system flags weak setups for human review but does not automatically adjust scoring weights.
- **Research-only boundary**: outcome data must not be used to place orders, execute trades, or manage portfolios.

## Module Layout

```text
vnalpha/src/vnalpha/outcomes/
├── __init__.py
├── models.py          # OutcomeStatus, DEFAULT_HORIZONS, record dataclasses
├── errors.py          # OutcomeError hierarchy
├── horizons.py        # Bar selection logic (entry/exit close, forward window)
├── metrics.py         # forward_return, excess_return, max_gain, max_drawdown
├── evaluator.py       # evaluate_watchlist_date, evaluate_date_range
├── aggregations.py    # aggregate_watchlist_outcome, score/setup/risk aggregations
├── calibration.py     # generate_calibration_report
└── repositories.py    # DuckDB upsert/query helpers for outcome tables
```

## Metric Policy

`metric_policy` controls how `max_gain` and `max_drawdown` are calculated. Pass
it to `evaluate_watchlist_date()` or `evaluate_date_range()`.

| Policy | Source | `max_gain` uses | `max_drawdown` uses |
|--------|--------|-----------------|---------------------|
| `CLOSE_ONLY_V1` (default) | close prices only | `max(window_close / entry - 1)` | `min(window_close / entry - 1)` |
| `OHLC_HIGH_LOW_V1` | high/low prices | `max(window_high / entry - 1)` | `min(window_low / entry - 1)` |

The policy name is stamped on every `candidate_outcome`, `watchlist_outcome`,
`score_bucket_performance`, `setup_type_performance`, and
`risk_flag_performance` row as `metric_policy_version`.

**Changing policy does not re-evaluate old rows.** Each evaluation run stamps
its own policy version. Compare results only within the same policy.

## Evaluation Runs

Every call to `evaluate_watchlist_date()` creates one row in
`outcome_evaluation_run` and stamps all outcome and aggregate rows with
`evaluation_run_id`. This enables:

- auditing which rows were produced by which run;
- detecting stale or duplicate evaluations;
- correlating outcomes with the evaluator and metric policy versions used.

**One run per date**: `evaluate_date_range()` calls `evaluate_watchlist_date()`
once per distinct date found in `daily_watchlist`. Each date gets its own
`evaluation_run_id`.

**CLI output** includes the run id for traceability:

```text
# Single date
Evaluation run: a1b2c3d4-...

# Date range
  2026-01-01: run_id=a1b2c3d4-..., evaluated=12, errors=0
  2026-01-02: run_id=b5c6d7e8-..., evaluated=11, errors=0
```
