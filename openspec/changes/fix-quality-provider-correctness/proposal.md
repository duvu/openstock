## Why

The data quality layer and provider hardening layer now pass CI on the happy path, but review identified several correctness issues that can still cause silent validation skips, runtime crashes on realistic DataFrame indexes, and type-contract mismatches.

The most important risks are:

- `VNSTOCK_QUALITY_ENABLED=true` does not automatically enable validation in `BaseUI._dispatch()`.
- validator internals may crash when row labels are `DatetimeIndex`, string index, or `MultiIndex` because several rules call `int(idx)`.
- quality validation can silently fail and return the original DataFrame without any diagnostic report.
- freshness validation may fail when `df.attrs["fetched_at"]` is a serialized ISO string.
- provider hardening models and functions have inconsistent type contracts.
- provider drift/comparison utilities are not defensive against invalid adapter outputs.
- contract tests can skip instead of failing when provider interfaces drift.

This change specifies a corrective hardening pass before the quality/provider layers are used as a foundation for scanner or AI trading workflows.

## What Changes

- Make global quality config effective:
  - `VNSTOCK_QUALITY_ENABLED=true` must enable validation without requiring per-call `validate=True`.
  - `VNSTOCK_QUALITY_MODE` must be used when `quality_mode` is not supplied.
- Replace all unsafe `int(idx)` conversions in quality validators/rules with positional row offsets.
- Make quality validation failures observable instead of silently swallowed.
- Parse string `fetched_at` metadata before freshness calculations.
- Convert timezone-aware timestamps to Vietnam local time before session-time validation.
- Fix provider model type contracts:
  - `ProviderComparisonReport.issues` must be `list[ProviderIssue]`.
  - `ProviderHealth.capabilities_checked` and `score_health()` must agree on `list[str]`.
- Add invalid-input guards to provider drift and comparison utilities.
- Remove `pytest.skip` from provider contract tests when adapter import/interface changes.
- Add regression tests for all corrected behaviors.

## Capabilities

### Modified Capabilities

- `data-quality-layer`: validation must be globally configurable, index-safe, and failure-observable.
- `freshness-metadata`: freshness rules must accept string and datetime metadata safely.
- `provider-hardening`: provider models, drift detection, comparison, and contract tests must have consistent type/runtime behavior.
- `provider-contract-tests`: contract tests must fail on adapter/interface drift instead of skipping.

## Impact

Affected areas:

- `vnstock/ui/_base.py`
- `vnstock/core/quality/rules/temporal.py`
- `vnstock/core/quality/rules/freshness.py`
- `vnstock/core/quality/rules/numeric.py`
- `vnstock/core/quality/validators/ohlcv.py`
- `vnstock/core/quality/validators/intraday.py`
- `vnstock/core/quality/validators/price_board.py`
- `vnstock/core/provider/models.py`
- `vnstock/core/provider/health.py`
- `vnstock/core/provider/drift.py`
- `vnstock/core/provider/compare.py`
- `tests/unit/core/quality/`
- `tests/unit/core/provider/`
- `tests/contracts/providers/`

This change does not add new market data providers, order execution, trading strategy logic, portfolio management, charting, or live endpoint checks.
