# Spec: Provider Normalization

## ADDED Requirements

### Requirement: Existing providers are represented as internal plugins

`vnstock` SHALL represent existing core providers as internal `ProviderPlugin` implementations after Phase 2.

The initial provider set SHOULD include:

- KBS;
- VCI;
- DNSE;
- TCBS;
- FMarket;
- MSN;
- FMP.

#### Scenario: provider plugin exists

Given Phase 2 is implemented
When the provider registry is initialized
Then each supported core provider SHOULD be available as an internal provider plugin.

#### Scenario: provider plugin exposes name

Given a provider plugin is registered
When its metadata is inspected
Then it SHALL expose a stable provider name.

---

### Requirement: Provider capability declarations

Each provider plugin SHALL declare dataset capabilities using the Phase 1 capability model.

Each capability declaration SHALL include, where applicable:

- dataset name;
- supported flag;
- capability status;
- auth requirement;
- supported intervals;
- notes or known limitations.

Allowed capability status values SHALL include:

```text
stable
experimental
partial
deprecated
unsupported
```

#### Scenario: provider declares OHLCV capability

Given a provider supports `equity.ohlcv`
When the provider capabilities are requested
Then the capabilities SHALL include `equity.ohlcv` with `supported=true`.

#### Scenario: provider marks unsupported dataset

Given a provider does not support `fund.nav`
When capabilities are requested
Then `fund.nav` SHALL either be absent or marked with `supported=false`.

#### Scenario: provider declares experimental support

Given a dataset is supported through an experimental or unofficial path
When capabilities are requested
Then the capability status SHOULD be `experimental` or `partial` rather than `stable`.

---

### Requirement: Provider limitations metadata

Each provider plugin SHOULD expose machine-readable limitations metadata.

Limitations metadata SHOULD include:

- provider status;
- known limitations;
- coverage gaps;
- schema drift risk where known;
- excluded out-of-scope capabilities.

#### Scenario: provider limitations are inspectable

Given a provider plugin is registered
When diagnostics are requested
Then diagnostics SHOULD include provider limitation metadata.

#### Scenario: broker capabilities are excluded

Given a provider has broker or account-related APIs outside the data layer
When provider capabilities are declared
Then broker login, broker order, account, portfolio, and execution capabilities SHALL NOT be exposed as supported `vnstock` capabilities.

---

### Requirement: Dataset-to-method mapping

Each provider plugin SHALL map canonical dataset names to provider-specific fetch handlers.

#### Scenario: supported dataset maps to handler

Given a provider supports `equity.ohlcv`
When the provider receives a fetch request for `equity.ohlcv`
Then the provider SHALL dispatch the request to the provider-specific OHLCV handler.

#### Scenario: unsupported dataset raises clear error

Given a provider does not support `fundamental.balance_sheet`
When the provider receives a fetch request for `fundamental.balance_sheet`
Then it SHALL raise `UnsupportedDatasetForProviderError` or an equivalent platform error.

---

### Requirement: Provider normalizers enforce dataset contracts

Provider plugins SHALL normalize provider-native payloads to canonical dataset contract `DataFrame` outputs.

#### Scenario: OHLCV normalizer outputs required columns

Given a provider-native OHLCV fixture
When the provider normalizer runs
Then the output `DataFrame` SHALL include:

```text
symbol
time
open
high
low
close
volume
```

#### Scenario: missing required column fails clearly

Given a provider-native payload cannot produce a required dataset column
When normalization runs
Then normalization SHALL fail with a clear contract or normalization error.

#### Scenario: optional provider fields are preserved safely

Given a provider-native payload has useful extra fields
When normalization runs
Then optional fields MAY be preserved if they do not violate the dataset contract and do not contain secrets.

---

### Requirement: Provider fixtures

Each provider plugin SHOULD include offline fixtures for supported core datasets.

Fixture categories SHOULD include:

- valid response;
- empty but valid response;
- invalid symbol;
- suspended symbol, where applicable;
- newly listed symbol, where applicable;
- non-trading day;
- missing optional fields;
- unexpected extra fields;
- schema drift sample.

#### Scenario: valid fixture normalizes

Given a valid provider fixture for `equity.ohlcv`
When the fixture is passed through the provider normalizer
Then the output SHALL satisfy the `equity.ohlcv` dataset contract.

#### Scenario: schema drift fixture is detected

Given a provider fixture representing schema drift
When the fixture is passed through the provider normalizer or contract validator
Then the test SHOULD detect the drift and fail clearly.

---

### Requirement: Provider contract tests

`vnstock` SHALL include provider contract tests for normalized providers.

Provider contract tests SHALL verify:

- provider registration;
- capability declarations;
- unsupported dataset behavior;
- fixture normalization;
- required output columns;
- diagnostics and limitations metadata;
- data-only boundary enforcement.

#### Scenario: provider contract test passes

Given a provider plugin supports `equity.ohlcv`
When provider contract tests run
Then valid fixtures SHALL normalize and validate successfully.

#### Scenario: unsupported dataset contract test passes

Given a provider plugin does not support a requested dataset
When provider contract tests request that dataset
Then the provider SHALL raise a clear unsupported dataset error.

---

### Requirement: Capability matrix generation

`vnstock` SHALL generate a provider capability matrix from registered provider plugins.

The capability matrix SHOULD include:

- dataset;
- provider;
- supported flag;
- capability status;
- auth requirement;
- intervals where applicable.

#### Scenario: capability matrix includes registered providers

Given providers are registered
When the capability matrix is generated
Then each registered provider SHALL appear in the matrix.

#### Scenario: capability matrix is deterministic

Given the same providers and capabilities
When the capability matrix is generated multiple times
Then the output SHOULD be deterministic for testing and documentation.

---

### Requirement: Backward-compatible public provider usage

Provider normalization SHALL preserve existing public API behavior.

#### Scenario: existing OHLCV call with explicit source

Given a user calls:

```python
Market().equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    source="TCBS",
)
```

Then the call SHALL continue to return a `pandas.DataFrame` if the provider supports the dataset.

#### Scenario: existing OHLCV call with auto/default source

Given a user calls `Market().equity.ohlcv(...)` without explicit source
When the provider router resolves the request
Then the public call SHALL remain backward-compatible with previous default behavior.

---

### Requirement: Data-only boundary remains enforced

Provider normalization MUST NOT introduce trading or broker capabilities into `vnstock`.

Provider plugins MUST NOT expose:

- trading signals;
- stock recommendations;
- broker execution;
- order placement;
- account APIs;
- portfolio APIs;
- trading bots.

#### Scenario: provider exposes out-of-scope capability

Given a provider plugin declares `broker.order` or equivalent execution capability
When provider contract tests run
Then the test SHOULD fail or flag the capability as out of scope.

#### Scenario: provider has login-related legacy script

Given the repository contains legacy login-related entry points
When Phase 2 normalizes providers
Then provider normalization SHALL NOT expand login/session behavior and SHALL defer auth/session redesign to a later auth-specific phase.
