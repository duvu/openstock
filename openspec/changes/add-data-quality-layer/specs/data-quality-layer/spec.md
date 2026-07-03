# Capability: Data Quality Layer

## Requirement: Validate OHLCV schema

The system SHALL validate OHLCV DataFrames against the standard OHLCV schema.

### Scenario: Valid OHLCV DataFrame

Given a DataFrame with columns `time`, `open`, `high`, `low`, `close`, `volume`
And all numeric values are valid
And all OHLC consistency rules pass
When the caller validates it as `dataset_type="ohlcv"`
Then the validation report SHALL have `valid=True`
And the report SHALL contain no errors.

### Scenario: Missing required OHLCV column

Given a DataFrame without the `close` column
When the caller validates it as `dataset_type="ohlcv"`
Then the validation report SHALL contain an error with code `SCHEMA_MISSING_COLUMN`
And `valid` SHALL be `False`.

### Scenario: OHLC inconsistency

Given a DataFrame where `high < low` for at least one row
When the caller validates it as `dataset_type="ohlcv"`
Then the validation report SHALL contain an error with code `OHLC_HIGH_BELOW_LOW`.

## Requirement: Validate price board schema

The system SHALL validate price board snapshots against the standard price board schema.

### Scenario: Duplicate symbol

Given a price board DataFrame containing the same symbol more than once
When the caller validates it as `dataset_type="price_board"`
Then the validation report SHALL contain a warning or error with code `BOARD_DUPLICATE_SYMBOL`.

### Scenario: Close price outside floor and ceiling

Given a row where `close_price` is greater than `ceiling_price`
When the caller validates the price board
Then the validation report SHALL contain an error with code `BOARD_PRICE_OUTSIDE_FLOOR_CEILING`.

## Requirement: Validate intraday trade schema

The system SHALL validate intraday trade DataFrames against the standard intraday trade schema.

### Scenario: Invalid match type

Given an intraday trade DataFrame where `match_type` contains `abc`
When the caller validates it as `dataset_type="intraday_trades"`
Then the validation report SHALL contain an error with code `TRADE_INVALID_MATCH_TYPE`.

### Scenario: Duplicate trade id

Given an intraday trade DataFrame with duplicate `id` values
When the caller validates it
Then the validation report SHALL contain a warning or error with code `TRADE_DUPLICATE_ID`.

## Requirement: Attach validation report to DataFrame

The system SHALL attach validation reports to returned DataFrames when validation is enabled.

### Scenario: Validation enabled in warning mode

Given a caller invokes a supported market data method with `validate=True` and `quality_mode="warn"`
When the method returns a DataFrame
Then the DataFrame SHALL include `df.attrs["quality"]`
And validation errors SHALL NOT raise exceptions.

### Scenario: Validation enabled in strict mode

Given a caller invokes a supported market data method with `validate=True` and `quality_mode="strict"`
And validation produces at least one error
When the method returns
Then the system SHALL raise `DataQualityError`
And the exception SHALL contain the validation report.

## Requirement: Support freshness checks

The system SHALL support freshness checks for live and historical datasets.

### Scenario: Stale price board

Given a price board DataFrame whose latest data timestamp is older than the configured stale threshold
When freshness validation runs
Then the validation report SHALL include a warning or error with code `FRESHNESS_STALE`.

### Scenario: Missing latest timestamp

Given a live dataset without latest timestamp metadata
When freshness validation runs
Then the validation report SHALL include a warning with code `FRESHNESS_LATEST_TIME_MISSING`.

## Requirement: Preserve backward compatibility

The system SHALL preserve existing behavior when validation is disabled.

### Scenario: Validation disabled

Given validation is disabled by configuration
And the caller does not pass `validate=True`
When a supported market data method returns a DataFrame
Then the result SHALL be returned without raising data quality exceptions
And no validation report is required.
