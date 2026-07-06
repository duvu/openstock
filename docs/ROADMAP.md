# openstock System Roadmap

## System boundary

`openstock` is the orchestration repository for the full research system.

```text
openstock
├── vnstock   # data platform service
└── vnalpha   # research engine and TUI workspace
```

The repository intentionally owns cross-repo roadmap, integration specs, local orchestration, and end-to-end acceptance criteria.

## Product goal

Build a local-first Vietnamese equity research system that can generate a daily alpha discovery watchlist.

The system should help answer:

```text
Which stocks are worth monitoring today, why, and what are the risks?
```

It must not place orders, connect to broker execution APIs, manage portfolios, or present deterministic scoring as investment advice.

---

## Phase 1-4 — vnstock data platform foundation

Phase 1-4 belong mainly to `vnstock`.

### Phase 1 — Core contracts and plugin foundation

Goal:

```text
Define the internal plugin architecture: ProviderPlugin, PluginRegistry, DatasetContract, DataResult.
```

Closure target:

```text
97-99% once conformance tests, contract tests, and status docs are complete.
```

### Phase 2 — Provider plugin normalization

Goal:

```text
Normalize built-in providers behind ProviderPlugin and default_plugin_registry().
```

Built-in providers:

```text
KBS
VCI
DNSE
TCBS
FMARKET
MSN
FMP
```

### Phase 3 — Health-aware and auth-aware routing

Goal:

```text
Route dataset requests by provider capability, priority, health, cooldown, and auth policy.
```

### Phase 3.5 — PluginRuntime default execution path

Goal:

```text
Make PluginRuntime the default execution path for migrated datasets.
```

### Phase 4 — Auth-aware local data service runtime

Goal:

```text
Expose vnstock as a local-first, read-only market data service.
```

Required service contract:

```text
GET /v1/reference/symbols
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/providers/health
GET /v1/providers/capabilities
```

Required service envelope:

```text
data
meta
diagnostics
```

Auth boundary:

```text
CLI auth allowed, especially TCBS local interactive auth.
REST login is forbidden.
Broker/account/order/portfolio APIs are forbidden.
```

---

## Phase 5 — End-to-End Alpha Discovery MVP with TUI

Phase 5 is the first system-level phase owned by `openstock`.

### Goal

Create the first useful end-to-end research workflow:

```text
vnstock-service
→ vnalpha sync
→ DuckDB research warehouse
→ feature store
→ scoring engine
→ daily watchlist
→ TUI workspace
```

### Output

A daily alpha discovery watchlist:

```text
symbol
score
candidate_class
setup_type
evidence
risk_flags
provider lineage
data quality status
```

### User interface

Use TUI, not Streamlit.

Recommended stack:

```text
Textual   # TUI framework
Rich      # tables, panels, console rendering
Typer     # CLI commands
DuckDB    # local research database
Pandas    # feature engineering
Plotext   # optional terminal charts
```

### Phase 5 modules

```text
5.0 openstock orchestration
5.1 vnstock operational contract
5.2 vnalpha core skeleton
5.3 vnstock client
5.4 DuckDB research warehouse
5.5 feature store v1
5.6 alpha scoring v1
5.7 daily watchlist TUI
```

### Minimum commands

```bash
make up-vnstock
make sync
make features
make score
make tui

vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui
```

### Minimum TUI screens

```text
Home / Market Overview
Daily Watchlist
Symbol Detail
Rejected Symbols
Provider / Data Quality
```

### Minimum scoring model

```text
Trend score              25
Relative strength score  25
Volume score             15
Base/compression score   15
Breakout proximity       10
Risk/data quality        10
```

Candidate classes:

```text
STRONG_CANDIDATE  score >= 80
WATCH_CANDIDATE   65 <= score < 80
WEAK_CANDIDATE    50 <= score < 65
IGNORE            score < 50
```

Setup types v1:

```text
TREND_CONTINUATION
ACCUMULATION_BASE
BASE_BREAKOUT_ATTEMPT
PULLBACK_TO_MA20
RELATIVE_STRENGTH_LEADER
```

### Definition of Done

```text
- openstock can start vnstock-service locally.
- vnalpha CLI runs.
- vnalpha can call vnstock-service.
- VN30 symbols and OHLCV can be synced.
- DuckDB warehouse is created.
- canonical_ohlcv is built.
- feature_snapshot is built.
- candidate_score is generated.
- daily_watchlist is generated.
- TUI opens daily watchlist.
- TUI can drill into symbol detail.
- each candidate has score breakdown, evidence, risk flags, and lineage.
- no buy/sell/order/portfolio language appears in API or TUI.
```

---

## Phase 6 — Outcome Tracking and Feedback Loop

Goal:

```text
Measure whether candidates actually work after fixed forward horizons.
```

Horizons:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

Tables:

```text
candidate_outcome
watchlist_outcome
score_bucket_performance
setup_type_performance
```

Metrics:

```text
forward_return
excess_return_vs_vnindex
max_gain
max_drawdown
hit_rate
failure_rate
average_return_by_score_bucket
```

Reason:

```text
Without outcome tracking, scoring remains an unverified heuristic.
```

---

## Phase 7 — Backtest Lab v1

Goal:

```text
Validate scoring and setup rules historically before adding more pattern complexity.
```

Scope:

```text
setup-type backtests
score-bucket backtests
market-regime split
threshold sensitivity
transaction-cost assumption
look-ahead-bias checks
```

---

## Phase 8 — Reliable Batch Ingestion and Warehouse Hardening

Goal:

```text
Harden data ingestion only after the alpha discovery loop proves useful.
```

Scope:

```text
rate limiter
retry policy
incremental sync
raw archive
Parquet/DuckDB optimization
data gap detector
provider failover report
scheduled jobs
```

---

## Phase 9 — AI Analyst Layer

Goal:

```text
Use AI to explain and critique deterministic research artifacts, not to generate independent signals.
```

Allowed:

```text
explain candidate
risk critic
daily report
weekly review
```

Forbidden:

```text
AI-only prediction
buy/sell instruction
order generation
portfolio execution
```

---

## Phase 10 — Advanced Pattern Engine

Goal:

```text
Add richer deterministic pattern families after candidate outcome data exists.
```

Candidate patterns:

```text
VCP
healthy pullback
failed breakout
distribution day
base-on-base
relative strength new high
```

---

## Phase 11 — ML Ranking

Goal:

```text
Train ranking models only after enough outcome history exists.
```

Output must remain ranking/research support, not prediction guarantee or investment advice.

---

## Operating principle

Implement the smallest end-to-end loop first:

```text
VN30
→ OHLCV
→ features
→ score
→ watchlist
→ TUI
→ outcome tracking
```

Do not optimize ingestion, AI, or advanced patterns before this loop works daily.
