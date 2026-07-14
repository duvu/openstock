# Proposal: Deep Symbol Analysis Engine

## Summary

Define the OpenSpec for a consolidated deep symbol analysis engine for OpenStock.

This is an OpenSpec-only change.

This revision records a runtime-proven completion gap and does not claim that
the behavior is implemented.

## Motivation

Current `/explain SYMBOL` can explain a candidate score, but the target system needs a richer warehouse-grounded analysis object that combines trend, momentum, relative strength, volume, volatility, levels, setup quality, caveats, and confidence.

Deep analysis is the core object that later powers assistant answers, TUI drilldowns, shortlist rationale, scenario planning, and historical evidence lookup.

Runtime evidence shows `analysis.deep_symbol` can succeed while declaring
`market_regime_snapshot` and `sector_strength_snapshot` missing. The existing
data-availability service ensures symbol, benchmark, feature, and score
artifacts only, while the assistant hook logs and suppresses an ensure failure
before executing the read tool. The contract therefore needs deterministic
context readiness and a fail-closed gate.

## Scope

Define requirements for:

```text
/analyze SYMBOL
analysis.deep_symbol tool
DeepSymbolAnalysis output contract
SymbolLevelSnapshot usage
SetupAnalysis persistence
multi-timeframe context
support/resistance levels
setup quality and confidence
research-only scenario summary
deterministic readiness for deep-analysis inputs
explicit CLI and TUI user commands for raw and derived data provisioning
structured provisioning status and audit events
```

## Capabilities

### Modified capabilities

- `auto-data-provisioning`: extend deterministic readiness from score inputs to
  the market-regime and sector-strength inputs requested by deep analysis.

### New capabilities

- `data-provisioning-commands`: expose bounded, explicit user commands for
  downloading raw inputs and building supported derived data types.

## Non-goals

- No buy/sell recommendation.
- No target price as investment advice.
- No order, broker, account, portfolio, allocation, margin, or live trading action.
- No unrestricted LLM-generated analysis without deterministic evidence.
- No assistant-selected or assistant-invoked `data.fetch` tool.
- No implicit full-universe refresh for one-symbol analysis unless the user
  explicitly requests a market or sector context build that requires it.

## Target output

```text
symbol
as_of_date
data_freshness
lineage
trend_context
momentum_context
relative_strength_context
volume_context
volatility_context
setup_quality
support_resistance_levels
scenario_summary
risks_caveats
missing_data
confidence
```

## Dependencies

Depends on the accepted auto-data-provisioning and market-regime-and-sector-context
contracts. The active change is partial: the deep tool, assistant intent, and
baseline ensure service exist, but context readiness, explicit manual commands,
and fail-closed integration remain.
