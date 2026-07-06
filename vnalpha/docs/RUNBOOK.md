# vnalpha Phase 5 — Local Development Runbook

## Repository Location

`vnalpha` is vendored under `openstock/vnalpha`.
All implementation work targets this directory.
The `openstock` root is the orchestration and source-of-truth repository.

## Prerequisites

- Python 3.11+
- pip (system or venv)
- `vnstock-service` running locally on port 6900 (optional — see Fixture Mode)

## Installation

```bash
# From the openstock root:
make install-vnalpha

# Or directly:
pip install -e vnalpha/
```

## Environment Variables

Copy `.env.example` and set:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `VNSTOCK_SERVICE_URL` | `http://localhost:6900` | Base URL of the vnstock HTTP service |
| `VNALPHA_WAREHOUSE_PATH` | `~/.vnalpha/warehouse.duckdb` | Path to the local DuckDB warehouse |
| `VNALPHA_UNIVERSE` | `VN30` | Universe filter (VN30, HOSE_LIQUID, or ALL) |
| `VNALPHA_LOG_LEVEL` | `INFO` | Logging level |

## First-Time Setup

```bash
# 1. Initialize the warehouse (creates DuckDB schema)
vnalpha init

# 2. Start vnstock-service (via Docker):
make up-vnstock

# 3. Sync symbols
vnalpha sync symbols

# 4. Sync OHLCV (last 365 days)
vnalpha sync ohlcv --start 2023-06-01 --end 2024-06-28

# 5. Build canonical OHLCV
vnalpha build canonical

# 6. Build feature snapshots
vnalpha build features --date 2024-06-28

# 7. Score and generate watchlist
vnalpha score --date 2024-06-28

# 8. Show watchlist table
vnalpha watchlist --date 2024-06-28

# 9. Launch TUI
vnalpha tui
```

## Running with Fixture Data (CI / Offline)

```bash
# Run tests — uses in-memory DuckDB, no live service required
make test-vnalpha

# Or:
cd vnalpha && python -m pytest tests/ -v
```

The E2E tests in `tests/test_e2e_pipeline.py` generate synthetic OHLCV data
for 3 symbols (FPT, VNM, HPG) and exercise the full pipeline without any
external dependencies.

## Running with Live vnstock-service

```bash
# Start the service
make up-vnstock

# Verify service is healthy
curl http://localhost:6900/health

# Run full pipeline
make sync && make features && make score

# Launch TUI
make tui
```

## CLI Command Reference

| Command | Description |
|---|---|
| `vnalpha init` | Create DuckDB warehouse schema |
| `vnalpha sync symbols` | Fetch symbols from vnstock-service → `symbol_master` |
| `vnalpha sync ohlcv` | Fetch OHLCV data → `market_ohlcv_raw` |
| `vnalpha build canonical` | Promote raw → `canonical_ohlcv` |
| `vnalpha build features --date DATE` | Compute features → `feature_snapshot` |
| `vnalpha score --date DATE` | Score symbols → `candidate_score` + `daily_watchlist` |
| `vnalpha watchlist --date DATE` | Display watchlist as Rich table |
| `vnalpha tui` | Launch Textual TUI |

## Candidate Class Ontology

Research-only classification. **Not trade signals.**

| Class | Meaning |
|---|---|
| `STRONG_CANDIDATE` | Composite score ≥ 0.70; strong trend + setup alignment |
| `WATCH_CANDIDATE` | Composite score ≥ 0.50; moderate setup — monitor for confirmation |
| `WEAK_CANDIDATE` | Composite score ≥ 0.30; marginal setup — low priority |
| `IGNORE` | Composite score < 0.30; insufficient evidence |

## Setup Type Ontology

| Setup | Pattern |
|---|---|
| `ACCUMULATION_BASE` | Tight base range near 52-week high |
| `BREAKOUT_ATTEMPT` | Near 52-week high + volume expansion |
| `MOMENTUM_CONTINUATION` | Uptrend + price extended above MA20 |
| `PULLBACK_TO_TREND` | Uptrend + close near MA20 (within 3%) |
| `MEAN_REVERSION` | Price below MA + volume expansion |
| `UNCLASSIFIED` | No clear pattern detected |

## Known Limitations (Phase 5)

1. **No live streaming** — data is batch-synced via CLI.
2. **Single interval** — 1D bars only; intraday not supported.
3. **VNINDEX benchmark** — relative strength is computed vs VNINDEX only.
4. **No persistence across warehouse resets** — re-run full pipeline after `init`.
5. **TUI requires textual** — `pip install textual` separately if not in venv.
6. **No real-time quality scoring** — quality flags are set during ingestion only.

## Deferred Work (Phase 5.8 / 5.9)

The following are explicitly out of scope for Phase 5 and documented for future phases:

- MCP tool server exposing watchlist and scoring to LLM agents (Phase 5.8)
- LLM narrative explanation of candidate setups (Phase 5.9)
- Automated backtesting of historical setups (Phase 6)
- Multi-interval feature computation (Phase 7)
