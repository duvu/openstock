# Fix Research Workspace Consistency, Data Drift, and Accuracy

## Summary

Add an OpenSpec change to fix the consistency, data drift, lineage, and accuracy findings identified in the current `vnalpha` codebase review.

This change is a specification-only change. It defines the implementation work needed to make the Phase 5.8 command layer, Phase 5.9 assistant layer, and Phase 6 outcome layer reliable for historical research and auditability.

## Problem

The codebase has improved substantially: command execution is now shared, tool calls are traced, assistant traces have explicit parent columns, `/scan` handles universe filtering and risk flags, and outcome evaluation now produces aggregates.

Remaining issues are concentrated in three areas:

```text
1. Maintain consistency
   - validation rules still differ between command handlers and tool functions.
   - assistant compare workflow passes symbols to quality.get_status, but the tool registry accepts only one symbol.
   - command handlers still contain fallback direct tool calls.
   - assistant tool traces may populate both research session and assistant session identifiers.

2. Avoid data drift
   - feature_snapshot.date may differ from the actual OHLCV bar used to compute the feature.
   - historical watchlist review may use latest quality data instead of quality as of the watchlist date.
   - rejected_symbol.date currently represents job detection date, not necessarily the affected data bar date.
   - outcome evaluation can change after canonical data is backfilled without an evaluation run/snapshot identifier.

3. Improve accuracy
   - candidate_score lineage may not carry selected_provider and ingestion_run_id.
   - quality tools do not consistently honor date context.
   - outcome max gain/drawdown currently use close-only windows while canonical OHLCV contains high/low.
   - resolve_date(None) uses system local date instead of a Vietnam trading calendar policy.
```

## Goals

- Make feature, scoring, watchlist, assistant, and outcome records auditable by date, source, and run version.
- Ensure historical review uses data available as of the target date, not current/latest data unless explicitly requested.
- Move validation and safety rules to shared lower-level modules so CLI, TUI, and assistant behavior cannot drift.
- Ensure assistant workflows call tools whose argument schemas actually match the plan.
- Clarify outcome metric policy and version outcome evaluation inputs.
- Preserve research-only language and safety boundaries.

## Non-goals

- No broker/order/account/portfolio integration.
- No automatic trading.
- No Python sandbox.
- No web retrieval.
- No MCP client.
- No ML ranking.
- No change to score weights unless a separate scoring calibration spec approves it.

## Scope

### In scope

```text
feature_snapshot as-of metadata
lineage propagation from canonical data to feature and score artifacts
historical quality lookup by target date
rejected_symbol date semantics
shared filter validation
quality.get_many_status or equivalent multi-symbol quality support
assistant compare-quality workflow fix
assistant tool_trace parent consistency
outcome evaluation run/snapshot metadata
outcome metric policy for close-only vs high/low
trading calendar date resolver
fallback direct tool call removal or test-only containment
regression tests for drift and historical accuracy
```

### Out of scope

```text
live trading
portfolio accounting
transaction-level PnL
external news/web retrieval
LLM-driven scoring
automatic mutation of scoring rules
```

## Acceptance summary

This change is complete when:

```text
- feature_snapshot stores the actual source bar date used for each feature row.
- candidate_score lineage includes provider and ingestion_run_id or an explicit missing-lineage status.
- historical watchlist and quality review use quality data as of the target date.
- filter validation is enforced at tool level and shared by CLI/TUI/assistant.
- assistant compare workflows retrieve quality for every requested symbol.
- assistant tool traces have exactly one appropriate parent path.
- outcome evaluation stores evaluation run/snapshot metadata.
- outcome max gain/drawdown metric policy is explicit and tested.
- date resolution uses a Vietnam trading-calendar-aware policy.
- tests prevent recurrence of consistency drift and data drift.
```
