# Provider Hardening

The provider hardening layer makes provider outputs more observable and safer to use in data collection pipelines.

It lives under:

```text
vnstock/core/provider/
```

It does not fetch data by itself. It declares provider capabilities, detects schema drift, compares normalized provider outputs, scores provider health from collected evidence, and supports offline/live tests.

---

## Current Status

| Component | Module | Status |
|---|---|---:|
| Provider capability registry | `vnstock/core/provider/capabilities.py` | Implemented |
| Provider models | `vnstock/core/provider/models.py` | Implemented |
| Schema drift detection | `vnstock/core/provider/drift.py` | Implemented |
| OHLCV cross-provider comparison | `vnstock/core/provider/compare.py` | Implemented |
| Provider health scoring | `vnstock/core/provider/health.py` | Implemented |
| Capability matrix | `vnstock/core/provider/matrix.py` | Implemented |
| Offline contract tests | `tests/contracts/providers/` | Implemented |
| Live smoke tests | `tests/live/providers/` | Implemented, disabled by default |
| Health-aware runtime router | `vnstock/core/router.py` | Not yet integrated; router is still round-robin + cooldown |
| Price-board / intraday comparison | `compare.py` | Planned |

---

## Registered Providers

Provider capabilities currently cover the implemented data-source surface:

| Provider | Main use |
|---|---|
| KBS | Vietnam equity/index OHLCV, price board, intraday, reference/fundamental APIs |
| VCI | Vietnam equity/index OHLCV, price board, intraday, industry/index data |
| DNSE | Vietnam equity OHLCV and price board; intraday is treated as auth/availability constrained |
| TCBS | Vietnam equity OHLCV, price board, company reference, financial statements, symbol industry, screener (experimental); unofficial public endpoints — may drift |
| MSN | Global/search and selected global OHLCV use cases |
| FMP | Auth-gated global OHLCV via FMP API key |
| FMARKET | Fund NAV and fund data |

SSI and ABS are **not implemented providers**. They remain discovery candidates until public/credential strategy, raw samples, and contract feasibility are confirmed.

---

## Capability Registry

Use capability queries to inspect what a provider claims to support.

```python
from vnstock.core.provider.capabilities import query_capabilities

# All equity OHLCV providers
caps = query_capabilities(dataset_type="ohlcv", asset_class="equity")

# DNSE-specific capabilities
caps_dnse = query_capabilities(provider="DNSE")
```

Each capability is represented by `ProviderCapability`, including:

```text
provider
dataset_type
asset_class
method
intervals
supports_batch
supports_intraday
supports_history
supports_live_snapshot
requires_auth
is_live_testable
notes
```

Capability declarations are not a substitute for tests. They describe expected support and must be kept aligned with fixtures, live smoke checks, and actual provider behavior.

---

## Schema Drift Detection

`detect_drift()` compares a normalized provider DataFrame against a stored baseline schema.

```python
from vnstock.core.provider.drift import detect_drift

issues = detect_drift(df, provider="KBS", dataset_type="ohlcv")

for issue in issues:
    print(issue.severity, issue.code, issue.message)
```

Important issue codes:

| Code | Meaning |
|---|---|
| `DRIFT_INVALID_INPUT` | Non-DataFrame input or invalid provider argument |
| `DRIFT_NO_BASELINE` | No baseline registered for provider/dataset combination |
| `DRIFT_MISSING_COLUMN` | Required column missing from normalized output |
| `DRIFT_DTYPE_MISMATCH` | Column dtype differs from baseline expectation |
| `DRIFT_UNEXPECTED_NULLS` | Non-nullable field contains null values |
| `DRIFT_ROW_COUNT_LOW` | Too few rows relative to baseline expectation |
| `DRIFT_ROW_COUNT_HIGH` | Too many rows relative to baseline expectation |

Current limitation: drift detection checks schema and dtype shape. Value-level correctness should be handled by the data quality layer.

---

## Cross-Provider Comparison

Current implementation supports OHLCV comparison.

```python
from vnstock.core.provider.compare import compare_ohlcv

report = compare_ohlcv(
    {
        "KBS": kbs_df,
        "VCI": vci_df,
        "DNSE": dnse_df,
    },
    symbol="FPT",
    interval="1D",
    start="2024-01-01",
    end="2024-06-30",
)

print(report.comparable)
print(report.price_diff_summary)

for issue in report.issues:
    print(issue.code, issue.message)
```

Important issue codes:

| Code | Meaning |
|---|---|
| `COMPARE_INVALID_INPUT` | Input is not a dict or provider value is not a DataFrame |
| `COMPARE_INSUFFICIENT_PROVIDERS` | Fewer than two providers supplied |
| `COMPARE_COVERAGE_GAP` | Provider misses too many base-provider dates |
| `COMPARE_NO_COMMON_DATES` | Providers have no overlapping time index |
| `COMPARE_PRICE_DIVERGENCE` | Price difference exceeds warning threshold |
| `COMPARE_PRICE_DIVERGENCE_HIGH` | Price difference exceeds error threshold |
| `COMPARE_VOLUME_DIVERGENCE` | Volume difference exceeds warning threshold |

Current limitations:

- comparison is OHLCV-only
- price board comparison is planned
- intraday comparison is planned
- provider-specific tolerances should be expanded before using comparison as a production acceptance gate

---

## Provider Health Scoring

`score_health()` derives a `ProviderHealth` snapshot from collected issues and optional runtime evidence.

```python
from vnstock.core.provider.health import score_health

health = score_health(
    provider="KBS",
    issues=issues,
    latency_ms=250.0,
    error_rate=0.02,
    schema_status="ok",
    freshness_status="fresh",
    capabilities_checked=["ohlcv/equity", "price_board/equity"],
)

print(health.status)  # healthy | degraded | failing | unknown
```

Status rules are evidence-based:

| Evidence | Status effect |
|---|---|
| Error-severity issue | failing |
| High latency | degraded or failing depending threshold |
| High error rate | degraded or failing depending threshold |
| Warning-severity issue | degraded |
| No negative evidence | healthy |

Current limitation: this is not yet wired into runtime source selection. `vnstock/core/router.py` currently uses round-robin selection with provider cooldown after runtime failures.

---

## Offline Contract Tests

Offline provider contract tests live under:

```text
tests/contracts/providers/
```

They use stored fixtures under:

```text
tests/fixtures/providers/
```

Run:

```bash
PYTHONPATH=. pytest tests/contracts/providers -q
```

Offline contract tests should fail when adapter imports or normalized schema contracts drift. They should not silently skip broken provider interfaces.

---

## Live Smoke Tests

Live smoke tests live under:

```text
tests/live/providers/
```

They are disabled by default and require explicit env enablement:

```bash
VNSTOCK_LIVE_TESTS=true PYTHONPATH=. pytest tests/live/providers -m live -v
```

Filters:

```bash
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=DNSE pytest tests/live/providers -m live
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_SYMBOLS=FPT pytest tests/live/providers -m live
```

Live tests are not part of the default CI job. They are intended for manual or separately scheduled verification because they call real provider endpoints.

---

## Foreign Investor Data

Foreign investor fields are currently exposed mainly in price board snapshots:

```text
foreign_buy_volume
foreign_sell_volume
foreign_room
```

This is not yet a first-class `foreign_flow` dataset. A historical daily foreign-flow dataset should be added only after endpoint feasibility, fixtures, contract tests, and quality contracts are defined.

---

## Recommended Provider-Onboarding Gate

A new provider should not be merged until it has:

1. explicit data-only scope
2. no broker login/order/account APIs in core provider path
3. verified endpoint discovery or official API documentation
4. raw fixtures for core endpoints
5. normalized DataFrame schema
6. capability declarations
7. drift baselines
8. contract tests
9. live smoke tests if the endpoint can be tested safely
10. roadmap/docs updates

For credentialed official APIs, credentials must be supplied through environment variables or caller config. Never commit credentials or account-specific samples.

---

## Roadmap Notes

Next provider-hardening work:

- integrate provider health into router or batch diagnostics
- add price board comparison
- add intraday comparison
- add dedicated live smoke workflow
- add `foreign_flow` dataset discovery/spec
- expand quality contracts beyond market data into reference and fundamental datasets
