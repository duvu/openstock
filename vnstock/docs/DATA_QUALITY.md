# Data Quality Layer

The data quality layer validates normalized market-data `DataFrame` outputs before they are consumed by downstream ingestion, storage, comparison, or scanner workflows.

It lives under:

```text
vnstock/core/quality/
```

It is designed for **diagnostics and safety**, not data repair. Validators report issues; they do not mutate or fix market data values.

---

## Current Status

| Dataset | Status |
|---|---|
| `ohlcv` | Implemented |
| `price_board` | Implemented |
| `intraday_trades` | Implemented |
| `reference` | Planned |
| `fundamental` | Planned |

The first implemented scope is market data because it is the foundation for provider comparison, ingestion, storage, and scanner workflows.

---

## Enabling Validation

Validation is disabled by default.

Per-call enablement:

```python
from vnstock import Market

market = Market()

df = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    validate=True,
    quality_mode="warn",
)

report = df.attrs.get("quality")
```

Global enablement:

```bash
export VNSTOCK_QUALITY_ENABLED=true
export VNSTOCK_QUALITY_MODE=warn
export VNSTOCK_QUALITY_ATTACH_REPORT=true
```

Supported modes:

| Mode | Behavior |
|---|---|
| `off` | Do not run validation |
| `warn` | Run validation, attach report, emit warnings, return data |
| `strict` | Run validation and raise on errors |

Per-call kwargs override global environment config.

---

## Environment Variables

| Variable | Default | Meaning |
|---|---:|---|
| `VNSTOCK_QUALITY_ENABLED` | `false` | Enable validation by default |
| `VNSTOCK_QUALITY_MODE` | `warn` | `off`, `warn`, or `strict` |
| `VNSTOCK_QUALITY_ATTACH_REPORT` | `true` | Attach `ValidationReport` to `df.attrs["quality"]` |
| `VNSTOCK_QUALITY_STALE_PRICE_BOARD_SECONDS` | `30` | Freshness threshold for price board snapshots |
| `VNSTOCK_QUALITY_STALE_INTRADAY_SECONDS` | `60` | Freshness threshold for intraday data |
| `VNSTOCK_QUALITY_STALE_DAILY_OHLCV_HOURS` | `36` | Freshness threshold for daily OHLCV |
| `VNSTOCK_QUALITY_CHECK_MISSING_SESSIONS` | `true` | Enable expected-session checks where inputs are provided |
| `VNSTOCK_QUALITY_CHECK_SESSION_TIME` | `false` | Enable intraday session-time checks |

---

## Report Model

Validators return a `ValidationReport` with issue buckets:

```text
valid
errors
warnings
infos
row_count
latest_time
freshness_status
provider
symbol
interval
```

Returned DataFrames can carry the report:

```python
report = df.attrs.get("quality")

if report and not report.valid:
    for issue in report.errors:
        print(issue.code, issue.message)
```

`QualityIssue.row_index` is a 0-based positional row offset. If the original DataFrame index is meaningful, validators may also attach the original label in `issue.context["index_label"]`.

---

## OHLCV Validation

Dataset type:

```text
ohlcv
```

Expected core columns:

```text
time, open, high, low, close, volume
```

Main checks:

- required columns
- empty DataFrame
- timestamp parseability
- duplicate timestamps
- monotonic time order
- future timestamps
- negative prices or volume
- null/NaN/inf values
- OHLC consistency:
  - `high >= low`
  - `high >= open`
  - `high >= close`
  - `low <= open`
  - `low <= close`
- price-scale suspiciousness
- daily freshness threshold

---

## Price Board Validation

Dataset type:

```text
price_board
```

Required columns:

```text
symbol, reference_price, close_price, volume_accumulated
```

Recognized optional fields include:

```text
ceiling_price
floor_price
open_price
high_price
low_price
bid_price_1
ask_price_1
bid_vol_1
ask_vol_1
foreign_buy_volume
foreign_sell_volume
```

Main checks:

- required columns
- empty DataFrame
- duplicate symbols
- floor/reference/ceiling consistency
- close price within price band
- crossed bid/ask
- non-negative volume fields
- price-board freshness

Foreign investor snapshot fields are validated as non-negative volume fields when present. These are not yet a historical foreign-flow time-series dataset.

---

## Intraday Trade Validation

Dataset type:

```text
intraday_trades
```

Expected core columns:

```text
time, price, volume, match_type, id
```

Main checks:

- required columns
- duplicate trade ids
- invalid match type
- non-positive price
- negative volume
- optional session-time validation

Timezone-aware timestamps are converted to Vietnam local time before session-time checks. Timezone-naive timestamps are treated as already local.

---

## Internal Validation Failures

Unexpected validator errors must not silently disappear.

Behavior:

| Mode | Internal validation exception |
|---|---|
| `off` | No validation is run |
| `warn` | Attach synthetic report and emit warning |
| `strict` | Raise an exception |

Synthetic issue code:

```text
QUALITY_VALIDATION_INTERNAL_ERROR
```

This is a signal that the validator itself failed, not necessarily that the market data is invalid.

---

## Current Limitations

- Validators do not repair data.
- Trading calendar support is not yet first-class; missing-session checks depend on caller-supplied expected dates.
- Reference and fundamental datasets do not yet have first-class validators.
- Foreign investor data exists mainly as price board snapshot fields, not historical daily time-series.
- Intraday session-time checks are disabled by default because pre-open, ATC, and post-close data can be legitimate depending on use case.

---

## Recommended Usage in Data Collection

For ingestion pipelines, prefer:

```python
df = market.equity.ohlcv(..., validate=True, quality_mode="warn")
report = df.attrs.get("quality")

# Persist data and report together.
```

For strict controlled jobs, use:

```python
df = market.equity.ohlcv(..., validate=True, quality_mode="strict")
```

For live snapshots where stale data is unacceptable, either disable cache or set a short TTL and keep validation enabled.

---

## Next Work

Planned extensions:

- reference data quality contracts
- fundamental statement quality contracts
- dedicated `foreign_flow` dataset quality contract
- storage of quality reports alongside ingested data
- data-quality dashboards for ingestion runs
