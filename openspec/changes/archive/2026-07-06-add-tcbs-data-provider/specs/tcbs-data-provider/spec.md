# Capability: TCBS Data Provider

## Requirement: TCBS provider package

The system SHALL provide a data-only TCBS provider package under `vnstock/explorer/tcbs/`.

### Scenario: TCBS package exposes data-only adapters

Given the TCBS provider is installed
When `vnstock.explorer.tcbs` is imported
Then it SHALL expose data-only adapters for quote, trading, company, fundamental, and screener data
And it SHALL NOT expose broker login, account, portfolio, order, cash transfer, margin, or iCopy action adapters.

### Scenario: TCBS provider does not accept credentials

Given a caller initializes any TCBS data adapter
When the adapter constructor is called
Then the adapter SHALL NOT require or store TCBS customer credentials
And it SHALL NOT create authenticated customer sessions.

## Requirement: TCBS OHLCV history

The system SHALL support TCBS historical OHLCV retrieval for equities through explicit `source="TCBS"` selection.

### Scenario: Fetch daily OHLCV

Given `source="TCBS"`
And symbol `FPT`
And interval `1D`
And a valid start/end date range
When the caller requests OHLCV history
Then the provider SHALL call a TCBS public/unofficial OHLCV endpoint
And return a DataFrame with columns `time`, `open`, `high`, `low`, `close`, and `volume`
And attach `df.attrs["source"] = "TCBS"`
And attach the successful endpoint variant in `df.attrs["endpoint_variant"]`.

### Scenario: Endpoint fallback

Given the primary TCBS OHLCV endpoint is unreachable or returns an incompatible schema
When the caller requests OHLCV history
Then the provider SHALL try configured fallback endpoint variants in order
And SHALL return data from the first compatible variant
And SHALL raise a structured provider error only after all variants fail.

### Scenario: Unsupported interval

Given the caller requests an interval not supported by TCBS
When the provider validates input
Then it SHALL raise a clear unsupported interval error
And SHALL include the allowed intervals in the error message.

### Scenario: Quality validation enabled

Given the caller requests TCBS OHLCV with `validate=True`
When the provider returns a DataFrame
Then the DataFrame SHALL be validated by the OHLCV quality validator
And the validation report SHALL be attached to `df.attrs["quality"]` when quality report attachment is enabled.

## Requirement: TCBS price board

The system SHALL support TCBS price board / quote snapshot retrieval for a small explicit list of symbols.

### Scenario: Fetch price board for symbols

Given `source="TCBS"`
And symbols `FPT`, `VCB`, and `TCB`
When the caller requests price board data
Then the provider SHALL call the TCBS price board endpoint with a comma-separated ticker list
And return a DataFrame containing at least `symbol`, `close_price`, and `volume_accumulated` when those fields are present
And attach `df.attrs["source"] = "TCBS"`.

### Scenario: Preserve vendor-derived fields

Given the TCBS price board response includes technical, valuation, rating, or relative-strength fields
When the provider normalizes the response
Then those fields SHALL be exposed under clearly named vendor-derived columns
And they SHALL NOT be presented as raw exchange market data.

### Scenario: Price board quality validation

Given the caller requests TCBS price board with `validate=True`
When the provider returns a DataFrame
Then the price board quality validator SHALL run
And any missing required field SHALL produce a validation warning or error according to `quality_mode`.

## Requirement: TCBS company overview and symbol industry

The system SHALL support TCBS company overview data and derive a TCBS_INTERNAL symbol-industry dataset.

### Scenario: Fetch company overview

Given symbol `FPT`
When the caller requests TCBS company overview
Then the provider SHALL return a DataFrame or record containing symbol, exchange, industry, company type, shares, website, foreign ownership percentage, and stock rating when present
And attach provider metadata.

### Scenario: Derive symbol industry

Given TCBS company overview includes `industry`, `industryID`, or `industryIDv2`
When the caller requests symbol industry from TCBS
Then the provider SHALL normalize it as classification system `TCBS_INTERNAL`
And include `symbol`, `industry_code`, `industry_name`, `provider`, `classification_system`, and `fetched_at`.

### Scenario: Missing industry fields

Given TCBS company overview does not contain industry fields for a symbol
When symbol industry normalization runs
Then the provider SHALL return an empty result or warning for that symbol
And SHALL NOT invent an industry classification.

## Requirement: TCBS company reference endpoints

The system SHALL support TCBS company reference endpoints where public/unofficial endpoints are reachable.

### Scenario: Fetch shareholders

Given symbol `FPT`
When the caller requests large shareholders from TCBS
Then the provider SHALL call the large-shareholders endpoint
And return a normalized DataFrame preserving shareholder name, ownership ratio, and related fields when present.

### Scenario: Fetch officers

Given symbol `FPT`
When the caller requests officers from TCBS
Then the provider SHALL call the officers endpoint
And return a normalized DataFrame preserving officer name, title, and related fields when present.

### Scenario: Fetch corporate events and news

Given symbol `FPT`
When the caller requests events or activity news from TCBS
Then the provider SHALL call the relevant paginated endpoint
And return a normalized DataFrame preserving event/news metadata and pagination diagnostics.

## Requirement: TCBS financial statements and ratios

The system SHALL support TCBS financial statements and financial ratios through explicit `source="TCBS"` usage.

### Scenario: Fetch financial ratios

Given symbol `FPT`
And `period="year"`
When the caller requests TCBS financial ratios
Then the provider SHALL call the TCBS financial ratio endpoint with yearly/quarterly parameters
And return a DataFrame preserving period metadata and ratio fields.

### Scenario: Fetch balance sheet

Given symbol `FPT`
When the caller requests TCBS balance sheet data
Then the provider SHALL call the balance-sheet endpoint
And return a DataFrame preserving raw line items and normalized period metadata.

### Scenario: Fetch income statement

Given symbol `FPT`
When the caller requests TCBS income statement data
Then the provider SHALL call the income-statement endpoint
And return a DataFrame preserving raw line items and normalized period metadata.

### Scenario: Fetch cash flow

Given symbol `FPT`
When the caller requests TCBS cash-flow data
Then the provider SHALL call the cash-flow endpoint
And return a DataFrame preserving raw line items and normalized period metadata.

### Scenario: Unsupported period

Given the caller requests an unsupported period
When the TCBS fundamental adapter validates input
Then it SHALL raise a clear unsupported period error
And include allowed values `year` and `quarter`.

## Requirement: TCBS screener dataset

The system SHALL support TCBS screener as an experimental vendor-derived dataset.

### Scenario: Fetch screener with default exchange filter

Given the caller requests TCBS screener with default parameters
When the provider sends a POST request to the watchlist preview endpoint
Then the request SHALL include a payload with filters and size
And the provider SHALL parse `searchData.pageContent`
And return a DataFrame.

### Scenario: Screener language extraction

Given screener response fields include multilingual objects
And caller passes `lang="vi"` or `lang="en"`
When the provider normalizes screener output
Then it SHALL extract the requested language value for known multilingual fields
And preserve raw multilingual objects when `get_all=True`.

### Scenario: Screener field semantics

Given screener output includes TCBS recommendation, buy/sell signal, rating, technical, or valuation fields
When the provider returns normalized output
Then those columns SHALL be documented as vendor-derived fields
And SHALL NOT be documented as investment recommendations from `vnstock`.

## Requirement: TCBS provider capability declarations

The system SHALL declare TCBS provider capabilities in the provider capability registry.

### Scenario: TCBS OHLCV capability exists

Given provider capabilities are loaded
When the caller queries provider `TCBS` and dataset type `ohlcv`
Then the registry SHALL return an equity OHLCV capability
And include supported intervals and unauthenticated public/unofficial notes.

### Scenario: TCBS company overview capability exists

Given provider capabilities are loaded
When the caller queries provider `TCBS` and dataset type `company_profile`
Then the registry SHALL return a company profile capability.

### Scenario: TCBS screener marked experimental

Given provider capabilities are loaded
When the caller queries provider `TCBS` and dataset type `vendor_screener`
Then the capability SHALL be marked experimental or include notes that it is vendor-derived and unstable.

## Requirement: TCBS contract tests

The system SHALL include offline contract tests for TCBS provider adapters.

### Scenario: Contract tests use fixtures only

Given the normal CI test suite is running
When TCBS provider contract tests execute
Then they SHALL use stored fixtures only
And SHALL NOT call live TCBS endpoints.

### Scenario: OHLCV fixture contract

Given a TCBS OHLCV raw fixture
When the contract test parses it
Then normalized output SHALL include required OHLCV columns
And required metadata attrs.

### Scenario: Screener fixture contract

Given a TCBS screener raw fixture containing `searchData.pageContent`
When the contract test parses it
Then normalized output SHALL be a DataFrame
And expected stable fields SHALL be present when included in the fixture.

### Scenario: Malformed fixture

Given a malformed TCBS response fixture missing required top-level keys
When the parser handles it
Then it SHALL raise a structured provider error
And not return a misleading empty DataFrame unless the endpoint semantics explicitly mean no data.

## Requirement: TCBS live smoke tests

The system SHALL include opt-in live smoke tests for TCBS endpoints.

### Scenario: Live tests disabled by default

Given `VNSTOCK_LIVE_TESTS` is unset or false
When the test suite runs
Then TCBS live tests SHALL be skipped.

### Scenario: Live OHLCV smoke test

Given `VNSTOCK_LIVE_TESTS=true`
And TCBS is included in `VNSTOCK_LIVE_PROVIDERS`
When the live test fetches a short daily OHLCV range for `FPT`
Then the response SHALL normalize to a non-empty OHLCV DataFrame or report a provider health failure.

### Scenario: Live company overview smoke test

Given `VNSTOCK_LIVE_TESTS=true`
When the live test fetches company overview for `FPT`
Then the response SHALL include symbol and at least one reference field such as industry, exchange, or short name.

### Scenario: Live endpoint blocked

Given a TCBS endpoint returns 401, 403, or repeated 429
When live smoke validation runs
Then the provider health SHALL be marked degraded or failing for that capability
And the normal CI suite SHALL remain unaffected.

## Requirement: Data-only safety boundary

The TCBS provider SHALL preserve the repository's data-only boundary.

### Scenario: Broker API excluded

Given TCBS has customer-facing trading features such as account, order, portfolio, margin, or iCopy
When implementing the TCBS provider
Then those endpoints SHALL NOT be implemented
And no public API in `vnstock/explorer/tcbs/` SHALL expose order execution or customer-account workflows.

### Scenario: Vendor signal disclaimer

Given TCBS returns rating or recommendation-like fields
When those fields are exposed
Then the documentation SHALL state they are vendor-derived data fields
And not advice generated by `vnstock`.

## Requirement: Backward compatibility

Adding TCBS SHALL preserve existing provider behavior by default.

### Scenario: Existing default source unchanged

Given a caller invokes existing market/reference/fundamental methods without `source="TCBS"`
When the method runs
Then the existing default source selection SHALL remain unchanged.

### Scenario: Explicit TCBS source

Given a caller passes `source="TCBS"` to a supported method
When the method runs
Then the TCBS provider SHALL be selected if the capability is implemented
And unsupported TCBS capabilities SHALL return a clear unsupported capability error.
