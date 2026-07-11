# Proposal: Deep Symbol Analysis Engine

## Summary

Define the OpenSpec for a consolidated deep symbol analysis engine for OpenStock.

This change defines and implements the deep symbol analysis engine in `vnalpha`.

## Motivation

Current `/explain SYMBOL` can explain a candidate score, but the target system needs a richer warehouse-grounded analysis object that combines trend, momentum, relative strength, volume, volatility, levels, setup quality, caveats, and confidence.

Deep analysis is the core object that later powers assistant answers, TUI drilldowns, shortlist rationale, scenario planning, and historical evidence lookup.

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
```

## Non-goals

- No buy/sell recommendation.
- No target price as investment advice.
- No order, broker, account, portfolio, allocation, margin, or live trading action.
- No unrestricted LLM-generated analysis without deterministic evidence.

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

Depends on data model foundation and benefits from market regime/sector context.
