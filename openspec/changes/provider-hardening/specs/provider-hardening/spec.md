# Capability: Provider Hardening

## Requirement: Provider capability declarations

The system SHALL maintain structured capability declarations for each supported provider.

### Scenario: Provider declares OHLCV capability

Given a provider supports historical OHLCV data
When the provider capability registry is loaded
Then the provider SHALL expose a `ProviderCapability` entry for dataset type `ohlcv`
And the entry SHALL include provider name, asset class, method name, supported intervals, and auth requirement.

### Scenario: Unsupported provider capability

Given a provider does not support a requested capability
When the caller queries the capability registry
Then the registry SHALL return no matching capability
And the caller SHALL receive a structured unsupported-capability result instead of an ambiguous provider error.

## Requirement: Contract tests for providers

The system SHALL provide contract tests for provider adapters using stored golden fixtures.

### Scenario: Raw fixture parses successfully

Given a stored raw response fixture for a provider endpoint
When the contract test runs the provider adapter parser against the fixture
Then the parser SHALL produce a normalized DataFrame
And the DataFrame SHALL satisfy the expected normalized schema.

### Scenario: Normalized schema mismatch

Given a provider parser returns a DataFrame missing a required normalized column
When the contract test validates the output
Then the test SHALL fail with a schema drift or contract violation message.

### Scenario: Contract tests do not call network

Given normal CI is running
When provider contract tests are executed
Then they SHALL use stored fixtures only
And they SHALL NOT call live provider endpoints.

## Requirement: Live smoke tests for providers

The system SHALL support opt-in live smoke tests for real provider endpoints.

### Scenario: Live tests disabled by default

Given `VNSTOCK_LIVE_TESTS` is unset or false
When the test suite runs
Then live provider tests SHALL be skipped.

### Scenario: Live endpoint returns compatible payload

Given `VNSTOCK_LIVE_TESTS=true`
And a provider endpoint is reachable
When a live smoke test fetches a small known symbol and date range
Then the response SHALL normalize to a valid DataFrame
And the live test SHALL record provider health as `healthy` or `degraded`.

### Scenario: Live endpoint schema drift

Given `VNSTOCK_LIVE_TESTS=true`
And a provider endpoint returns a payload missing required raw fields
When live smoke validation runs
Then the system SHALL report schema drift
And the provider health status SHALL be `failing` or `degraded` depending on severity.

## Requirement: Schema drift detection

The system SHALL detect raw and normalized schema drift.

### Scenario: Raw response adds optional field

Given a provider raw response contains an additional optional field
When raw schema drift detection runs
Then the drift level SHALL be `minor`
And the provider SHALL NOT be marked failing solely because of the optional addition.

### Scenario: Raw response misses required field

Given a provider raw response misses a raw field required by the parser
When raw schema drift detection runs
Then the drift level SHALL be `major`
And the provider SHALL be marked `failing` for that capability.

### Scenario: Normalized DataFrame misses required column

Given a provider adapter returns a normalized DataFrame without a required column
When normalized schema drift detection runs
Then the drift level SHALL be `major`
And the system SHALL emit a contract violation.

## Requirement: Cross-provider comparison

The system SHALL compare overlapping provider outputs for the same symbol, interval, and date range.

### Scenario: Comparable OHLCV outputs

Given KBS, VCI, and DNSE all return daily OHLCV for the same symbol and date range
When cross-provider comparison runs
Then the comparison report SHALL include row counts by provider
And missing dates by provider
And price difference summary
And volume difference summary.

### Scenario: Provider has missing dates

Given one provider is missing trading dates present in other providers
When cross-provider comparison runs
Then the comparison report SHALL identify the missing dates for that provider.

### Scenario: Provider has price scale mismatch

Given one provider returns prices at a different scale from the other providers
When cross-provider comparison runs
Then the comparison report SHALL emit a price-scale issue
And provider health for that capability SHALL be marked `degraded` or `failing`.

## Requirement: Provider health scoring

The system SHALL produce a health status for each provider and capability.

### Scenario: Healthy provider

Given a provider endpoint is reachable
And schema checks pass
And freshness checks pass
And error rate is below threshold
When provider health is evaluated
Then the provider status SHALL be `healthy`.

### Scenario: Degraded provider

Given a provider endpoint is reachable
But latency is high or data is stale or optional schema drift exists
When provider health is evaluated
Then the provider status SHALL be `degraded`.

### Scenario: Failing provider

Given a provider endpoint is unreachable or required schema fields are missing
When provider health is evaluated
Then the provider status SHALL be `failing`.

### Scenario: Unknown provider health

Given no recent provider health check exists
When provider health is requested
Then the provider status SHALL be `unknown`.

## Requirement: Router integration

The provider router SHOULD consider provider health when choosing providers.

### Scenario: Healthy provider available

Given at least one healthy provider supports the requested capability
When the router picks a provider
Then it SHOULD prefer healthy providers.

### Scenario: Only degraded providers available

Given all providers for a capability are degraded
When the router picks a provider
Then it MAY use a degraded provider
And the result SHOULD include provider diagnostics when requested.

### Scenario: Provider marked failing

Given a provider is marked failing for a capability
When the router picks a provider
Then it SHOULD skip the failing provider unless the caller explicitly forces that source.

## Requirement: Provider capability matrix

The system SHALL generate a provider capability matrix from provider declarations and test results.

### Scenario: Generate provider matrix markdown

Given provider capabilities are declared
And contract test statuses are available
When the matrix generation command runs
Then the system SHALL generate `docs/PROVIDER_MATRIX.md`.

### Scenario: Generate provider matrix JSON

Given provider capabilities are declared
And test statuses are available
When the matrix generation command runs
Then the system SHALL generate a machine-readable provider matrix JSON artifact.

## Requirement: Backward compatibility

Provider hardening SHALL preserve existing data-fetching behavior by default.

### Scenario: Health checks disabled

Given provider health checks are disabled
When a caller invokes a market data method without diagnostic flags
Then the method SHALL behave as it did before provider hardening.

### Scenario: Diagnostics requested

Given a caller invokes a market data method with `include_provider_diagnostics=True`
When the method returns a DataFrame
Then the DataFrame SHALL include provider diagnostic metadata in `df.attrs`.
