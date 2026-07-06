# 07. Implementation roadmap

## Roadmap principle

Build the smallest useful research workspace loop before adding AI complexity.

Correct order:

```text
service foundation
→ data-service integration
→ canonical research warehouse
→ feature store
→ pattern detection
→ outcome tracking
→ workspace dashboard
→ AI explanation
→ backtest lab
→ ML ranking
```

Wrong order:

```text
multi-agent AI
→ prediction
→ auto-trading
→ later validation
```

## Service assumption

`vnalpha` is now designed as an independent service:

```text
vnstock-service  = data platform service
vnalpha-service  = research workspace service
```

`vnalpha-service` should consume `vnstock-service` through HTTP or a thin client. It should not embed provider-specific market data logic.

---

## Phase 0. Workspace service foundation

Goal: create the project skeleton and service boundary.

Deliverables:

```text
pyproject.toml
README.md
docs/
configs/
src/vnalpha/
src/vnalpha/api/
src/vnalpha/clients/vnstock/
src/vnalpha/workspace/
tests/
Dockerfile
docker-compose.yml
```

Definition of done:

- project imports successfully;
- `vnalpha-service` FastAPI app starts;
- `/healthz` endpoint exists;
- basic CLI entrypoint exists;
- config can point to `vnstock-service`;
- lint/test command is documented;
- docs define service split and workspace scope.

---

## Phase 1. vnstock-service integration and canonical store

Goal: ingest validated end-of-day OHLCV data from `vnstock-service` and build a canonical research dataset.

Deliverables:

```text
vnstock-service HTTP client
sync_universe_from_vnstock_service
sync_ohlcv_from_vnstock_service
quality_gate
build_canonical_ohlcv
DuckDB schema
Parquet export
```

Minimum tables:

```text
ingestion_run
market_ohlcv
canonical_ohlcv
ticker_master
provider_quality_report
```

Definition of done:

- can connect to configured `vnstock-service`;
- can sync a small symbol universe;
- can sync at least 3 years of daily OHLCV;
- quality status is stored;
- provider/source metadata is preserved;
- canonical OHLCV is built;
- rejected symbols have exclusion reasons.

---

## Phase 2. Feature store

Goal: compute core technical, liquidity, relative-strength, and market-regime features.

Deliverables:

```text
price features
volume features
volatility features
candle features
relative strength features
market breadth features
feature table
feature recomputation command
```

Minimum features:

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

Definition of done:

- features are computed from canonical OHLCV only;
- feature table is reproducible by date;
- missing feature cases are handled explicitly;
- at least one benchmark index is supported.

---

## Phase 3. Pattern Engine v1

Goal: detect the first three useful patterns.

Patterns:

```text
ACCUMULATION_BASE
ACCUMULATION_BREAKOUT
FAILED_BREAKOUT
```

Deliverables:

```text
PatternDetector interface
AccumulationBaseDetector
AccumulationBreakoutDetector
FailedBreakoutDetector
Scoring engine
Risk flags
pattern_instance table
```

Definition of done:

- system scans the universe end-of-day;
- each pattern includes evidence features;
- each pattern has status and score;
- each pattern has invalidation logic;
- workspace API can list detected patterns.

---

## Phase 4. Outcome tracking

Goal: evaluate every detected pattern after fixed forward horizons.

Deliverables:

```text
pattern_outcome table
forward return calculator
excess return calculator
max gain/drawdown calculator
outcome labeler
```

Horizons:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

Definition of done:

- every pattern instance can be evaluated later;
- success/fail/neutral labels are assigned;
- outcome summary by pattern type is available;
- failed breakout rate is visible.

---

## Phase 5. Workspace Dashboard MVP

Goal: make the system usable daily as a research workspace.

MVP UI: Streamlit.

Screens:

```text
Market Overview
Daily Watchlist
Symbol Workspace
Pattern Detail
Failed Breakout Review
Outcome Summary
Research Journal
```

API endpoints:

```text
GET /v1/workspace/market/overview
GET /v1/workspace/watchlists/daily
GET /v1/workspace/patterns
GET /v1/workspace/patterns/{pattern_id}
GET /v1/workspace/symbols/{symbol}
GET /v1/workspace/outcomes/summary
```

Definition of done:

- can filter by date, pattern type, score, sector, and status;
- can inspect pattern evidence;
- can view chart context;
- can see risk flags and invalidation level;
- can export watchlist.

---

## Phase 6. AI explanation and risk critique

Goal: add AI as an analyst layer, not a decision engine.

Deliverables:

```text
explain_pattern
risk_critic
daily_report
prompt templates
AI output cache
AI generation metadata
```

Definition of done:

- AI explanation is grounded in pattern JSON;
- AI risk critique separates setup, data, market, and execution risks;
- daily report summarizes only system-provided data;
- prompts are versioned;
- outputs are cached and stored.

---

## Phase 7. Backtest Lab

Goal: validate strategy rules beyond simple outcome tracking.

Deliverables:

```text
VectorBT integration
entry/exit simulation
fee/slippage assumptions
parameter testing
regime-level performance report
```

Definition of done:

- next-session entry assumption is supported;
- stop-loss and invalidation exits are supported;
- fees/slippage can be configured;
- results are split by year, sector, and market regime;
- strategy output can be compared with VN-Index/VN30 benchmark.

---

## Phase 8. Workspace API and agent tools

Goal: expose safe workspace tools for notebooks, CLI/TUI, and future AI agents.

Deliverables:

```text
query APIs
workspace search
pattern explain API
watchlist export API
journal API
agent-safe tool contracts
```

Definition of done:

- agent tools can query workspace state;
- tools return grounded evidence only;
- no tool places orders or accesses broker accounts;
- all AI outputs preserve source pattern/data IDs.

---

## Phase 9. Pattern Engine v2 and ML ranking

Goal: add more sophisticated structures and optional ML ranking after enough outcomes exist.

New detectors:

```text
VCP
HEALTHY_PULLBACK
DISTRIBUTION
RELATIVE_STRENGTH_LEADER
```

Definition of done:

- new detectors are backtested;
- ML ranking is trained only on stored historical outcomes;
- feature leakage checks exist;
- model output is ranking/triage only, not investment advice.

---

## Hard boundary

`vnalpha-service` must remain a research workspace.

It must not implement:

```text
broker login
account balance
order placement
portfolio execution
auto trading
LLM-only prediction engine
investment advice workflow
```
