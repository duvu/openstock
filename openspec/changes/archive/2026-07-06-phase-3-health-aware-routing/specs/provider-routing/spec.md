# Spec: Provider Routing and Diagnostics

## ADDED Requirements

### Requirement: Provider health model

`vnstock` SHALL define a provider health model for dataset-level provider status.

Provider health SHALL include:

- provider name;
- dataset name;
- health status;
- optional latency;
- optional error rate;
- optional freshness score;
- last success timestamp;
- last failure timestamp;
- failure count;
- success count;
- optional cooldown timestamp;
- optional notes.

Allowed statuses SHALL include:

```text
HEALTHY
DEGRADED
FAILING
UNKNOWN
DISABLED
```

#### Scenario: unknown provider health defaults to UNKNOWN

Given no health record exists for provider `KBS` and dataset `equity.ohlcv`
When health is requested
Then the health store SHALL return status `UNKNOWN`.

#### Scenario: successful fetch updates health

Given provider `KBS` successfully fetches `equity.ohlcv`
When success is recorded
Then provider health SHOULD update `last_success_at` and increment success count.

#### Scenario: failed fetch updates health

Given provider `KBS` fails to fetch `equity.ohlcv`
When failure is recorded
Then provider health SHOULD update `last_failure_at` and increment failure count.

---

### Requirement: Provider health store

`vnstock` SHALL provide a provider health store.

Phase 3 SHALL include an in-memory implementation.

The health store SHALL support:

- reading provider health;
- setting provider health;
- recording success;
- recording failure;
- listing health by dataset.

#### Scenario: list health for dataset

Given multiple providers have health records for `equity.ohlcv`
When health is listed for `equity.ohlcv`
Then the store SHALL return health records for that dataset.

---

### Requirement: Health-aware auto routing

`ProviderRouter` SHALL support health-aware provider selection when `source` is `None` or `"auto"`.

Auto routing SHALL consider:

- dataset support;
- provider health;
- active cooldown;
- configured priority;
- routing policy.

#### Scenario: auto routing selects healthy provider

Given providers `KBS` and `TCBS` support `equity.ohlcv`
And `KBS` is `HEALTHY`
And `TCBS` is `DEGRADED`
When the caller requests `equity.ohlcv` with `source="auto"`
Then the router SHALL select `KBS`.

#### Scenario: auto routing skips cooldown provider

Given providers `KBS` and `VCI` support `equity.ohlcv`
And `KBS` is in active cooldown
And `VCI` is available
When the caller requests `equity.ohlcv` with `source="auto"`
Then the router SHALL not select `KBS`.

#### Scenario: auto routing falls back to degraded provider

Given no `HEALTHY` provider is available
And provider `VCI` is `DEGRADED`
And routing policy allows degraded providers
When the caller requests `equity.ohlcv` with `source="auto"`
Then the router MAY select `VCI` and MUST include a degradation warning in diagnostics.

#### Scenario: failing providers are rejected by default

Given provider `TCBS` is `FAILING`
When the caller requests `equity.ohlcv` with `source="auto"`
Then the router SHALL reject `TCBS` unless routing policy explicitly allows failing fallback.

---

### Requirement: Explicit source routing is preserved

`ProviderRouter` SHALL preserve explicit source behavior.

If a caller explicitly requests a provider that supports the dataset, the router SHALL select that provider unless it is disabled or unsupported.

#### Scenario: explicit degraded provider is selected with warning

Given provider `TCBS` supports `equity.ohlcv`
And `TCBS` is `DEGRADED`
When the caller requests `equity.ohlcv` with `source="TCBS"`
Then the router SHALL select `TCBS`
And diagnostics SHALL include a health warning.

#### Scenario: explicit unsupported provider fails clearly

Given provider `FMarket` does not support `equity.ohlcv`
When the caller requests `equity.ohlcv` with `source="FMarket"`
Then the router SHALL raise a clear unsupported dataset for provider error.

---

### Requirement: Routing diagnostics

`ProviderRouter` SHALL produce routing diagnostics for routed requests.

Diagnostics SHOULD include:

- dataset;
- requested source;
- selected provider;
- candidate providers;
- rejected providers;
- routing reason;
- fallback used;
- health snapshot;
- warnings.

#### Scenario: diagnostics include selected provider

Given routing completes successfully
When diagnostics are inspected
Then diagnostics SHALL include the selected provider.

#### Scenario: diagnostics include rejected providers

Given one or more candidates are rejected due to cooldown, unsupported dataset, disabled status, or failing health
When diagnostics are inspected
Then diagnostics SHOULD include rejected providers and rejection reasons.

#### Scenario: diagnostics do not expose credential material

Given routing diagnostics are attached to a result
When diagnostics are inspected
Then diagnostics MUST NOT contain sensitive credential material.

---

### Requirement: Cooldown behavior

`vnstock` SHALL support provider cooldown for recently failing provider-dataset combinations.

Cooldown SHALL prevent auto routing from repeatedly selecting providers that recently failed.

#### Scenario: repeated failure triggers cooldown

Given provider `KBS` repeatedly fails for `equity.ohlcv`
When failures are recorded
Then provider `KBS` SHOULD enter cooldown for `equity.ohlcv`.

#### Scenario: cooldown expires

Given provider `KBS` is in cooldown for `equity.ohlcv`
When the cooldown timestamp has passed
Then auto routing MAY consider `KBS` again.

---

### Requirement: Provider comparison expansion

`vnstock` SHALL expand provider comparison capabilities.

Comparison functions SHOULD include:

- `compare_ohlcv`;
- `compare_quote`;
- `compare_intraday_shape`;
- `compare_coverage`;
- `compare_freshness`.

#### Scenario: OHLCV comparison handles missing required columns

Given a provider OHLCV frame is missing required columns
When `compare_ohlcv` runs
Then comparison SHALL fail clearly before accessing missing columns.

#### Scenario: quote comparison compares basic fields

Given two providers return quote data for the same symbols
When `compare_quote` runs
Then comparison SHOULD report coverage, freshness, and value mismatches where possible.

#### Scenario: intraday comparison checks shape

Given two providers return intraday data
When `compare_intraday_shape` runs
Then comparison SHOULD check required columns, row count, timestamp parseability, duplicate rows, and session coverage.

#### Scenario: freshness comparison reports stale provider

Given provider `TCBS` returns older data than provider `KBS` for the same dataset
When `compare_freshness` runs
Then comparison SHOULD identify `TCBS` as less fresh.

---

### Requirement: DataResult diagnostics integration

Routing diagnostics SHALL be attached to internal result metadata.

#### Scenario: DataResult contains routing diagnostics

Given a dataset fetch is routed through `ProviderRouter`
When a `DataResult` is created
Then `DataResult.diagnostics` SHALL include routing diagnostics.

#### Scenario: DataFrame attrs preserve diagnostics

Given a public API returns a `DataFrame`
When internal diagnostics exist
Then `DataFrame.attrs` SHOULD include diagnostics without breaking existing quality metadata.

---

### Requirement: Backward-compatible public API

Health-aware routing SHALL preserve existing public API behavior.

#### Scenario: existing OHLCV call still returns DataFrame

Given a user calls `Market().equity.ohlcv(...)`
When the request is routed through health-aware routing
Then the public result SHALL remain a `pandas.DataFrame`.

#### Scenario: validate true remains compatible

Given a user calls OHLCV with `validate=True`
When quality validation runs
Then existing quality metadata access through `df.attrs.get("quality")` SHOULD remain compatible.

---

### Requirement: Data-only boundary remains enforced

Health-aware routing and diagnostics MUST NOT introduce trading or broker capabilities.

The routing layer MUST NOT provide:

- trading signals;
- stock recommendations;
- broker execution;
- order placement;
- account APIs;
- portfolio APIs;
- trading bots.

#### Scenario: routing is used by AI/MCP consumer

Given a future AI or MCP consumer requests provider diagnostics
When the routing layer responds
Then it SHALL return data-provider diagnostics only, not investment recommendations.
