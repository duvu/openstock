# 02. System architecture

## Architecture goal

`vnalpha` should be built as an independent OpenBB-inspired research workspace service for Vietnamese equities.

It should not embed market data provider logic. The data foundation is a separate service:

```text
vnstock-service  = market data platform service
vnalpha-service  = research workspace service
```

`vnalpha-service` owns research state, user-facing workflows, watchlists, dashboards, AI explanations, reports, journals, and backtest/outcome artifacts. `vnstock-service` owns provider connectivity, provider routing, validation, auth-aware data access, rate limits, ingestion runtime, and normalized market data delivery.

The system should not begin as an auto-trading platform.

---

## High-level service architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Workspace UI Layer                        │
│ Streamlit MVP / later Next.js / Watchlist / Journal / Charts │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    vnalpha-service API                       │
│ FastAPI / Workspace API / Query API / Report endpoints       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  Workspace Application Layer                 │
│ Market │ Watchlist │ Pattern │ Backtest │ AI │ Journal │ Risk │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    Core Research Engine                      │
│ Feature │ Pivot │ Pattern │ Scoring │ Outcome │ Regime       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  Research Data Warehouse                     │
│ Raw refs │ Canonical OHLCV │ Features │ Patterns │ Outcomes  │
│ Watchlists │ Reports │ AI outputs │ Journal                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                vnstock-service client adapter                │
│ HTTP client / SDK client / data contracts / diagnostics      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                      vnstock-service                         │
│ Provider plugins │ routing │ quality │ auth │ ingestion      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  External Data Providers                     │
│              KBS / VCI / DNSE / TCBS / others                │
└─────────────────────────────────────────────────────────────┘
```

---

## Product analogy

`vnalpha` should be closer to an investment research workspace than a single scanner.

OpenBB positions Workspace as a place where investment teams bring data, workflows, and AI together under their control, with interactive dashboards that analysts and AI agents can use together. `vnalpha` should adapt that idea to Vietnamese equities, but with a narrower MVP and a strict research-only boundary.

---

## Service ownership boundary

### `vnstock-service` owns

```text
provider plugins
provider auth/session management
provider health and diagnostics
provider routing
quality validation
rate limiting
batch ingestion
raw/normalized market data delivery
market/reference/fundamental/fund data APIs
```

### `vnalpha-service` owns

```text
workspace API
workspace UI
research data warehouse
canonical OHLCV selection
feature store
pivot engine
pattern engine
scoring engine
market regime engine
watchlist generation
outcome tracking
backtest workspace
AI explanation and risk critique
research journal
report generation
```

### Explicit non-ownership

`vnalpha-service` must not own:

```text
provider crawling
provider login implementation
broker account APIs
order placement
portfolio execution
automated trading
investment advice claims
```

---

## Major layers

### 1. Data foundation client

Responsibility:

- call `vnstock-service` through HTTP or a thin SDK client;
- request validated data and provider diagnostics;
- preserve provider metadata and quality status;
- translate service responses into local research ingestion records;
- avoid direct dependency on provider-specific endpoints.

Boundary:

`vnalpha` should not reimplement provider crawling or endpoint-specific logic if `vnstock-service` already provides it.

### 2. Research data warehouse

Responsibility:

- persist fetched data snapshots;
- store quality reports and provider diagnostics;
- build canonical OHLCV dataset;
- version ingestion runs;
- provide reliable tables for feature engineering and backtests;
- store workspace artifacts such as watchlists, AI outputs, reports, and journal entries.

Recommended MVP storage:

```text
DuckDB + Parquet
```

Recommended later storage:

```text
PostgreSQL / TimescaleDB + object storage
```

### 3. Core research engine

Responsibility:

- compute features;
- identify swing/pivot points;
- detect pattern candidates;
- score patterns;
- classify market regime;
- evaluate outcomes;
- prepare backtest datasets.

This is the deterministic research engine. It should be unit-tested and auditable.

### 4. Workspace application layer

Responsibility:

- produce daily watchlists;
- expose pattern details;
- run backtests;
- store journal entries;
- generate AI explanations and risk critiques;
- support user workflows such as market overview, symbol workspace, pattern review, failed breakout review, and outcome analysis.

### 5. Workspace API layer

MVP API:

```text
GET  /healthz
GET  /v1/workspace/market/overview
GET  /v1/workspace/watchlists/daily
GET  /v1/workspace/patterns
GET  /v1/workspace/patterns/{pattern_id}
GET  /v1/workspace/symbols/{symbol}
GET  /v1/workspace/outcomes/summary
POST /v1/workspace/backtests
POST /v1/workspace/ai/explain-pattern
POST /v1/workspace/journal
```

Forbidden API groups:

```text
broker login
account balance
order placement
order history
portfolio execution
auto trading
```

### 6. Workspace UI layer

MVP UI:

```text
Streamlit
```

Later UI:

```text
FastAPI backend + Next.js frontend
```

Workspace screens:

```text
Market Overview
Daily Watchlist
Symbol Workspace
Pattern Detail
Failed Breakout Review
Outcome Summary
Backtest Lab
AI Explanation
Research Journal
```

---

## Service decomposition

MVP can be two services:

```text
vnstock-service
vnalpha-service
```

Inside `vnalpha-service`, use modular monolith boundaries:

```text
vnalpha/
├── clients
│   └── vnstock
├── ingestion
├── warehouse
├── features
├── pivots
├── patterns
├── scoring
├── regime
├── outcome
├── backtest
├── ai
├── workspace
├── api
├── dashboard
└── common
```

A later split could be:

```text
workspace-api
feature-service
pattern-service
backtest-service
ai-report-service
dashboard
```

Do not split `vnalpha-service` into microservices before the core scanner/backtest is proven useful.

---

## Daily processing flow

```text
1. sync_universe_from_vnstock_service
2. sync_ohlcv_from_vnstock_service
3. store_raw_service_responses
4. build_canonical_ohlcv
5. compute_features
6. detect_pivots
7. detect_patterns
8. score_patterns
9. update_pattern_outcomes
10. generate_watchlist
11. generate_ai_explanations
12. publish_workspace_dashboard
```

---

## Key data contracts

### Canonical OHLCV

The feature engine must consume canonical data, not anonymous provider frames.

Minimum fields:

```text
symbol
time
interval
open
high
low
close
volume
selected_provider
quality_status
ingestion_run_id
source_service_run_id
```

### Pattern instance

Every detected pattern should be stored as a structured object.

Minimum fields:

```text
pattern_id
symbol
pattern_type
start_date
end_date
trigger_date
status
score
invalidation_price
feature_json
risk_json
data_quality_status
ingestion_run_id
created_at
```

### Pattern outcome

Every pattern should later receive forward outcome labels.

Minimum fields:

```text
pattern_id
horizon_days
forward_return
index_return
sector_return
excess_return
max_gain
max_drawdown
outcome_label
```

### Workspace artifact

Workspace state should be explicit.

Minimum fields:

```text
artifact_id
artifact_type
workspace_date
symbol
pattern_id
payload_json
created_by
generated_by
created_at
```

---

## Technology choices

### MVP

```text
Python
FastAPI
Streamlit
DuckDB
Parquet
Pandas / NumPy
vnstock-service HTTP client
LiteLLM-compatible gateway
```

### Later

```text
PostgreSQL / TimescaleDB
Next.js
Redis cache
VectorBT
MLflow
MCP tools
```

---

## Deployment view

Local MVP:

```text
docker compose
├── vnstock-service
├── vnalpha-service
├── vnalpha-dashboard
└── duckdb/parquet volume
```

Later deployment:

```text
vnstock-service
vnalpha-service
workspace-dashboard
postgres/timescaledb
object storage
llm gateway
```

---

## Design principle

`vnstock-service` answers: "What is the validated market data?"

`vnalpha-service` answers: "What does this data mean for research, patterns, watchlists, risk, outcomes, and reports?"
