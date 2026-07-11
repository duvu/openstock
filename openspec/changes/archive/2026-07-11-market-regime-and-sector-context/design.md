# Design: Market Regime and Sector Context

## Architecture

```text
canonical/index/symbol data
  -> MarketRegimeBuilder
  -> SectorStrengthBuilder
  -> regime/sector repositories
  -> command handlers
  -> assistant tools
  -> TUI rendering
  -> research answer audit
```

## Proposed modules

```text
vnalpha/research_intelligence/regime.py
vnalpha/research_intelligence/sector.py
vnalpha/research_intelligence/breadth.py
vnalpha/research_intelligence/regime_repo.py
vnalpha/commands/handlers/market_regime.py
vnalpha/commands/handlers/sector_strength.py
```

## Market regime logic

MVP regime logic should be deterministic and data-grounded.

Example dimensions:

```text
index trend: above/below key moving averages, slope, return windows
index volatility: ATR or rolling volatility regime
breadth: percent of symbols above moving averages, positive return participation, new strength proxy
risk context: high volatility, weak breadth, narrow leadership, deteriorating index
```

Regime states should be coarse and caveated:

```text
risk_on
constructive
mixed
risk_off
insufficient_data
```

The regime state requires at least 60 benchmark bars, while output-only return
windows preserve unavailable values as null rather than fabricated zeroes. Breadth
percentages use only active non-benchmark symbols with exact-date usable feature
rows; outputs separately report the active universe, eligible denominator,
excluded count, and coverage.

## Sector strength logic

Sector strength should rank sectors using available symbol metadata and persisted market data.

Example dimensions:

```text
sector median return windows
sector relative strength vs VNINDEX
sector percent above MA20/MA50
sector leadership count
rotation_state: improving | stable | weakening | insufficient_data
```

## Commands

```text
/market-regime [--date YYYY-MM-DD]
/sector-strength [--date YYYY-MM-DD] [--top N]
/sector-strength SYMBOL [--date YYYY-MM-DD]
```

## Assistant integration

Add bounded tools:

```text
market.get_regime
sector.get_strength
sector.get_symbol_alignment
```

Add intents:

```text
review_market_regime
review_sector_strength
review_symbol_sector_alignment
```

## Output requirements

Every output must include:

```text
as_of_date
methodology_version
freshness
lineage
quality status
caveats
```

## Boundary

The engine provides context. It must not generate allocation, rebalance, order, or live trading instructions.
