# Capability: Correctness Fixes for Quality and Provider Hardening

## Requirement: Global quality configuration is honored

The system SHALL honor global quality configuration when per-call validation kwargs are absent.

### Scenario: Environment enables validation globally

Given `VNSTOCK_QUALITY_ENABLED=true`
And the caller does not pass `validate`
When a supported UI/API method returns a DataFrame
Then quality validation SHALL run
And the returned DataFrame SHALL include `df.attrs["quality"]` when report attachment is enabled.

### Scenario: Explicit validate false overrides global enablement

Given `VNSTOCK_QUALITY_ENABLED=true`
And the caller passes `validate=False`
When a supported UI/API method returns a DataFrame
Then quality validation SHALL NOT run
And no validation report is required.

### Scenario: Quality mode comes from config

Given `VNSTOCK_QUALITY_MODE=strict`
And the caller does not pass `quality_mode`
When validation runs and produces errors
Then the system SHALL behave as strict mode and raise `DataQualityError`.

## Requirement: Quality validation is index-safe

The system SHALL not assume DataFrame index labels are integers.

### Scenario: OHLCV validator receives DatetimeIndex

Given an OHLCV DataFrame with a `DatetimeIndex`
And at least one row violates an OHLC consistency rule
When the OHLCV validator runs
Then it SHALL return a `ValidationReport`
And it SHALL NOT raise `TypeError` or `ValueError` from converting the index label to int
And issue `row_index` SHALL contain the 0-based positional row offset.

### Scenario: Temporal rule receives string index

Given a DataFrame with a string index
And an invalid timestamp value
When temporal validation runs
Then it SHALL report `TIME_INVALID`
And it SHALL NOT raise from `int(idx)` conversion.

### Scenario: Intraday validator receives string index

Given an intraday trades DataFrame with a string index
And an invalid `match_type`
When intraday validation runs
Then it SHALL report `TRADE_INVALID_MATCH_TYPE`
And it SHALL NOT raise from index conversion.

## Requirement: Validation internal failures are observable

The system SHALL not silently swallow validation internal failures.

### Scenario: Warn mode internal validation failure

Given `quality_mode="warn"`
And validation raises an unexpected internal exception
When `_run_quality_validation` handles the exception
Then the original DataFrame SHALL still be returned
And the DataFrame SHALL include `df.attrs["quality"]` when report attachment is enabled
And the report SHALL contain error code `QUALITY_VALIDATION_INTERNAL_ERROR`.

### Scenario: Strict mode internal validation failure

Given `quality_mode="strict"`
And validation raises an unexpected internal exception
When `_run_quality_validation` handles the exception
Then the system SHALL raise an exception rather than silently returning unvalidated data.

## Requirement: Freshness metadata is robustly parsed

The system SHALL accept common serialized timestamp formats for freshness metadata.

### Scenario: fetched_at is ISO string

Given a DataFrame with `df.attrs["fetched_at"]` set to an ISO datetime string
When freshness validation runs
Then the system SHALL parse the string into a timestamp
And it SHALL NOT raise `AttributeError` from accessing `.tzinfo` on a string.

### Scenario: fetched_at is timezone-naive datetime

Given `fetched_at` is a timezone-naive datetime
When freshness validation runs
Then the timestamp SHALL be treated as UTC or converted according to documented behavior
And freshness age SHALL be computed without timezone comparison errors.

## Requirement: Intraday session validation uses Vietnam local time

The system SHALL evaluate market session windows using Vietnam local time.

### Scenario: Intraday timestamp is UTC timezone-aware

Given an intraday timestamp such as `2026-07-02T02:15:00Z`
When session validation runs
Then the timestamp SHALL be converted to `Asia/Ho_Chi_Minh` before hour/minute extraction
And a valid 09:15 ICT trade SHALL NOT be flagged outside the session.

### Scenario: Intraday timestamp is timezone-naive

Given an intraday timestamp without timezone information
When session validation runs
Then the timestamp SHALL be treated as already local time unless otherwise configured.

## Requirement: Provider comparison report uses structured issues

The system SHALL use structured `ProviderIssue` objects in provider comparison reports.

### Scenario: compare_ohlcv emits insufficient-provider issue

Given `compare_ohlcv()` receives fewer than two providers
When it returns `ProviderComparisonReport`
Then `report.issues` SHALL be a list of `ProviderIssue` objects
And `report.to_dict()` / `report.to_json()` SHALL serialize those issues correctly.

## Requirement: Provider health capability contract is consistent

The system SHALL keep `ProviderHealth.capabilities_checked` and `score_health()` aligned.

### Scenario: score health with capability keys

Given `score_health()` receives `capabilities_checked=["ohlcv/equity", "price_board/equity"]`
When it returns `ProviderHealth`
Then `health.capabilities_checked` SHALL contain the same list of strings.

### Scenario: score health without capability keys

Given `score_health()` receives no `capabilities_checked` argument
When it returns `ProviderHealth`
Then `health.capabilities_checked` SHALL be an empty list.

## Requirement: Provider drift detection handles invalid inputs

The system SHALL return structured provider issues instead of crashing on invalid inputs.

### Scenario: detect_drift receives None

Given `detect_drift(None, provider="DNSE", dataset_type="ohlcv")`
When drift detection runs
Then it SHALL return one error issue with code `DRIFT_INVALID_INPUT`.

### Scenario: detect_drift receives non-DataFrame object

Given `detect_drift()` receives a list, dict, string, or other non-DataFrame object
When drift detection runs
Then it SHALL return one error issue with code `DRIFT_INVALID_INPUT`.

## Requirement: Cross-provider comparison handles invalid inputs

The system SHALL return non-comparable reports instead of crashing on invalid comparison inputs.

### Scenario: compare_ohlcv receives non-dict input

Given `compare_ohlcv()` receives a non-dict input
When comparison runs
Then it SHALL return a `ProviderComparisonReport` with `comparable=False`
And issue code `COMPARE_INVALID_INPUT`.

### Scenario: compare_ohlcv receives dict with non-DataFrame value

Given `compare_ohlcv({"DNSE": None}, symbol="FPT")`
When comparison runs
Then it SHALL return `comparable=False`
And issue code `COMPARE_INVALID_INPUT`.

### Scenario: compare_ohlcv receives missing required OHLCV columns

Given a provider DataFrame missing `time` or `close`
When comparison runs
Then it SHALL return `comparable=False`
And issue code `COMPARE_INVALID_INPUT` or `COMPARE_MISSING_COLUMN`.

## Requirement: Contract tests fail on adapter drift

Provider contract tests SHALL fail when provider adapter modules or interfaces drift.

### Scenario: Provider adapter import fails

Given a contract test imports a provider adapter
And the adapter module path is broken
When the contract test runs
Then the test SHALL fail
And it SHALL NOT call `pytest.skip()` for that failure.

### Scenario: Provider adapter signature changes

Given a contract test calls a provider method
And the method signature no longer matches the contract
When the contract test runs
Then the test SHALL fail
And it SHALL NOT convert the failure into a skip.

## Requirement: Backward compatibility is preserved

The system SHALL preserve existing caller behavior when validation and diagnostics are disabled.

### Scenario: No validation kwargs and global config disabled

Given `VNSTOCK_QUALITY_ENABLED` is unset or false
And the caller does not pass `validate`
When a supported method returns a DataFrame
Then the method SHALL behave as before
And no quality report is required.

### Scenario: Provider hardening invalid-input guards do not affect valid inputs

Given valid provider DataFrames with required OHLCV columns
When `detect_drift()` and `compare_ohlcv()` run
Then their output SHALL remain compatible with existing successful tests.
