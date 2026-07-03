# Provider Hardening Design

## Goals

Provider hardening must ensure that providers remain safe to use as interchangeable market-data sources.

The system must:

1. Verify provider adapters against stored golden samples.
2. Optionally verify real provider endpoints using live smoke tests.
3. Detect raw response schema drift.
4. Detect normalized DataFrame schema drift.
5. Compare overlapping providers for the same capability.
6. Produce provider health status and capability metadata.
7. Integrate provider health with router/fallback decisions.
8. Keep all live network tests opt-in.

## Non-Goals

Provider hardening must not:

- certify data as official exchange data
- guarantee investment correctness
- execute trades
- perform strategy evaluation
- replace the data quality layer
- require network access during normal CI

## Proposed Package Structure

```text
vnstock/core/provider/
├── __init__.py
├── capabilities.py
├── contracts.py
├── drift.py
├── health.py
├── compare.py
└── models.py
```

Test and fixture structure:

```text
tests/
├── fixtures/
│   └── providers/
│       ├── dnse/
│       │   ├── ohlcv_daily_raw.json
│       │   ├── ohlcv_daily_normalized.parquet
│       │   ├── price_board_raw.json
│       │   └── intraday_raw.json
│       ├── kbs/
│       └── vci/
├── contracts/
│   └── providers/
│       ├── test_dnse_contracts.py
│       ├── test_kbs_contracts.py
│       ├── test_vci_contracts.py
│       └── test_cross_provider_contracts.py
└── live/
    └── providers/
        ├── test_dnse_live.py
        ├── test_kbs_live.py
        └── test_vci_live.py
```

## Provider Capability Model

Each provider should declare supported capabilities in a structured form.

```python
@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    dataset_type: str
    asset_class: str
    method: str
    intervals: list[str]
    supports_batch: bool = False
    supports_intraday: bool = False
    supports_history: bool = False
    supports_live_snapshot: bool = False
    requires_auth: bool = False
    is_live_testable: bool = True
    notes: str | None = None
```

Example:

```python
ProviderCapability(
    provider="DNSE",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    requires_auth=False,
)
```

## Provider Health Model

```python
@dataclass
class ProviderHealth:
    provider: str
    status: Literal["healthy", "degraded", "failing", "unknown"]
    checked_at: datetime
    capabilities_checked: list[str]
    latency_ms: float | None
    error_rate: float | None
    schema_status: Literal["compatible", "drifted", "unknown"]
    freshness_status: Literal["fresh", "stale", "unknown"]
    issues: list[str]
```

Status rules:

| Status | Meaning |
|---|---|
| `healthy` | endpoint reachable, schema compatible, data fresh enough |
| `degraded` | endpoint reachable but has warnings, stale data, high latency, or partial schema differences |
| `failing` | endpoint unavailable, response invalid, schema incompatible, or repeated errors |
| `unknown` | no recent health check available |

## Contract Tests

Contract tests validate provider adapters using stored raw samples.

They must verify:

- raw fixture can be parsed
- normalized output has expected schema
- normalized output has stable column names
- normalized output has expected core dtypes
- metadata attrs are present where required
- provider-specific quirks are documented

Contract tests must not call live provider endpoints.

## Live Smoke Tests

Live tests verify real provider availability and compatibility.

Live tests must:

- be disabled by default
- require explicit marker or env flag
- use a small fixed symbol set such as `FPT`, `VCB`, `TCB`
- limit date ranges and request size
- avoid provider abuse
- fail loudly on schema incompatibility
- classify endpoint issues as provider health problems, not unit test failures in normal CI

Recommended flags:

```text
VNSTOCK_LIVE_TESTS=false
VNSTOCK_LIVE_PROVIDERS=DNSE,KBS,VCI
VNSTOCK_LIVE_SYMBOLS=FPT,VCB,TCB
```

Pytest markers:

```text
contract
live
provider
provider_dnse
provider_kbs
provider_vci
```

## Schema Drift Detection

Schema drift detection must compare actual schemas against known contracts.

### Raw response drift

Raw response drift checks should compare:

- top-level JSON type
- top-level keys
- nested data keys where applicable
- array lengths for OHLCV array-of-arrays responses
- required raw fields used by the adapter

### Normalized schema drift

Normalized schema drift checks should compare:

- column names
- required columns
- optional columns
- dtype categories
- index shape
- DataFrame attrs contract

Drift levels:

| Level | Meaning |
|---|---|
| `none` | no incompatible change |
| `minor` | optional field added or harmless type broadening |
| `major` | required field missing, required dtype incompatible, parser cannot normalize |

## Cross-Provider Comparison

Cross-provider comparison must compare overlapping capabilities across providers.

Initial supported comparisons:

```text
equity OHLCV daily: KBS vs VCI vs DNSE
equity price_board: KBS vs VCI vs DNSE
equity intraday trades: KBS vs VCI vs DNSE where available
index OHLCV: KBS vs VCI
```

Example API:

```python
from vnstock.core.provider.compare import compare_ohlcv

report = compare_ohlcv(
    symbol="FPT",
    start="2026-01-01",
    end="2026-07-02",
    interval="1D",
    providers=["KBS", "VCI", "DNSE"],
    tolerances={"price_pct": 0.01, "volume_pct": 0.05},
)
```

Comparison report:

```python
@dataclass
class ProviderComparisonReport:
    dataset_type: str
    symbol: str
    providers: list[str]
    comparable: bool
    base_provider: str
    row_count_by_provider: dict[str, int]
    missing_dates_by_provider: dict[str, list[str]]
    price_diff_summary: dict[str, Any]
    volume_diff_summary: dict[str, Any]
    issues: list[str]
```

## Router Integration

The provider router currently supports round-robin and cooldown behavior. Provider hardening should allow the router to skip providers that are known to be failing.

Proposed router behavior:

```text
healthy providers → preferred
degraded providers → allowed only if no healthy provider is available
failing providers → skipped unless forced by caller
unknown providers → allowed by default but flagged
```

Caller override:

```python
df = Market().equity("FPT").ohlcv(
    source="DNSE",
    ignore_provider_health=True,
)
```

## Provider Capability Matrix

The system should generate a provider capability matrix from provider declarations and tests.

Output formats:

```text
docs/PROVIDER_MATRIX.md
artifacts/provider_matrix.json
```

Example fields:

```text
provider
dataset_type
asset_class
method
intervals
contract_test_status
live_test_status
last_live_check
notes
```

## Failure Handling

Provider hardening must distinguish:

- provider unreachable
- HTTP error
- rate limited
- response schema drift
- normalized schema drift
- stale data
- partial data
- empty but valid data
- unsupported capability

These should be expressed as structured issue codes rather than only free-text errors.

## CI Strategy

Normal CI:

```bash
pytest tests/contracts/providers -m "contract and not live"
```

Live smoke checks, manually or scheduled:

```bash
VNSTOCK_LIVE_TESTS=true pytest tests/live/providers -m live
```

Live tests should not be required for merging routine code changes unless the PR changes provider adapter logic.

## Compatibility

Provider hardening should not change public market data method signatures unless optional diagnostic flags are added.

Recommended optional flags:

```python
check_provider_health: bool = False
ignore_provider_health: bool = False
include_provider_diagnostics: bool = False
```

Default behavior should remain compatible with existing callers.
