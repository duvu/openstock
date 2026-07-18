# 05. Backtest and outcome tracking

> **Status:** stable design principles plus current/target command boundaries.
>
> Current Backtest Lab scope, dependencies and status are owned by GitHub issue
> [#108](https://github.com/duvu/openstock/issues/108); product priority is
> maintained in [#209](https://github.com/duvu/openstock/issues/209).

## Purpose

Backtesting and outcome tracking are the validation layer of `vnalpha`.

The question is not only:

```text
Did the system detect a pattern?
```

The real question is:

```text
Did detected patterns produce a repeatable statistical edge after realistic constraints?
```

## Two validation modes

`vnalpha` should support two complementary validation modes.

### 1. Pattern outcome tracking

Every detected pattern is stored and later evaluated after fixed horizons.

Horizons:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

This is the most important validation mechanism for the MVP.

### 2. Strategy backtesting

A full backtest simulates entry/exit rules, stop losses, position sizing, fees, and market regime filters.

This should come after pattern detection and outcome tracking are stable.

## Pattern outcome schema

```sql
CREATE TABLE pattern_outcome (
    pattern_id BIGINT,
    horizon_days INT,
    forward_return DOUBLE,
    index_return DOUBLE,
    sector_return DOUBLE,
    excess_return DOUBLE,
    max_gain DOUBLE,
    max_drawdown DOUBLE,
    hit_invalidation BOOLEAN,
    hit_take_profit BOOLEAN,
    outcome_label TEXT,
    evaluated_at TIMESTAMP,
    PRIMARY KEY (pattern_id, horizon_days)
);
```

The SQL above is a conceptual contract. The implemented warehouse schema and
migrations remain authoritative.

## Outcome metrics

For each pattern, calculate:

```text
forward_return_Nd
index_return_Nd
sector_return_Nd
excess_return_Nd
max_gain_Nd
max_drawdown_Nd
max_adverse_excursion
max_favorable_excursion
hit_invalidation
hit_take_profit
```

Where:

```text
excess_return = stock_forward_return - benchmark_forward_return
```

Benchmarks:

```text
VN-Index
sector index, if available
VN30, if applicable
```

## Outcome labels

Initial label rules:

### SUCCESS

```text
forward_return_20d > 8%
AND excess_return_20d > 3%
AND max_drawdown_20d > -7%
```

### FAIL

```text
hit_invalidation = true
OR max_drawdown_20d <= -7%
OR excess_return_20d < -3%
```

### NEUTRAL

```text
neither SUCCESS nor FAIL
```

These thresholds should be configurable and versioned. A document example must
not override the implemented metric policy.

## Backtest scenarios

The target Backtest Lab should test at least these entry assumptions.

### Scenario A: close-entry reference only

```text
Entry: close price on signal date
Purpose: analytical reference only
```

This is not realistic if the signal is generated after market close.

### Scenario B: next-open entry

```text
Entry: next session open
Purpose: realistic end-of-day workflow
```

### Scenario C: pullback entry

```text
Entry: first pullback near breakout level or MA20
Purpose: reduce chase risk
```

## Exit rules

Initial target rules:

```text
Exit after 5/10/20 sessions
Stop loss at invalidation level
Stop loss below MA20
Take profit at +10% or +15%
Trailing stop after profit threshold
```

Each rule should be tested separately and represented by a versioned strategy
specification rather than prose-only configuration.

## Required backtest metrics

```text
number_of_trades
win_rate
average_return
median_return
profit_factor
expectancy
max_drawdown
average_holding_days
false_breakout_rate
return_by_year
return_by_market_regime
return_by_sector
```

## Avoiding common backtest errors

### Look-ahead bias

A signal generated after close cannot assume entry at that same close in a realistic strategy.

Bad:

```text
Signal uses close of day T.
Backtest buys at close of day T.
```

Better:

```text
Signal uses close of day T.
Backtest buys at open of T+1 or later.
```

### Survivorship bias

The universe should not include only stocks that still exist today if the backtest period includes delisted or inactive stocks.

MVP limitations must be explicit and must not be presented as point-in-time correctness.

### Liquidity bias

Backtests must exclude or penalize low-liquidity stocks.

Minimum filters:

```text
average traded value threshold
minimum volume threshold
maximum position size as percentage of average daily value
```

### Fees and taxes

Backtest should include:

```text
brokerage fee
transaction tax
slippage
spread assumption
```

### Corporate actions

If prices are not adjusted for splits/dividends, pattern detection and returns can be wrong.

Adjusted-price claims require the provider-independent corporate-action and price-basis contracts owned by issues #112–#114. A vendor request flag is not sufficient lineage.

## Market regime validation

Backtest results should be split by regime only after the production methodology
owned by issue #84 is validated and versioned.

```text
UPTREND
SIDEWAY
DISTRIBUTION
DOWNTREND
RECOVERY
```

A pattern that works only in strong uptrends should not be treated as universally valid.

## Parameter testing

Example parameters:

```text
base_range_pct: 10%, 12%, 15%, 20%
base_window: 20, 30, 40, 60 sessions
volume_ratio: 1.3x, 1.5x, 2.0x
rs_window: 20, 30, 60 sessions
max_distance_to_ma20: 6%, 8%, 10%
```

The goal is not to find the best-looking historical parameter. The goal is to find stable parameter zones with explicit train/test and sensitivity evidence.

## Output reports

The target Backtest Lab should produce:

```text
pattern summary
false breakout report
return distribution
regime breakdown
sector breakdown
parameter sensitivity report
```

## Current and planned command surfaces

Current implemented research-validation commands use the public Typer CLI:

```bash
vnalpha outcome --help
vnalpha outcome evaluate --help
vnalpha cmd "/experiment event-study rs_20d_vs_vnindex > 0 --horizon 10"
```

The exact subcommands shown by `--help` are authoritative for the installed
version. Module-level `python -m vnalpha.<implementation module>` invocations are
not a supported public interface.

A full Backtest Lab command is **planned, not implemented**. Issue #108 and child
issues #119–#121 own its point-in-time dataset, engine, metrics, artifact and
surface contracts. Until those issues close, no command or event-study alias may
be presented as a completed strategy backtest.

## Decision rule

No new AI/ML ranking layer should be added until the system can answer:

```text
What is the historical success rate of each pattern type?
What is the false breakout rate?
Which market regime makes the pattern fail?
Which features separate successful from failed patterns?
```
