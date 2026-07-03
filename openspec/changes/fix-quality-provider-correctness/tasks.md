# Tasks: Fix Quality and Provider Correctness Findings

## 1. Global Quality Config

- [x] Update `BaseUI._dispatch()` to load `get_config().quality` before popping quality kwargs
- [x] Make `validate` default to `get_config().quality.enabled`
- [x] Make `quality_mode` default to `get_config().quality.mode`
- [x] Preserve explicit per-call `validate=False` override
- [x] Preserve explicit per-call `quality_mode="off"|"warn"|"strict"` override
- [x] Add unit test: env-enabled validation runs without `validate=True`
- [x] Add unit test: `validate=False` disables validation even when env-enabled
- [x] Add unit test: `VNSTOCK_QUALITY_MODE=strict` raises on validation errors

## 2. Index-Safe Row Reporting

- [x] Replace all `row_index=int(idx)` patterns in quality layer
- [x] Add helper for positional issue iteration, e.g. `_iter_bad_positions(mask, max_examples)`
- [x] Store positional row offset in `QualityIssue.row_index`
- [x] Store original index label in `QualityIssue.context["index_label"]` where useful
- [x] Update temporal rules:
  - [x] datetime parse
  - [x] duplicate time
  - [x] monotonic time
  - [x] future time
- [x] Update numeric rules:
  - [x] negative price
  - [x] negative volume
  - [x] null/NaN/inf
  - [x] price scale
- [x] Update OHLCV validator consistency checks
- [x] Update price board validator checks
- [x] Update intraday validator checks
- [x] Add regression test: OHLCV validator with `DatetimeIndex`
- [x] Add regression test: temporal rules with string index
- [x] Add regression test: intraday validator with string index
- [x] Add regression test: price board validator with string index

## 3. Observable Internal Validation Failures

- [x] Add issue code `QUALITY_VALIDATION_INTERNAL_ERROR`
- [x] Add helper to create synthetic validation failure report
- [x] In warn mode, attach synthetic report to `df.attrs["quality"]` when validator raises unexpectedly
- [x] In warn mode, emit `UserWarning` for internal validation failures
- [x] In strict mode, re-raise unexpected validation exceptions or wrap them in `DataQualityError`
- [x] Do not silently `pass` unexpected validation errors
- [x] Add unit test: warn mode internal validator exception attaches synthetic report
- [x] Add unit test: strict mode internal validator exception raises

## 4. Freshness Metadata Normalization

- [x] Add `_coerce_datetime(value)` helper in `freshness.py`
- [x] Accept `datetime.datetime`
- [x] Accept `pandas.Timestamp`
- [x] Accept ISO datetime strings
- [x] Return `None` for unparseable values instead of crashing
- [x] Normalize all comparison timestamps to UTC-aware datetimes
- [x] Add unit test: `df.attrs["fetched_at"]` as ISO string
- [x] Add unit test: timezone-naive `fetched_at`
- [x] Add unit test: invalid string `fetched_at` returns missing metadata warning

## 5. Intraday Session Timezone Handling

- [x] Convert timezone-aware timestamps to `Asia/Ho_Chi_Minh` before session checks
- [x] Treat timezone-naive timestamps as already local by default
- [x] Add unit test: UTC timestamp corresponding to 09:15 ICT is inside session
- [x] Add unit test: UTC timestamp corresponding to 08:00 ICT is outside session
- [x] Add unit test: timezone-naive 09:15 is inside session

## 6. Provider Model Type Fixes

- [x] Change `ProviderComparisonReport.issues` from `list[str]` to `list[ProviderIssue]`
- [x] Ensure `ProviderComparisonReport.to_dict()` serializes issue objects safely
- [x] Ensure `ProviderComparisonReport.to_json()` serializes issue objects safely
- [x] Change `score_health()` signature to `capabilities_checked: list[str] | None = None`
- [x] Pass `capabilities_checked=capabilities_checked or []` into `ProviderHealth`
- [x] Update health tests for capability key preservation
- [x] Update comparison report serialization tests

## 7. Provider Invalid Input Guards

- [x] Add `DRIFT_INVALID_INPUT` guard in `detect_drift()`
- [x] Guard against `None`
- [x] Guard against non-DataFrame objects
- [x] Add `COMPARE_INVALID_INPUT` guard in `compare_ohlcv()`
- [x] Guard against non-dict input
- [x] Guard against dict values that are not DataFrames
- [x] Guard against missing required OHLCV columns before `.copy()`, `pd.to_datetime`, and `.set_index()`
- [x] Add unit test: `detect_drift(None, ...)`
- [x] Add unit test: `detect_drift({})`
- [x] Add unit test: `compare_ohlcv(None, ...)`
- [x] Add unit test: `compare_ohlcv({"DNSE": None}, ...)`
- [x] Add unit test: `compare_ohlcv()` with missing `time` column

## 8. Provider Contract Tests Must Fail on Interface Drift

- [x] Remove broad `try/except Exception: pytest.skip(...)` blocks from contract tests
- [x] Ensure adapter imports fail the test if module path changes
- [x] Ensure method signature changes fail the test
- [x] Add explicit skip only for intentionally optional live tests, not offline contract tests
- [x] Add grep/regression check or test asserting no `pytest.skip` in `tests/contracts/providers/` for adapter failures

## 9. Documentation Updates

- [x] Update `docs/DATA_QUALITY.md` to explain global env behavior
- [x] Document `QUALITY_VALIDATION_INTERNAL_ERROR`
- [x] Document `row_index` as positional offset, not index label
- [x] Document original label in `context["index_label"]`
- [x] Update `docs/PROVIDER_HARDENING.md` for structured `ProviderIssue` comparison reports
- [x] Document invalid input issue codes:
  - `DRIFT_INVALID_INPUT`
  - `COMPARE_INVALID_INPUT`
  - `COMPARE_MISSING_COLUMN` if implemented

## 10. Verification

- [x] Run `ruff check .`
- [x] Run `ruff format --check .`
- [x] Run `PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts`
- [x] Run `PYTHONPATH=. pytest tests/unit/core/quality tests/unit/core/provider tests/contracts/providers -q`
- [x] Run `python -m build --sdist --wheel --no-isolation`
- [x] Confirm CI passes on Python 3.10, 3.11, 3.12, 3.13
- [x] Confirm no unresolved high-priority review findings remain
