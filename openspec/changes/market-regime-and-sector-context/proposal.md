# Proposal: Market Regime and Sector Context

## Summary

Implement the market regime and sector context engine required by OpenStock research intelligence, with its OpenSpec requirements.

This change adds the research-only market-regime and sector-context capability to `vnalpha`.

## Motivation

OpenStock currently has symbol-level scoring and relative strength versus VNINDEX. The target system needs broader context so analysis, shortlist, pattern scans, and scenario plans can distinguish between:

```text
strong symbol in strong market
strong symbol in weak market
weak sector participation
broad market deterioration
narrow leadership
improving sector rotation
```

Without regime and sector context, deep analysis and watchlist synthesis remain too symbol-local.

## Scope

Define requirements for:

```text
/market-regime
/sector-strength
market_regime_snapshot
sector_strength_snapshot
breadth metrics
sector ranking
sector rotation state
symbol-sector alignment
assistant tools and intents
TUI rendering hooks
observability and evaluation
```

## Non-goals

- No live trading signal generation.
- No portfolio or allocation recommendation.
- No broker/order/account integration.
- No personalized investment advice.
- No intraday/real-time market regime in MVP.

## Target output

Market regime output must include:

```text
market_regime_state
index_trend
index_volatility
breadth_metrics
sector_strength_ranking
risk_context
freshness
lineage
caveats
```

Sector output must include:

```text
sector
rank
relative_performance
rotation_state
member_count
methodology_version
quality_status
```

## Dependencies

Depends on research-intelligence data model foundation and existing canonical OHLCV/index ingestion.
