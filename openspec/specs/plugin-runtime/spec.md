# Spec: Plugin Runtime

## ADDED Requirements

### Requirement: PluginRuntime facade

`vnstock` SHALL provide a `PluginRuntime` facade that serves as the default execution boundary for public data requests.

The runtime SHALL:

- accept canonical dataset requests;
- resolve dataset contracts;
- resolve providers through `PluginRouter`;
- call provider plugins;
- wrap output in `DataResult`;
- return `pandas.DataFrame` by default for backward compatibility.

#### Scenario: runtime fetches OHLCV

Given `PluginRuntime` is configured with provider plugins
When `fetch("equity.ohlcv", params={...})` is called
Then the runtime SHALL resolve a provider through `PluginRouter` and return a `pandas.DataFrame`.

#### Scenario: runtime returns DataResult

Given `return_result=True`
When a dataset request succeeds
Then the runtime SHALL return `DataResult` instead of only `pandas.DataFrame`.

---

### Requirement: Public APIs use PluginRuntime

Public data APIs SHALL route supported datasets through `PluginRuntime`.

#### Scenario: Market OHLCV uses plugin runtime

Given a user calls `Market().equity.ohlcv(...)`
When `equity.ohlcv` is supported by provider plugins
Then the call SHALL route through `PluginRuntime`.

#### Scenario: Reference symbols use plugin runtime

Given a user calls the public symbols API
When `reference.symbols` is supported by provider plugins
Then the call SHALL route through `PluginRuntime`.

#### Scenario: Fundamental balance sheet uses plugin runtime

Given a user calls the public balance sheet API
When `fundamental.balance_sheet` is supported by provider plugins
Then the call SHALL route through `PluginRuntime`.

---

### Requirement: Legacy dispatch is retired for migrated datasets

Public APIs SHALL NOT silently bypass `PluginRuntime` for migrated datasets.

#### Scenario: migrated dataset does not use legacy dispatch

Given `equity.ohlcv` is marked migrated
When a public OHLCV request is made
Then the request SHALL NOT directly call legacy provider dispatch outside the plugin runtime.

#### Scenario: legacy client remains internal

Given a provider plugin wraps an old provider client
When the plugin fetches data
Then the old client MAY be used internally, but the public API SHALL still pass through `PluginRuntime`.

---

### Requirement: Controlled legacy fallback

Legacy fallback SHALL be explicit and observable.

#### Scenario: fallback disabled for migrated dataset

Given `equity.ohlcv` is migrated
When plugin runtime fails
Then the runtime SHALL NOT silently fallback to legacy dispatch by default.

#### Scenario: fallback emits diagnostics

Given fallback is explicitly enabled for an unmigrated dataset
When fallback is used
Then the returned result diagnostics SHALL identify the runtime path as `legacy_fallback`.

---

### Requirement: Provider registry bootstrap

`vnstock` SHALL provide a default plugin registry bootstrap.

#### Scenario: default registry contains core providers

Given `default_plugin_registry()` is called
Then the registry SHOULD include KBS, VCI, DNSE, TCBS, FMarket, MSN, and FMP where available.

#### Scenario: default registry exposes capability matrix

Given the default registry is created
When `capability_matrix()` is called
Then the matrix SHALL include registered provider capabilities.

---

### Requirement: DataResult is consistently produced

Every plugin runtime fetch SHALL produce a `DataResult` internally.

#### Scenario: DataFrame attrs include runtime metadata

Given a public API returns a `DataFrame`
When the request is served by `PluginRuntime`
Then `DataFrame.attrs` SHOULD include dataset, provider, quality status, diagnostics, and fetch timestamp metadata.

#### Scenario: diagnostics include runtime path

Given a request is served by `PluginRuntime`
When diagnostics are inspected
Then diagnostics SHALL include runtime path metadata.

---

### Requirement: Health state is updated through runtime

`PluginRuntime` SHALL update provider health state after provider fetch attempts.

#### Scenario: successful fetch records success

Given a provider fetch succeeds
When the runtime returns data
Then provider health SHALL record success.

#### Scenario: failed fetch records failure

Given a provider fetch fails
When the runtime handles the error
Then provider health SHALL record failure.

---

### Requirement: Contract validation integration

`PluginRuntime` SHALL validate provider output against dataset contracts when validation is enabled.

#### Scenario: required columns are present

Given a provider returns data for `equity.ohlcv`
When validation is enabled
Then required OHLCV columns SHALL be checked.

#### Scenario: missing required column fails clearly

Given provider output is missing a required column
When validation is enabled
Then the runtime SHALL fail with a clear contract validation error.

---

### Requirement: Backward-compatible public behavior

Migrating to plugin runtime SHALL preserve public behavior where practical.

#### Scenario: public call still returns DataFrame

Given a user calls an existing public data API
When the request is served by `PluginRuntime`
Then the default return type SHALL remain `pandas.DataFrame`.

#### Scenario: source parameter remains compatible

Given a user passes `source="KBS"` or `source="auto"`
When the request is served by `PluginRuntime`
Then provider selection SHALL respect the source parameter through `PluginRouter`.

---

### Requirement: Phase 4 depends on PluginRuntime only

Phase 4 service and auth-aware data endpoints SHALL use `PluginRuntime` as the only data execution path.

#### Scenario: service endpoint does not call legacy provider directly

Given Phase 4 local data service is implemented
When a service endpoint handles a data request
Then it SHALL call `PluginRuntime`, not legacy provider dispatch.

---

### Requirement: Data-only boundary remains enforced

Completing plugin runtime SHALL NOT introduce non-data platform capabilities.

#### Scenario: plugin runtime rejects out-of-scope capability

Given a provider exposes a non-data capability
When it is registered or routed
Then the platform SHOULD reject or flag it as out of scope.
