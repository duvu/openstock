## Why

`vnstock` is being shaped into a data-only market data extraction library. For scanner, backtesting, and AI trading workflows, returning a `DataFrame` is not enough. Callers need to know whether returned data is structurally valid, complete enough, fresh enough, and safe to pass into downstream signal generation.

Provider responses may differ across KBS, VCI, DNSE, MSN, FMP, and FMarket. The same logical dataset can have different column names, price scale, timezone handling, missing sessions, duplicate rows, or stale values. Without a standard quality layer, downstream systems must repeatedly implement fragile validation logic.

This change introduces a reusable data quality layer for validating normalized market data before it is consumed by scanners, backtests, dashboards, or storage sinks.

## What Changes

- Add a new core data quality module under `vnstock/core/quality/`.
- Add standardized schema contracts for:
  - OHLCV bars
  - price board snapshots
  - intraday trades
  - reference/listing data
  - fundamental data
- Add a structured `ValidationReport` model.
- Add `validate=True|False` and `quality_mode="off"|"warn"|"strict"` support to eligible UI/API calls.
- Attach quality results to returned DataFrames via `df.attrs["quality"]` when validation runs.
- Add strict mode that raises typed exceptions when validation produces errors.
- Add unit tests and contract tests for OHLCV, price board, and intraday validation.
- Preserve backwards compatibility by keeping validation disabled by default unless explicitly configured or requested.

## Capabilities

### New Capabilities

- `data-quality-layer`: validate normalized market data using provider-independent schema and quality checks.
- `schema-contracts`: define reusable schema contracts for supported dataset types.
- `freshness-metadata`: attach freshness and validation metadata to returned DataFrames.

### Modified Capabilities

- `market-data-fetching`: market data methods may run validation automatically when requested by the caller or enabled by configuration.

## Impact

Affected areas:

- `vnstock/core/quality/`
- `vnstock/core/settings.py`
- `vnstock/ui/_base.py`
- `vnstock/api/quote.py`
- `vnstock/api/trading.py`
- provider explorers where applicable: KBS, VCI, DNSE, MSN, FMP
- tests under `tests/unit/core/quality/`
- contract tests under `tests/contracts/quality/`

This change does not add order execution, notification, charting, portfolio management, or strategy logic.
