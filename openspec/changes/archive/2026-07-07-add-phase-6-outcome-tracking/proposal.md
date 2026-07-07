# Add Phase 6 Outcome Tracking and Feedback Loop

## Summary

Add an OpenSpec change for Phase 6: Outcome Tracking and Feedback Loop.

Phase 5 produces daily research candidates. Phase 6 measures whether those candidates actually perform after fixed forward horizons and uses the result to calibrate scoring, setup types, and risk flags.

The key shift:

```text
Phase 5 = discover candidates today
Phase 6 = evaluate whether prior candidates worked
```

## Motivation

Without outcome tracking, the scoring engine remains an unverified heuristic.

The system needs to answer:

```text
Do high-score candidates outperform lower-score candidates?
Do STRONG_CANDIDATE rows outperform WATCH_CANDIDATE rows?
Which setup types have the best realized outcomes?
Which risk flags predict weak outcomes?
How often do candidates fail after being selected?
```

Phase 6 turns watchlist generation into a measurable feedback loop.

## Goals

- Persist candidate-level forward outcomes for fixed horizons.
- Compute benchmark-relative outcomes versus VNINDEX.
- Track max gain and max drawdown after candidate discovery.
- Aggregate performance by score bucket, candidate class, setup type, and risk flag.
- Identify false positives and weak setup types.
- Provide CLI/TUI review surfaces for outcome analysis.
- Preserve research-only boundaries: outcome metrics are evaluation artifacts, not trading instructions.

## Non-goals

- No live trading.
- No broker/order/account/portfolio integration.
- No autonomous strategy execution.
- No ML ranking yet.
- No full backtest lab yet.
- No transaction-cost/slippage modeling beyond optional annotations.
- No investment advice wording.

## Scope

### In scope

```text
candidate_outcome table
watchlist_outcome table
score_bucket_performance table
setup_type_performance table
risk_flag_performance table
outcome evaluator
benchmark-relative return calculation
horizon windows: 5, 10, 20, 60 sessions
CLI outcome commands
TUI outcome review screen
calibration report
```

### Out of scope

```text
Phase 8 backtest lab
Phase 11 AI analyst workflows
Phase 13 ML ranking
broker execution
portfolio accounting
transaction-level PnL
```

## User impact

Users can review whether the watchlist is useful over time.

Example questions Phase 6 should answer:

```text
How did candidates from 20 sessions ago perform?
Did STRONG_CANDIDATE outperform WATCH_CANDIDATE?
Which setup type worked best in the last 3 months?
Which risk flags were associated with poor outcomes?
Are scores above 0.80 actually better than scores between 0.60 and 0.70?
```

## Safety impact

Outcome tracking is retrospective evaluation. It must not become trade recommendation logic.

Allowed language:

```text
realized outcome
forward return
excess return
hit rate
failure rate
calibration
false positive
research performance
```

Forbidden behavior:

```text
buy/sell instruction
order execution
portfolio action
future guarantee
```

## Acceptance summary

The change is complete when:

```text
- historical daily_watchlist rows can be evaluated after forward windows complete.
- candidate_outcome records are persisted for 5/10/20/60-session horizons.
- outcome metrics include forward_return, excess_return_vs_vnindex, max_gain, and max_drawdown.
- aggregate performance is available by score bucket, candidate class, setup type, and risk flag.
- CLI and TUI can show outcome review.
- missing future data is handled explicitly and not fabricated.
- no trading execution or recommendation language is introduced.
```
