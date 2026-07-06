# 10. vnalpha Roadmap — OpenBB-style Research Workspace Service

## Strategic direction

`vnalpha` is an independent research workspace service for Vietnamese equities.

```text
vnstock-service  = data platform service
vnalpha-service  = research workspace service
```

`vnalpha` should not be just a scanner. It should become a workspace where a user can monitor the market, inspect watchlists, open symbol workspaces, review pattern evidence, track outcomes, run backtests, generate AI explanations, and keep a research journal.

Hard boundary:

```text
No broker login
No account APIs
No order placement
No portfolio execution
No auto-trading
No LLM-only prediction engine
No investment-advice workflow
```

---

## Phase 0 — Workspace Service Foundation

### Goal

Create the executable foundation for `vnalpha-service`.

### Core question

Can the service start, load config, expose health API, and connect to future workspace modules?

### Deliverables

```text
pyproject.toml
src/vnalpha/
src/vnalpha/api/
src/vnalpha/common/
configs/
tests/
Dockerfile
docker-compose.yml
Makefile
.env.example
```

### Minimum modules

```text
vnalpha.api.app
vnalpha.api.routes_health
vnalpha.common.config
vnalpha.common.logging
vnalpha.common.types
```

### API

```text
GET /healthz
GET /version
```

### Definition of Done

```text
- project imports successfully
- FastAPI app starts
- /healthz works
- config loads from YAML/env
- test command works
- Docker image builds
- docker compose can start vnalpha-service
```

---

## Phase 1 — vnstock-service Client & Data Contract Integration

### Goal

Allow `vnalpha-service` to consume validated market data from `vnstock-service`.

### Core question

Can `vnalpha` fetch OHLCV, symbols, index data, and provider diagnostics without knowing provider internals?

### Deliverables

```text
src/vnalpha/clients/vnstock/client.py
src/vnalpha/clients/vnstock/schemas.py
src/vnalpha/clients/vnstock/errors.py
configs/services.yaml
integration tests with mocked vnstock-service
```

### Required client operations

```text
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/reference/symbols
GET /v1/company/info
GET /v1/providers/health
GET /v1/providers/capabilities
```

### Must preserve

```text
provider
quality_status
quality_report
diagnostics
fetched_at
ingestion_run_id
```

### Definition of Done

```text
- vnalpha can call vnstock-service base URL from config
- client handles timeout/retry/basic errors
- client maps service response into typed objects
- no direct provider-specific endpoint exists in vnalpha
- tests mock vnstock-service responses
```

---

## Phase 2 — Research Warehouse & Canonical OHLCV

### Goal

Persist raw service responses and build canonical OHLCV for research.

### Core question

Can `vnalpha` create a reliable research dataset from `vnstock-service` output?

### Deliverables

```text
DuckDB schema
Parquet export
ingestion_run table
market_ohlcv table
canonical_ohlcv table
ticker_master table
provider_quality_report table
```

### Minimum tables

```text
ingestion_run
market_ohlcv
canonical_ohlcv
ticker_master
provider_quality_report
```

### Canonical OHLCV minimum fields

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

### Commands

```bash
python -m vnalpha.ingestion.sync_universe
python -m vnalpha.ingestion.sync_ohlcv --start 2023-01-01 --end today
python -m vnalpha.ingestion.build_canonical --date today
```

### Definition of Done

```text
- can sync a small symbol universe
- can store raw market OHLCV
- can build canonical OHLCV
- rejected rows/symbols have reasons
- canonical data is reproducible by date
```

---

## Phase 3 — Feature Store v1

### Goal

Compute deterministic features from canonical OHLCV.

### Core question

Can `vnalpha` transform clean OHLCV into reusable feature snapshots?

### Deliverables

```text
feature_snapshot table
price_features
volume_features
volatility_features
relative_strength
market_regime basic
```

### Minimum features

```text
ma20
ma50
ma100
volume_ma20
volume_ratio
atr14
base_range_30d
close_strength
rs_20d
rs_60d
rs_line
rs_line_slope
distance_to_ma20
```

### Definition of Done

```text
- features are computed only from canonical OHLCV
- feature values are reproducible by date
- missing windows are handled explicitly
- benchmark index comparison works
- synthetic dataset tests pass
```

---

## Phase 4 — Pivot Engine & Market Regime

### Goal

Detect swing structure and classify basic market environment.

### Core question

Can the system understand structure before detecting patterns?

### Deliverables

```text
pivot_points table
market_regime table
zigzag pivot detector
ATR-based pivot detector
trend/regime classifier
market breadth indicators
```

### Minimum regime labels

```text
UPTREND
DOWNTREND
SIDEWAY
RECOVERY
DISTRIBUTION
UNKNOWN
```

### Definition of Done

```text
- pivots are detected deterministically
- regime is computed per date
- detector output is explainable
- pattern engine can consume pivots and regime
```

---

## Phase 5 — Pattern Engine v1

### Goal

Detect first high-value setup families.

### Core question

Can `vnalpha` produce a daily watchlist with evidence, not just tickers?

### Patterns

```text
ACCUMULATION_BASE
ACCUMULATION_BREAKOUT
FAILED_BREAKOUT
```

### Deliverables

```text
PatternDetector interface
AccumulationBaseDetector
AccumulationBreakoutDetector
FailedBreakoutDetector
pattern_instance table
risk flag model
scoring engine
```

### Pattern instance fields

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

### Definition of Done

```text
- system scans universe end-of-day
- each pattern has evidence features
- each pattern has score
- each pattern has status
- each pattern has invalidation logic
- watchlist can be generated from pattern_instance
```

---

## Phase 6 — Watchlist Workspace API

### Goal

Expose the first useful OpenBB-style workspace surface.

### Core question

Can a user open `vnalpha` daily and inspect actionable research artifacts?

### Deliverables

```text
workspace watchlist service
market overview service
symbol workspace service
pattern detail service
workspace API routes
```

### API

```text
GET /v1/workspace/market/overview
GET /v1/workspace/watchlists/daily
GET /v1/workspace/patterns
GET /v1/workspace/patterns/{pattern_id}
GET /v1/workspace/symbols/{symbol}
```

### Definition of Done

```text
- daily watchlist API works
- pattern detail includes evidence and risk flags
- symbol workspace shows features and pattern history
- response contains data lineage
- no AI required yet
```

---

## Phase 7 — Outcome Tracking

### Goal

Evaluate every detected pattern after fixed forward horizons.

### Core question

Do detected setups actually work historically?

### Horizons

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

### Deliverables

```text
pattern_outcome table
forward return calculator
excess return calculator
max gain/drawdown calculator
outcome labeler
outcome summary API
```

### Outcome labels

```text
SUCCESS
FAIL
NEUTRAL
PENDING
```

### API

```text
GET /v1/workspace/outcomes/summary
GET /v1/workspace/patterns/{pattern_id}/outcomes
```

### Definition of Done

```text
- every mature pattern can be evaluated
- outcome label is assigned
- outcome summary by pattern type works
- outcome summary by score bucket works
- failed breakout rate is visible
```

---

## Phase 8 — Streamlit Workspace Dashboard MVP

### Goal

Make the workspace usable without notebooks.

### Core question

Can the user research market setups visually every day?

### Screens

```text
Market Overview
Daily Watchlist
Symbol Workspace
Pattern Detail
Failed Breakout Review
Outcome Summary
Research Journal
```

### Deliverables

```text
src/vnalpha/dashboard/streamlit_app.py
dashboard API client
charts
filters
watchlist export
```

### Definition of Done

```text
- dashboard starts locally
- can filter by date, pattern type, score, sector, status
- can inspect pattern evidence
- can view chart context
- can see risk flags and invalidation level
- can export watchlist
```

---

## Phase 9 — AI Explanation & Risk Critique

### Goal

Add AI as workspace assistant, not signal generator.

### Core question

Can AI explain and critique deterministic research artifacts without inventing data?

### Deliverables

```text
AI client
prompt templates
explain_pattern
risk_critic
daily_report
AI output cache
AI generation metadata
```

### AI input must be grounded in

```text
pattern_instance
feature_snapshot
market_regime
quality_report
outcome_history
```

### API

```text
POST /v1/workspace/ai/explain-pattern
POST /v1/workspace/ai/risk-critic
POST /v1/workspace/ai/daily-report
```

### Must store

```text
model_name
prompt_version
input_hash
generated_at
source_artifact_ids
output_text
```

### Definition of Done

```text
- AI explanation uses pattern JSON only
- AI critique separates setup/data/market/execution risks
- AI does not override score
- AI does not create buy/sell instruction
- prompts are versioned
- outputs are cached and traceable
```

---

## Phase 10 — Research Journal & Report Workspace

### Goal

Turn `vnalpha` from scanner into research workflow system.

### Core question

Can the user record reasoning, compare later outcomes, and generate reports?

### Deliverables

```text
journal_entry table
report table
journal API
daily report generator
weekly review report
pattern review notes
```

### API

```text
POST /v1/workspace/journal
GET  /v1/workspace/journal
GET  /v1/workspace/journal/{entry_id}
POST /v1/workspace/reports/daily
POST /v1/workspace/reports/weekly
```

### Definition of Done

```text
- notes can attach to date/symbol/pattern/watchlist
- reports cite source pattern/data IDs
- later outcome can be compared with original reasoning
- AI can draft reports but not invent missing data
```

---

## Phase 11 — Backtest Lab

### Goal

Validate strategy rules beyond simple outcome tracking.

### Core question

Can the user test entry/exit assumptions and compare performance by regime?

### Deliverables

```text
backtest_run table
backtest_result table
VectorBT integration
entry/exit simulation
fee/slippage assumptions
parameter testing
regime-level performance report
```

### API

```text
POST /v1/workspace/backtests
GET  /v1/workspace/backtests/{backtest_id}
GET  /v1/workspace/backtests/{backtest_id}/results
```

### Definition of Done

```text
- next-session entry assumption supported
- stop-loss and invalidation exits supported
- fees/slippage configurable
- results split by year, sector, regime
- compared with VN-Index/VN30 benchmark
```

---

## Phase 12 — Workspace API, CLI/TUI & Agent-safe Tools

### Goal

Expose workspace state safely to notebooks, CLI/TUI, and future AI agents.

### Core question

Can users and agents query research artifacts without bypassing governance?

### Deliverables

```text
workspace query API
CLI commands
optional TUI
agent-safe tool contracts
workspace search
watchlist export
pattern explain tool
```

### Example commands

```bash
vnalpha market overview
vnalpha watchlist daily
vnalpha symbol FPT
vnalpha pattern PATTERN_ID
vnalpha report daily
```

### Agent-safe tools

```text
get_market_overview
get_daily_watchlist
get_symbol_workspace
get_pattern_detail
get_pattern_outcome
explain_pattern
risk_critic
```

### Forbidden tools

```text
place_order
connect_broker
get_account_balance
execute_portfolio
auto_trade
```

### Definition of Done

```text
- CLI can query core workspace artifacts
- TUI can browse watchlist and pattern detail
- agent tools return grounded evidence only
- no tool accesses broker/order/account capability
```

---

## Phase 13 — Pattern Engine v2

### Goal

Add more sophisticated pattern families after v1 is validated.

### Patterns

```text
VCP
HEALTHY_PULLBACK
DISTRIBUTION
RELATIVE_STRENGTH_LEADER
BASE_BREAKDOWN
SHAKEOUT_RECOVERY
```

### Definition of Done

```text
- new detectors are rule-based and auditable
- each detector has synthetic tests
- each detector has backtest/outcome summary
- detector config is versioned
```

---

## Phase 14 — ML Ranking

### Goal

Rank setups using historical outcomes, not replace deterministic logic.

### Core question

Can ML improve triage after enough labeled pattern outcomes exist?

### Deliverables

```text
training dataset builder
feature leakage checks
LightGBM or similar ranker
model registry metadata
ranking explanation
performance by regime
```

### Definition of Done

```text
- ML trains only on historical outcome labels
- no future leakage
- model output is ranking/triage only
- deterministic pattern evidence remains visible
- AI/ML cannot become investment-advice engine
```

---

## Recommended MVP cut

The first meaningful MVP should stop at Phase 8:

```text
Phase 0: Service foundation
Phase 1: vnstock-service client
Phase 2: Canonical OHLCV
Phase 3: Feature store
Phase 4: Pivot/regime
Phase 5: Pattern Engine v1
Phase 6: Watchlist API
Phase 7: Outcome tracking
Phase 8: Streamlit dashboard
```

AI should start only after the deterministic research artifacts are stable.

---

## Phase dependency summary

```text
0 service foundation
→ 1 data-service client
→ 2 warehouse/canonical data
→ 3 features
→ 4 pivots/regime
→ 5 pattern engine
→ 6 workspace API
→ 7 outcomes
→ 8 dashboard
→ 9 AI explanation
→ 10 journal/report
→ 11 backtest lab
→ 12 CLI/TUI/agent tools
→ 13 pattern v2
→ 14 ML ranking
```
