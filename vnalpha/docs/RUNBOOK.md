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
# Full pipeline
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha sync index --symbol VNINDEX --start 2024-01-01
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui --date today
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

**Fixture-mode E2E test:**
```bash
cd vnalpha && pytest tests/test_phase5_e2e.py -q
```
This test runs the full pipeline in an isolated in-memory DuckDB — no network access required.

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

### Universe support

`vnalpha sync ohlcv` supports two ways to specify symbols:

- `--universe VN30` — resolves to the 32 VN30 index constituents (static list)
- `--symbols FPT,VNM,HPG` — explicit comma-separated symbols

Resolution order: `--symbols` takes precedence over `--universe`. If neither is given, all active symbols from the warehouse are synced.

**Phase 5 supported universes:** `VN30`

### Benchmark data (VNINDEX)

Relative strength features require benchmark OHLCV in `canonical_ohlcv`. Sync it explicitly:

    vnalpha sync index --symbol VNINDEX --start 2024-01-01
    vnalpha build canonical

If VNINDEX data is missing, features will compute with NaN relative strength values (a warning is logged).

### Score scale and thresholds

Scores are in the range **0.0 – 1.0**.

| Candidate class  | Score threshold |
|-----------------|----------------|
| STRONG_CANDIDATE | >= 0.70        |
| WATCH_CANDIDATE  | >= 0.50        |
| WEAK_CANDIDATE   | >= 0.30        |
| IGNORE           | < 0.30         |

Sub-score weights:
- Trend: 30%
- Relative strength: 25%
- Volume: 15%
- Base: 10%
- Breakout: 10%
- Risk quality: 10%

### Candidate class and setup type ontology

**Phase 5 canonical candidate classes:**
- `STRONG_CANDIDATE` — score >= 0.70
- `WATCH_CANDIDATE` — score >= 0.50
- `WEAK_CANDIDATE` — score >= 0.30
- `IGNORE` — score < 0.30 (excluded from watchlist)

**Phase 5 canonical setup types:**
- `ACCUMULATION_BASE` — tight base near 52-week high
- `BREAKOUT_ATTEMPT` — near 52-week high with volume expansion
- `MOMENTUM_CONTINUATION` — uptrend + price above MA
- `PULLBACK_TO_TREND` — uptrend + close near MA20
- `MEAN_REVERSION` — price below MA with volume expansion
- `UNCLASSIFIED` — no clear pattern

Legacy aliases (`STAGE1`, `STAGE2`, `BREAKOUT`, etc.) exist in code for backward compatibility but are **not accepted** in persisted data. The persistence guard raises `ValueError` if a non-canonical value is written.

### Known limitations and deferred work

**Phase 5 scope:**
- VN30 universe resolved from a static list. Current symbol-universe work is tracked through GitHub Issues.
- VNINDEX benchmark must be synced separately before feature build.
- TUI requires `textual` to be installed (`pip install textual`).
- Backtest Lab is outside this legacy runbook; current scope and dependencies are tracked in issue #108.
- No broker/order/portfolio integration (research-only, by design).

| Command | Description |
|---|---|
| `vnalpha init` | Create DuckDB warehouse schema |
| `vnalpha sync symbols` | Fetch symbols from vnstock-service → `symbol_master` |
| `vnalpha sync ohlcv` | Fetch OHLCV data → `market_ohlcv_raw` |
| `vnalpha build canonical` | Promote raw → `canonical_ohlcv` |
| `vnalpha build features --date DATE` | Compute features → `feature_snapshot` |
| `vnalpha score --date DATE` | Score symbols → `candidate_score` (authoritative) + `daily_watchlist` |
| `vnalpha watchlist --date DATE` | Display watchlist from persisted `candidate_score` as Rich table |
| `vnalpha tui [--date DATE]` | Launch Textual TUI (date defaults to today) |

**Date formats accepted:** `today` or ISO `YYYY-MM-DD`. Both `--date today` and `--date 2024-06-28` are valid.

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

## Troubleshooting

### Empty watchlist after `score`

**Symptom:** `vnalpha watchlist --date <date>` shows "No watchlist entries".

**Causes and fixes:**

1. **No feature snapshots for that date** — run `vnalpha build features --date <date>` first.
2. **All symbols scored as IGNORE** — check that canonical OHLCV has sufficient history (≥ 60 bars).
3. **All scores below min-score threshold** — try `vnalpha score --min-score 0.0 --date <date>`.
4. **Wrong date** — verify the date has data: `duckdb ~/.vnalpha/warehouse.duckdb -c "SELECT COUNT(*) FROM feature_snapshot WHERE date = '<date>'"`.

### Missing feature snapshots

**Symptom:** `build features` exits with `built: 0 symbols`.

**Causes and fixes:**

1. **No canonical OHLCV** — run `vnalpha build canonical` after syncing OHLCV.
2. **Insufficient history for moving averages** — ensure at least 100 days of OHLCV data exists.
3. **Wrong VNALPHA_WAREHOUSE_PATH** — check your `.env` points to the correct DuckDB file.

### Scoring version mismatch

If `lineage_json.scoring_version` in `candidate_score` does not match the current
`SCORING_VERSION` constant in `repositories.py`, re-run `vnalpha score` to refresh scores.
Historical scores are preserved as-is; only new `(symbol, date)` pairs are overwritten.

## Roadmap references

This runbook documents a historical Phase 5 operating surface; it does not schedule future work.

- Use [the unified roadmap](../../ROADMAP.md) and GitHub issue [#90](https://github.com/duvu/openstock/issues/90) for current priority and dependencies.
- Backtest Lab MVP scope is tracked in [#108](https://github.com/duvu/openstock/issues/108).
- Any remaining MCP, narrative, multi-interval or workspace work requires a focused GitHub issue before it enters the roadmap.
