# Tasks: Add Data Quality Layer

## 1. Core Models

- [x] Add `vnstock/core/quality/models.py`
- [x] Implement `QualityIssue`
- [x] Implement `ValidationReport`
- [x] Add serialization helpers: `to_dict()`, `to_json()`
- [x] Add tests for report validity and severity aggregation

## 2. Exceptions

- [x] Add `vnstock/core/quality/exceptions.py`
- [x] Implement `VnstockQualityError`
- [x] Implement `DataQualityError`
- [x] Implement `SchemaValidationError`
- [x] Implement `FreshnessError`
- [x] Add tests for strict mode exception behavior

## 3. Configuration

- [x] Add `QualityConfig` to `vnstock/core/settings.py`
- [x] Add environment variable parsing
- [x] Add defaults:
  - `enabled=False`
  - `mode="warn"`
  - `attach_report=True`
- [x] Add tests for config defaults and env overrides

## 4. Schema Rules

- [x] Add `vnstock/core/quality/rules/schema.py`
- [x] Implement required column validation
- [x] Implement dtype validation
- [x] Implement empty DataFrame validation
- [x] Implement all-null column validation

## 5. Numeric Rules

- [x] Add `vnstock/core/quality/rules/numeric.py`
- [x] Implement negative price checks
- [x] Implement negative volume checks
- [x] Implement null/NaN/inf checks
- [x] Implement suspicious price scale check

## 6. Temporal Rules

- [x] Add `vnstock/core/quality/rules/temporal.py`
- [x] Implement datetime parse validation
- [x] Implement duplicate time detection
- [x] Implement monotonic time validation
- [x] Implement future time detection
- [x] Add optional missing session validation

## 7. Freshness Rules

- [x] Add `vnstock/core/quality/rules/freshness.py`
- [x] Implement stale price board check
- [x] Implement stale intraday check
- [x] Implement stale daily OHLCV check
- [x] Implement missing latest timestamp warning

## 8. OHLCV Validator

- [x] Add `vnstock/core/quality/validators/ohlcv.py`
- [x] Validate required schema: `time`, `open`, `high`, `low`, `close`, `volume`
- [x] Validate OHLC consistency
- [x] Validate positive prices
- [x] Validate non-negative volume
- [x] Validate duplicate timestamps
- [x] Validate freshness metadata
- [x] Add unit tests

## 9. Price Board Validator

- [x] Add `vnstock/core/quality/validators/price_board.py`
- [x] Validate required minimum schema
- [x] Validate duplicate symbols
- [x] Validate floor/reference/ceiling consistency
- [x] Validate bid/ask consistency
- [x] Validate non-negative volume fields
- [x] Validate freshness metadata
- [x] Add unit tests

## 10. Intraday Trade Validator

- [x] Add `vnstock/core/quality/validators/intraday.py`
- [x] Validate required schema: `time`, `price`, `volume`, `match_type`, `id`
- [x] Validate match type enum
- [x] Validate duplicate trade IDs
- [x] Validate positive prices
- [x] Validate non-negative volumes
- [x] Add optional market session validation
- [x] Add unit tests

## 11. Validator Registry

- [x] Add `vnstock/core/quality/registry.py`
- [x] Register validators by dataset type
- [x] Implement `validate_dataframe(...)`
- [x] Add tests for unsupported dataset type behavior

## 12. UI/API Integration

- [x] Add `validate` and `quality_mode` kwargs handling in `BaseUI._dispatch`
- [x] Ensure quality kwargs do not leak into provider method calls
- [x] Attach `df.attrs["quality"]` when validation runs
- [x] Raise `DataQualityError` in strict mode
- [x] Add tests for `warn`, `strict`, and `off` modes

## 13. Provider Contract Tests

- [x] Add OHLCV sample contract tests for DNSE
- [x] Add OHLCV sample contract tests for KBS
- [x] Add OHLCV sample contract tests for VCI
- [x] Add price board sample contract tests
- [x] Add intraday sample contract tests

## 14. Documentation

- [x] Add docs page: `docs/DATA_QUALITY.md`
- [x] Document validation modes
- [x] Document issue codes
- [x] Document example usage
- [x] Document limitations
- [x] Add migration note for downstream scanner users
