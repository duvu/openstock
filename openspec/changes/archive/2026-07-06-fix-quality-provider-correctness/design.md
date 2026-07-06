# Correctness Fixes for Data Quality and Provider Hardening

## Goals

This change must make the recently added quality/provider layers safe for real DataFrame shapes and consistent for downstream consumers.

The implementation must:

1. Respect global quality configuration.
2. Avoid runtime crashes caused by non-integer DataFrame indexes.
3. Make validation failures observable.
4. Normalize freshness metadata inputs.
5. Fix provider model type contracts.
6. Harden provider drift/comparison functions against invalid inputs.
7. Ensure contract tests fail on interface drift.
8. Add regression tests for every fix.

## Non-Goals

This change must not:

- add new providers
- call live provider endpoints in default CI
- change core provider fetching behavior unrelated to validation/diagnostics
- introduce strategy, signal, execution, or portfolio logic
- make quality validation default-on unless explicitly configured by environment or caller

## Design Decisions

## 1. Global Quality Config Must Work

Current behavior only validates when `validate=True` is passed explicitly. The corrected behavior must use config defaults when kwargs are absent.

Recommended dispatch logic:

```python
from vnstock.core.settings import get_config

_quality_cfg = get_config().quality
_validate = kwargs.pop("validate", _quality_cfg.enabled)
_quality_mode = kwargs.pop("quality_mode", _quality_cfg.mode)
```

Precedence order:

```text
explicit call kwargs > environment/global config > hardcoded defaults
```

Examples:

```python
# validate disabled unless global config enables it
Market().equity("FPT").ohlcv(...)

# always validate this call
Market().equity("FPT").ohlcv(..., validate=True)

# force-disable validation even if env enables it
Market().equity("FPT").ohlcv(..., validate=False)
```

## 2. Index-Safe Row Reporting

Quality rules must not assume that `df.index` labels are integers.

Forbidden pattern:

```python
for idx in df.index[mask]:
    row_index = int(idx)
```

Required pattern:

```python
positions = [pos for pos, bad in enumerate(mask.fillna(False).to_numpy()) if bad]
for pos in positions[:max_examples]:
    idx = df.index[pos]
    issue = QualityIssue(
        row_index=pos,
        context={"index_label": str(idx)},
    )
```

`row_index` must represent the 0-based positional row offset. The original index label may be stored in `context["index_label"]`.

Affected checks include at least:

- datetime parse
- duplicate time
- monotonic time
- future time
- OHLC consistency
- negative price/volume
- null/NaN/inf
- price scale
- price board duplicate symbol / band checks
- intraday match type / duplicate id / price / volume / session time

## 3. Observable Validation Failure

Validation should not crash normal data fetching in `warn` mode, but it also must not fail silently.

Behavior:

| Mode | Internal validation exception |
|---|---|
| `off` | no validation |
| `warn` | attach synthetic quality report and emit warning |
| `strict` | raise validation exception |

Synthetic issue code:

```text
QUALITY_VALIDATION_INTERNAL_ERROR
```

Synthetic report fields:

```python
ValidationReport(
    valid=False,
    dataset_type=dataset_type or "unknown",
    provider=provider,
    symbol=symbol,
    interval=None,
    row_count=len(df) if possible else 0,
    latest_time=None,
    freshness_status="unknown",
    errors=[QualityIssue(...)]
)
```

In `warn` mode, attach this report to `df.attrs["quality"]` if config allows `attach_report`.

## 4. Freshness Metadata Normalization

Freshness rules must accept:

- `datetime.datetime`
- `pandas.Timestamp`
- ISO datetime strings
- timezone-aware datetimes
- timezone-naive datetimes

Recommended helper:

```python
def _coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = pd.to_datetime(value)
        except Exception:
            return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    return None
```

All timestamps used for age comparison must be converted to UTC-aware datetimes.

## 5. Intraday Session Timezone Handling

Intraday session checks must use Vietnam local time before extracting hour/minute.

Recommended behavior:

```python
parsed = pd.to_datetime(df["time"], errors="coerce")
if parsed.dt.tz is not None:
    parsed = parsed.dt.tz_convert("Asia/Ho_Chi_Minh")
```

Timezone-naive values should be treated as already local unless explicit config says otherwise.

## 6. Provider Model Type Contracts

`ProviderComparisonReport.issues` must be typed as:

```python
issues: list[ProviderIssue] = field(default_factory=list)
```

`ProviderHealth.capabilities_checked` must remain:

```python
capabilities_checked: list[str] = field(default_factory=list)
```

`score_health()` must accept:

```python
capabilities_checked: list[str] | None = None
```

and pass:

```python
capabilities_checked=capabilities_checked or []
```

## 7. Provider Invalid Input Guards

`detect_drift()` must return a structured issue if input is invalid.

Example:

```python
if df is None or not isinstance(df, pd.DataFrame):
    return [
        ProviderIssue(
            code="DRIFT_INVALID_INPUT",
            severity="error",
            provider=provider,
            capability=dataset_type,
            message=f"Expected pandas DataFrame, got {type(df).__name__}.",
        )
    ]
```

`compare_ohlcv()` must return a non-comparable report with issue `COMPARE_INVALID_INPUT` when:

- input is not a dict
- any provider value is not a DataFrame
- required OHLCV columns are missing before comparison

## 8. Contract Tests Must Fail on Interface Drift

Provider contract tests must not skip when adapter import or method signature breaks.

Forbidden pattern:

```python
try:
    from provider import Adapter
    ...
except Exception:
    pytest.skip(...)
```

Required behavior:

```python
from provider import Adapter
...
```

If import/method invocation breaks, the contract test must fail.

## Regression Tests Required

Add tests for:

1. `VNSTOCK_QUALITY_ENABLED=true` enables validation without per-call `validate=True`.
2. `validate=False` overrides global enablement.
3. `quality_mode` falls back to config when not supplied.
4. OHLCV validator handles `DatetimeIndex` without crash.
5. temporal rules handle string index without crash.
6. intraday validator handles string index without crash.
7. freshness accepts ISO string `fetched_at`.
8. strict mode raises on internal validation exception.
9. warn mode attaches synthetic internal-error report.
10. `ProviderComparisonReport.issues` serializes `ProviderIssue` records correctly.
11. `score_health(..., capabilities_checked=[...])` preserves capability keys.
12. `detect_drift(None, ...)` returns `DRIFT_INVALID_INPUT`.
13. `compare_ohlcv({"A": None}, ...)` returns `COMPARE_INVALID_INPUT`.
14. DNSE contract test fails, not skips, when adapter interface is broken.

## CI Requirements

The final fix implementation must pass:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
```

Additionally, add targeted tests:

```bash
PYTHONPATH=. pytest tests/unit/core/quality tests/unit/core/provider tests/contracts/providers -q
```
