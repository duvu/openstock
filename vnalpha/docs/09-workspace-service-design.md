# 09. Workspace service design

## Purpose

`vnalpha-service` is the research workspace layer for Vietnamese equities.

It is inspired by the OpenBB Workspace model: one controlled environment where analysts, dashboards, research workflows, and AI assistants operate on the same governed data and context.

The service boundary is explicit:

```text
vnstock-service  = data platform service
vnalpha-service  = research workspace service
```

## Core idea

`vnalpha-service` should not be a single scanner script.

It should be a workspace that lets users:

- monitor the market;
- inspect watchlists;
- open a symbol workspace;
- inspect pattern evidence;
- review failed setups;
- track forward outcomes;
- run backtests;
- generate AI explanations and critiques;
- keep a research journal.

## Service responsibilities

`vnalpha-service` owns:

```text
workspace API
workspace UI state
canonical research datasets
feature store
pattern engine
outcome tracker
backtest artifacts
AI explanations
risk critiques
reports
research journal
```

`vnalpha-service` does not own:

```text
market provider login
provider crawling
provider-specific endpoints
broker account data
order placement
portfolio execution
auto-trading
investment advice claims
```

## Dependency on vnstock-service

`vnalpha-service` consumes `vnstock-service` through a service client.

Minimum data operations:

```text
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/reference/symbols
GET /v1/company/info
GET /v1/providers/health
GET /v1/providers/capabilities
```

`vnalpha-service` should preserve:

```text
provider
quality_status
quality_report
diagnostics
fetched_at
ingestion_run_id
```

## Workspace modules

### 1. Market Overview

Purpose:

- summarize index behavior;
- show market breadth;
- show sector strength;
- show liquidity conditions;
- identify regime.

Output examples:

```text
VNINDEX trend state
VN30 leadership
advancers / decliners
new highs / new lows
volume above/below average
risk-on / risk-off regime
```

### 2. Daily Watchlist

Purpose:

- list symbols with interesting setups;
- rank by deterministic score;
- show evidence, not just a score.

Minimum fields:

```text
symbol
pattern_type
status
score
setup_date
trigger_date
relative_strength
volume_signal
risk_flags
invalidation_price
```

### 3. Symbol Workspace

Purpose:

- open a single-symbol research page;
- show price/volume context;
- show detected patterns;
- show feature history;
- show outcome history.

### 4. Pattern Detail

Purpose:

- explain why a pattern exists;
- expose every evidence feature;
- show invalidation logic;
- show data quality and provider lineage.

### 5. Failed Breakout Review

Purpose:

- learn from invalidated setups;
- detect repeat failure modes;
- improve pattern rules.

### 6. Outcome Summary

Purpose:

- evaluate patterns after 5/10/20/60 sessions;
- aggregate by pattern type, score bucket, sector, and regime.

### 7. Backtest Lab

Purpose:

- test deterministic rules;
- configure entry/exit assumptions;
- compare against benchmarks.

### 8. AI Explanation

Purpose:

- generate grounded explanation from pattern JSON;
- critique setup risk;
- summarize daily market context;
- write journal notes.

AI must not generate unverified buy/sell instructions or override deterministic rules.

### 9. Research Journal

Purpose:

- store user notes;
- attach notes to symbols, patterns, watchlists, or dates;
- compare later outcomes against original reasoning.

## API design

### Health

```text
GET /healthz
```

### Market workspace

```text
GET /v1/workspace/market/overview
GET /v1/workspace/market/regime
GET /v1/workspace/market/breadth
```

### Watchlists

```text
GET  /v1/workspace/watchlists/daily
GET  /v1/workspace/watchlists/{watchlist_id}
POST /v1/workspace/watchlists/export
```

### Symbols

```text
GET /v1/workspace/symbols/{symbol}
GET /v1/workspace/symbols/{symbol}/features
GET /v1/workspace/symbols/{symbol}/patterns
GET /v1/workspace/symbols/{symbol}/outcomes
```

### Patterns

```text
GET /v1/workspace/patterns
GET /v1/workspace/patterns/{pattern_id}
GET /v1/workspace/patterns/{pattern_id}/evidence
GET /v1/workspace/patterns/{pattern_id}/outcomes
```

### Backtests

```text
POST /v1/workspace/backtests
GET  /v1/workspace/backtests/{backtest_id}
```

### AI

```text
POST /v1/workspace/ai/explain-pattern
POST /v1/workspace/ai/risk-critic
POST /v1/workspace/ai/daily-report
```

### Journal

```text
POST /v1/workspace/journal
GET  /v1/workspace/journal
GET  /v1/workspace/journal/{entry_id}
```

## Forbidden endpoints

`vnalpha-service` must not expose:

```text
POST /order
POST /trade
POST /broker/login
GET  /account
GET  /portfolio/live
POST /portfolio/execute
```

## Data model overview

Minimum tables:

```text
ingestion_run
market_ohlcv
canonical_ohlcv
feature_snapshot
pattern_instance
pattern_outcome
watchlist
watchlist_item
ai_output
journal_entry
backtest_run
backtest_result
```

## AI safety and grounding

AI outputs must be generated from structured workspace data:

```text
pattern_instance
feature_snapshot
market_regime
quality_report
outcome_history
```

AI outputs must store:

```text
model_name
prompt_version
input_hash
generated_at
source_artifact_ids
output_text
```

AI must not:

```text
override score
place orders
generate broker payloads
claim certainty
invent missing data
```

## Deployment model

Local MVP:

```text
docker compose
├── vnstock-service      # market data service
├── vnalpha-service      # FastAPI workspace service
├── vnalpha-dashboard    # Streamlit workspace UI
└── data-volume          # DuckDB + Parquet
```

Service URLs:

```text
vnstock-service: http://localhost:6900
vnalpha-service: http://localhost:7800
vnalpha-dashboard: http://localhost:8501
```

## MVP build order

```text
1. Create FastAPI service skeleton.
2. Add vnstock-service client.
3. Add DuckDB schema.
4. Sync small OHLCV universe.
5. Build canonical OHLCV.
6. Compute core features.
7. Detect accumulation base and breakout.
8. Generate daily watchlist API.
9. Build Streamlit dashboard.
10. Add AI explanation after pattern evidence is stable.
```

## Design rule

`vnalpha-service` should never answer from raw market data alone.

It should answer from research artifacts with lineage:

```text
raw service response
→ canonical OHLCV
→ feature snapshot
→ pattern instance
→ watchlist item
→ explanation / journal / report
```
