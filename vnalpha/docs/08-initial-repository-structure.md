# 08. Initial repository structure

## Recommended structure

`vnalpha` is now designed as an independent workspace service. The repository should start as a modular monolith with a FastAPI service, Streamlit dashboard, and a thin client for `vnstock-service`.

```text
vnalpha/
├── README.md
├── docs/
│   ├── README.md
│   ├── 01-vision-and-scope.md
│   ├── 02-system-architecture.md
│   ├── 03-data-pipeline.md
│   ├── 04-pattern-engine.md
│   ├── 05-backtest-and-outcome.md
│   ├── 06-ai-layer.md
│   ├── 07-implementation-roadmap.md
│   ├── 08-initial-repository-structure.md
│   └── 09-workspace-service-design.md
│
├── configs/
│   ├── app.yaml
│   ├── services.yaml
│   ├── universe.yaml
│   ├── features.yaml
│   ├── patterns.yaml
│   └── scoring.yaml
│
├── src/
│   └── vnalpha/
│       ├── __init__.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── routes_health.py
│       │   ├── routes_market.py
│       │   ├── routes_watchlist.py
│       │   ├── routes_patterns.py
│       │   ├── routes_outcomes.py
│       │   ├── routes_backtest.py
│       │   └── routes_ai.py
│       │
│       ├── clients/
│       │   └── vnstock/
│       │       ├── __init__.py
│       │       ├── client.py
│       │       ├── schemas.py
│       │       └── errors.py
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── sync_universe.py
│       │   ├── sync_ohlcv.py
│       │   ├── quality_gate.py
│       │   └── build_canonical.py
│       │
│       ├── warehouse/
│       │   ├── __init__.py
│       │   ├── duckdb_store.py
│       │   ├── parquet_store.py
│       │   └── schema.sql
│       │
│       ├── features/
│       │   ├── __init__.py
│       │   ├── price_features.py
│       │   ├── volume_features.py
│       │   ├── volatility_features.py
│       │   ├── candle_features.py
│       │   ├── relative_strength.py
│       │   └── market_regime.py
│       │
│       ├── pivots/
│       │   ├── __init__.py
│       │   ├── zigzag.py
│       │   └── atr_pivot.py
│       │
│       ├── patterns/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── accumulation_base.py
│       │   ├── accumulation_breakout.py
│       │   ├── failed_breakout.py
│       │   ├── vcp.py
│       │   └── healthy_pullback.py
│       │
│       ├── scoring/
│       │   ├── __init__.py
│       │   └── pattern_score.py
│       │
│       ├── outcome/
│       │   ├── __init__.py
│       │   ├── forward_returns.py
│       │   └── outcome_labeler.py
│       │
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── vectorbt_runner.py
│       │   └── metrics.py
│       │
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── client.py
│       │   ├── explain_pattern.py
│       │   ├── risk_critic.py
│       │   ├── daily_report.py
│       │   └── prompts/
│       │       ├── explain_pattern.md
│       │       ├── risk_critic.md
│       │       └── daily_report.md
│       │
│       ├── workspace/
│       │   ├── __init__.py
│       │   ├── market_overview.py
│       │   ├── watchlist.py
│       │   ├── symbol_workspace.py
│       │   ├── pattern_detail.py
│       │   ├── journal.py
│       │   └── reports.py
│       │
│       ├── dashboard/
│       │   ├── __init__.py
│       │   └── streamlit_app.py
│       │
│       └── common/
│           ├── __init__.py
│           ├── config.py
│           ├── logging.py
│           └── types.py
│
├── scripts/
│   ├── run_eod_pipeline.sh
│   └── backfill_ohlcv.sh
│
├── notebooks/
│   ├── 01_data_quality_check.ipynb
│   ├── 02_feature_exploration.ipynb
│   └── 03_pattern_backtest.ipynb
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── Makefile
```

## Minimal first implementation

Do not build everything at once.

Start with this reduced structure:

```text
vnalpha/
├── README.md
├── docs/
├── configs/
│   ├── app.yaml
│   ├── services.yaml
│   └── universe.yaml
├── src/
│   └── vnalpha/
│       ├── api/
│       │   ├── app.py
│       │   └── routes_health.py
│       ├── clients/
│       │   └── vnstock/
│       │       ├── client.py
│       │       └── schemas.py
│       ├── ingestion/
│       │   ├── sync_ohlcv.py
│       │   ├── quality_gate.py
│       │   └── build_canonical.py
│       ├── warehouse/
│       │   ├── duckdb_store.py
│       │   └── schema.sql
│       ├── features/
│       │   ├── price_features.py
│       │   ├── volume_features.py
│       │   └── relative_strength.py
│       ├── patterns/
│       │   ├── base.py
│       │   ├── accumulation_base.py
│       │   └── accumulation_breakout.py
│       ├── workspace/
│       │   ├── watchlist.py
│       │   └── pattern_detail.py
│       └── dashboard/
│           └── streamlit_app.py
└── tests/
```

## Suggested configuration files

### configs/app.yaml

```yaml
app:
  name: vnalpha-service
  environment: local
  storage_path: ./data
  timezone: Asia/Ho_Chi_Minh
```

### configs/services.yaml

```yaml
services:
  vnstock:
    mode: service
    base_url: http://localhost:6900
    timeout_seconds: 30
    default_source: auto
    validate: true
```

### configs/universe.yaml

```yaml
universe:
  name: vn_equity_core
  exchanges:
    - HOSE
    - HNX
    - UPCOM
  exclude:
    listing_status:
      - delisted
      - suspended
    liquidity:
      min_avg_traded_value_20d: 3000000000
```

### configs/patterns.yaml

```yaml
accumulation_base:
  min_base_days: 30
  max_base_days: 60
  max_base_range_pct: 0.15
  min_close_position: 0.5
  require_rs_positive: true

accumulation_breakout:
  min_volume_ratio: 1.5
  min_close_strength: 0.75
  max_distance_to_ma20: 0.10
  require_market_regime:
    - UPTREND
    - RECOVERY
    - SIDEWAY
```

### configs/scoring.yaml

```yaml
accumulation_breakout:
  structure_weight: 0.30
  volume_weight: 0.25
  relative_strength_weight: 0.20
  market_regime_weight: 0.15
  liquidity_weight: 0.10

ratings:
  high_quality: 85
  watchlist: 70
  early_candidate: 55
```

## Suggested command flow

Service startup:

```bash
uvicorn vnalpha.api.app:app --host 127.0.0.1 --port 7800
```

Pipeline:

```bash
python -m vnalpha.ingestion.sync_ohlcv --start 2023-01-01 --end today
python -m vnalpha.ingestion.build_canonical --date today
python -m vnalpha.features.price_features --date today
python -m vnalpha.features.volume_features --date today
python -m vnalpha.features.relative_strength --date today
python -m vnalpha.patterns.accumulation_base --date today
python -m vnalpha.patterns.accumulation_breakout --date today
streamlit run src/vnalpha/dashboard/streamlit_app.py
```

Docker compose target:

```bash
docker compose up vnstock-service vnalpha-service vnalpha-dashboard
```

## Initial package dependencies

Recommended starting dependencies:

```text
fastapi
uvicorn
httpx
pydantic
pydantic-settings
pandas
numpy
duckdb
pyarrow
pyyaml
plotly
streamlit
```

Later:

```text
vectorbt
litellm
mlflow
lightgbm
redis
```

## Testing priorities

First tests should cover:

```text
vnstock-service client contract
OHLC consistency validation
quality gate decisions
canonical OHLCV construction
MA/volume/RS feature computation
accumulation base detection
breakout detection
failed breakout detection
forward return calculation
workspace watchlist API response
```

## Development rule

Every pattern detector should be testable with a small synthetic OHLCV dataset.

Do not rely only on visual chart inspection.

`vnalpha` must never call broker/account/order APIs. It is a research workspace service only.
