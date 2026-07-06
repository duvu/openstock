# Spec: Provider Platform Core

## ADDED Requirements

### Requirement: Dataset contracts

`vnstock` SHALL define dataset contracts for canonical financial datasets.

Each dataset contract SHALL specify:

- dataset name;
- required columns;
- optional columns;
- dtype rules where practical;
- time column policy where applicable;
- symbol column policy where applicable;
- validator binding where applicable.

#### Scenario: OHLCV contract exists

Given the platform contract registry is initialized
When the caller requests the contract for `equity.ohlcv`
Then the registry SHALL return a contract with required columns:

```text
symbol
time
open
high
low
close
volume
```

#### Scenario: unknown contract lookup

Given the platform contract registry is initialized
When the caller requests an unknown dataset contract
Then the registry SHALL raise a clear dataset contract error.

---

### Requirement: Provider plugin interface

`vnstock` SHALL define a provider plugin interface for data providers.

The provider plugin interface SHALL support:

- provider name;
- capability declaration;
- dataset fetch;
- parameter validation;
- diagnostics.

#### Scenario: provider exposes capabilities

Given a provider plugin is registered
When the registry asks for provider capabilities
Then the provider SHALL return a capability mapping by dataset name.

#### Scenario: provider fetches dataset

Given a provider plugin supports `equity.ohlcv`
When the provider receives a valid fetch request for `equity.ohlcv`
Then it SHALL return a normalized `pandas.DataFrame` matching the dataset contract.

#### Scenario: provider rejects unsupported dataset

Given a provider plugin does not support `fundamental.balance_sheet`
When the provider receives a fetch request for `fundamental.balance_sheet`
Then it SHALL raise a clear unsupported dataset error.

---

### Requirement: Provider registry

`vnstock` SHALL provide a provider registry.

The provider registry SHALL support:

- registering provider plugins;
- provider lookup by name;
- provider candidate lookup by dataset;
- capability matrix generation.

#### Scenario: register provider

Given a valid provider plugin
When it is registered
Then the registry SHALL make it available by provider name.

#### Scenario: duplicate provider

Given a provider named `KBS` is already registered
When another provider named `KBS` is registered
Then the registry SHALL raise a duplicate provider error.

#### Scenario: providers for dataset

Given multiple providers are registered
When the caller asks for providers supporting `equity.ohlcv`
Then the registry SHALL return only providers that declare support for `equity.ohlcv`.

---

### Requirement: Provider router skeleton

`vnstock` SHALL provide a provider router that resolves dataset requests to provider plugins.

Phase 1 router behavior SHALL support:

- explicit provider source;
- `source=None`;
- `source="auto"`;
- routing diagnostics.

#### Scenario: explicit provider routing

Given provider `TCBS` is registered and supports `equity.ohlcv`
When the caller requests `equity.ohlcv` with `source="TCBS"`
Then the router SHALL return the `TCBS` provider.

#### Scenario: explicit unsupported provider routing

Given provider `TCBS` is registered but does not support `fund.nav`
When the caller requests `fund.nav` with `source="TCBS"`
Then the router SHALL raise an unsupported dataset for provider error.

#### Scenario: auto routing

Given multiple providers support `equity.ohlcv`
When the caller requests `equity.ohlcv` with `source="auto"`
Then the router SHALL select a provider based on configured default provider priority.

#### Scenario: routing diagnostics

Given the router resolves a provider
When routing completes
Then diagnostics SHOULD include:

```text
dataset
source
selected_provider
candidate_providers
routing_reason
```

---

### Requirement: DataResult envelope

`vnstock` SHALL define a structured internal result envelope called `DataResult`.

`DataResult` SHALL include:

- dataset;
- provider;
- data;
- quality status;
- quality report;
- diagnostics;
- fetched timestamp;
- optional ingestion run ID.

#### Scenario: DataResult to DataFrame

Given a `DataResult` with metadata
When `to_dataframe()` is called
Then the returned `DataFrame` SHALL contain metadata in `DataFrame.attrs`.

#### Scenario: no secrets in metadata

Given a `DataResult` is created
When metadata is attached to `DataFrame.attrs`
Then the metadata MUST NOT include:

```text
password
api_key
access_token
refresh_token
cookie
authorization header
session id
```

---

### Requirement: Backward-compatible public API

`vnstock` SHALL preserve existing public API behavior during Phase 1.

#### Scenario: existing OHLCV call

Given user code imports `Market`
When the user calls:

```python
Market().equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    validate=True,
)
```

Then the call SHALL continue to return a `pandas.DataFrame`.

#### Scenario: quality metadata compatibility

Given the user calls OHLCV with `validate=True`
When quality validation is attached
Then existing quality metadata access through `df.attrs.get("quality")` SHOULD remain compatible.

---

### Requirement: Data-only boundary

`vnstock` SHALL remain a data-only platform.

The core provider platform MUST NOT introduce:

- trading signals;
- stock recommendations;
- portfolio management;
- broker execution;
- order placement;
- account APIs;
- trading bots.

#### Scenario: provider plugin attempts broker execution

Given a provider plugin declares broker execution capabilities
When the plugin is validated against platform scope
Then the platform SHOULD reject or flag the capability as out of scope.

#### Scenario: surface requests recommendation

Given a future API, CLI, TUI, or MCP surface uses the provider platform
When the user asks for stock recommendation
Then the provider platform SHALL not provide recommendation logic and SHOULD direct such analysis to an external research layer such as `vnalpha`.
