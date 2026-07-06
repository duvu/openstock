# Data Quality Layer Design

## Goals

The data quality layer must:

1. Validate that returned data matches the expected schema.
2. Detect common data defects before downstream usage.
3. Report quality issues in a structured, machine-readable format.
4. Work across multiple providers.
5. Support both non-blocking warning mode and blocking strict mode.
6. Avoid introducing strategy-specific trading logic.

## Non-Goals

The data quality layer must not:

- decide buy/sell signals
- repair data silently without reporting
- execute trades
- perform portfolio risk management
- guarantee correctness of third-party provider data
- replace a licensed official market data feed

## Proposed Package Structure

```text
vnstock/core/quality/
├── __init__.py
├── base.py
├── config.py
├── exceptions.py
├── models.py
├── registry.py
├── validators/
│   ├── __init__.py
│   ├── ohlcv.py
│   ├── price_board.py
│   ├── intraday.py
│   ├── reference.py
│   └── fundamental.py
└── rules/
    ├── __init__.py
    ├── schema.py
    ├── temporal.py
    ├── numeric.py
    └── freshness.py
```

## Core Concepts

### Dataset Types

```python
DatasetType = Literal[
    "ohlcv",
    "price_board",
    "intraday_trades",
    "reference",
    "fundamental",
]
```

### Severity

```python
Severity = Literal["info", "warning", "error"]
```

### Quality Mode

```python
QualityMode = Literal["off", "warn", "strict"]
```

| Mode | Behavior |
|---|---|
| `off` | No validation |
| `warn` | Run validation, attach report to `df.attrs["quality"]`, do not raise |
| `strict` | Run validation, raise exception if report contains errors |

## Public API

### Function-level API

```python
from vnstock.core.quality import validate_dataframe

report = validate_dataframe(
    df,
    dataset_type="ohlcv",
    provider="DNSE",
    symbol="FPT",
    interval="1D",
)
```

### UI/API usage

```python
df = Market().equity("FPT").ohlcv(
    start="2025-01-01",
    end="2026-07-02",
    source="DNSE",
    validate=True,
    quality_mode="warn",
)

quality = df.attrs["quality"]
```

### Strict mode

```python
df = Market().equity("FPT").ohlcv(
    start="2025-01-01",
    end="2026-07-02",
    source="DNSE",
    validate=True,
    quality_mode="strict",
)
```

If validation fails with errors, raise `DataQualityError(report)`.

## Validation Report

```python
@dataclass
class QualityIssue:
    code: str
    severity: str
    message: str
    column: str | None = None
    row_index: int | None = None
    value: Any | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    valid: bool
    dataset_type: str
    provider: str | None
    symbol: str | None
    interval: str | None
    row_count: int
    latest_time: str | None
    freshness_status: str
    errors: list[QualityIssue]
    warnings: list[QualityIssue]
    infos: list[QualityIssue]

    @property
    def severity(self) -> str:
        if self.errors:
            return "error"
        if self.warnings:
            return "warning"
        return "info"
```

## Standard Issue Codes

### Schema Codes

```text
SCHEMA_MISSING_COLUMN
SCHEMA_UNEXPECTED_COLUMN
SCHEMA_EMPTY_DATAFRAME
SCHEMA_INVALID_DTYPE
SCHEMA_COLUMN_ALL_NULL
```

### Temporal Codes

```text
TIME_MISSING
TIME_INVALID
TIME_DUPLICATED
TIME_NOT_MONOTONIC
TIME_FUTURE_VALUE
TIME_MISSING_SESSIONS
TIME_TIMEZONE_AMBIGUOUS
```

### Numeric Codes

```text
NUMERIC_NEGATIVE_PRICE
NUMERIC_NEGATIVE_VOLUME
NUMERIC_ZERO_VOLUME
NUMERIC_NULL_VALUE
NUMERIC_INF_VALUE
```

### OHLCV Codes

```text
OHLC_HIGH_BELOW_LOW
OHLC_HIGH_BELOW_OPEN
OHLC_HIGH_BELOW_CLOSE
OHLC_LOW_ABOVE_OPEN
OHLC_LOW_ABOVE_CLOSE
OHLC_PRICE_SCALE_SUSPICIOUS
```

### Price Board Codes

```text
BOARD_DUPLICATE_SYMBOL
BOARD_PRICE_OUTSIDE_FLOOR_CEILING
BOARD_BID_ASK_CROSSED
BOARD_NEGATIVE_BID_VOLUME
BOARD_NEGATIVE_ASK_VOLUME
BOARD_MISSING_REFERENCE_PRICE
```

### Intraday Codes

```text
TRADE_DUPLICATE_ID
TRADE_SYNTHETIC_ID
TRADE_INVALID_MATCH_TYPE
TRADE_NON_POSITIVE_PRICE
TRADE_NEGATIVE_VOLUME
TRADE_TIME_OUTSIDE_SESSION
```

### Freshness Codes

```text
FRESHNESS_STALE
FRESHNESS_LATEST_TIME_MISSING
FRESHNESS_FETCHED_AT_MISSING
```

## Dataset Contracts

### OHLCV Contract

Required columns:

```text
time
open
high
low
close
volume
```

Rules:

- `time` must be parseable as datetime.
- `time` must not contain duplicates for the same symbol and interval.
- `time` should be monotonic increasing after normalization.
- `open`, `high`, `low`, `close` must be numeric.
- `volume` must be numeric.
- Price values must be positive.
- Volume must be greater than or equal to zero.
- `high >= low`.
- `high >= open`.
- `high >= close`.
- `low <= open`.
- `low <= close`.
- Latest data time must not be stale beyond configured threshold.
- For daily OHLCV, missing trading sessions should be warnings unless a trading calendar is provided.

### Price Board Contract

Required minimum columns:

```text
symbol
reference_price
close_price
volume_accumulated
```

Recommended columns:

```text
ceiling_price
floor_price
open_price
high_price
low_price
price_change
percent_change
bid_price_1
bid_vol_1
ask_price_1
ask_vol_1
foreign_buy_volume
foreign_sell_volume
foreign_room
```

Rules:

- `symbol` must be non-empty.
- Each symbol should appear once.
- Price columns must be numeric if present.
- Volume columns must be non-negative if present.
- `floor_price <= reference_price <= ceiling_price` if all are present.
- `floor_price <= close_price <= ceiling_price` if all are present.
- Best bid should be less than or equal to best ask when both exist and are non-zero.
- Data must contain freshness metadata when used for live/intraday scanner.

### Intraday Trades Contract

Required columns:

```text
time
price
volume
match_type
id
```

Rules:

- `time` must be parseable as time or datetime.
- `price` must be positive.
- `volume` must be non-negative.
- `match_type` must be one of `buy`, `sell`, `unknown`, `ato`, `atc`.
- `id` should be unique when provided by provider.
- If `id` is synthesized, report an info issue.
- Trade time should be inside configured market session unless session validation is disabled.

## Configuration

Add to `vnstock/core/settings.py`:

```python
@dataclass
class QualityConfig:
    enabled: bool = False
    mode: str = "warn"
    attach_report: bool = True
    max_error_examples: int = 20

    stale_price_board_seconds: int = 30
    stale_intraday_seconds: int = 60
    stale_daily_ohlcv_hours: int = 36

    check_missing_sessions: bool = True
    check_ohlc_consistency: bool = True
    check_price_scale: bool = True
    check_session_time: bool = False
```

Environment variables:

```text
VNSTOCK_QUALITY_ENABLED=false
VNSTOCK_QUALITY_MODE=warn
VNSTOCK_QUALITY_ATTACH_REPORT=true
VNSTOCK_QUALITY_STALE_PRICE_BOARD_SECONDS=30
VNSTOCK_QUALITY_STALE_INTRADAY_SECONDS=60
VNSTOCK_QUALITY_STALE_DAILY_OHLCV_HOURS=36
VNSTOCK_QUALITY_CHECK_MISSING_SESSIONS=true
VNSTOCK_QUALITY_CHECK_SESSION_TIME=false
```

## Integration Point

Validation should run after provider dispatch and before returning the result to caller.

Proposed flow:

```text
BaseUI._dispatch()
→ provider execution
→ DataFrame result
→ optional cache write
→ optional quality validation
→ attach df.attrs["quality"]
→ return DataFrame
```

For cached responses, validation behavior must be explicit:

| Case | Behavior |
|---|---|
| cache hit + report already attached | return existing report |
| cache hit + no report + validate=True | validate cached DataFrame |
| cache hit + stale cache metadata | add freshness warning |

## Exception Model

```python
class VnstockQualityError(Exception):
    pass

class DataQualityError(VnstockQualityError):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__(f"Data quality validation failed: {report.severity}")

class SchemaValidationError(DataQualityError):
    pass

class FreshnessError(DataQualityError):
    pass
```

## Performance Considerations

Validation must be lightweight for normal use.

Rules:

- Validate only supported dataset types.
- Avoid expensive checks unless enabled.
- Limit row-level issue examples using `max_error_examples`.
- Do not mutate source data except for optional sorting if explicitly requested.
- Use vectorized pandas checks where possible.

## Compatibility

Default behavior should avoid breaking existing users.

Recommended default:

```text
VNSTOCK_QUALITY_ENABLED=false
```

Caller can enable per call:

```python
df = quote.history(..., validate=True)
```

Future releases may enable `warn` mode by default after stability is proven.
