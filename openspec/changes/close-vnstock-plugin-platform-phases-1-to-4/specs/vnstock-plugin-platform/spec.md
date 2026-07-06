# Spec: vnstock Plugin Platform Closure

## ADDED Requirements

### Requirement: Phase 1 plugin foundation closure

The plugin foundation SHALL be marked closed only when provider interface, plugin registry, DataResult, and dataset contract behavior are tested and documented.

#### Scenario: provider interface is canonical

Given a provider adapter is used by the plugin path  
When it is registered  
Then it SHALL conform to the `ProviderPlugin` interface.

#### Scenario: registry behavior is deterministic

Given providers are registered  
When provider names and capability matrix are requested  
Then results SHALL be deterministic and case-insensitive where applicable.

#### Scenario: DataResult preserves metadata

Given runtime returns a DataResult  
When converted to DataFrame  
Then dataset, provider, quality status, diagnostics, and fetched timestamp SHALL be preserved in attrs or equivalent metadata.

#### Scenario: dataset contracts are closed for initial scope

Given initial dataset names are part of Phase 1  
When the contract registry is inspected  
Then each dataset SHALL either have a registered contract or be explicitly listed as deferred in the architecture status document.

---

### Requirement: Phase 2 provider plugin normalization closure

Built-in providers SHALL be verified as plugin-conforming providers with honest capability declarations.

#### Scenario: built-in providers are registered

Given `default_plugin_registry()` is called  
When provider names are listed  
Then all available built-in provider plugins SHALL be registered.

#### Scenario: capabilities are valid

Given a built-in provider exposes capabilities  
When the capability matrix is generated  
Then every capability record SHALL have a valid `supported` flag and status.

#### Scenario: unsupported datasets are explicit

Given a provider does not support a dataset  
When that dataset is requested from that provider  
Then the provider SHALL reject it explicitly rather than silently returning incorrect data.

---

### Requirement: Phase 3 routing closure

Routing SHALL be deterministic, diagnostics-first, health-aware, and auth-policy-aware.

#### Scenario: auto routing selects healthy candidate

Given multiple providers support a dataset  
When auto routing is used  
Then the router SHALL select according to capability, priority, health, cooldown, and policy.

#### Scenario: explicit routing is honored safely

Given a caller requests a specific provider  
When the provider supports the dataset  
Then explicit routing SHALL select it unless hard-disabled or blocked by cooldown policy.

#### Scenario: routing diagnostics are serializable

Given a routing decision is made  
When diagnostics are requested  
Then diagnostics SHALL include selected provider, candidates, rejection reasons, fallback flag, and reason.

#### Scenario: health state is updated

Given runtime records provider success or failure  
When the health store is inspected  
Then provider health state SHALL reflect the update.

---

### Requirement: Phase 3.5 PluginRuntime closure

PluginRuntime SHALL be the default execution path for migrated datasets.

#### Scenario: runtime returns DataResult

Given a dataset fetch is executed with `return_result=True`  
When the provider returns data  
Then runtime SHALL return a DataResult with dataset, provider, data, diagnostics, and fetched timestamp.

#### Scenario: runtime attaches runtime path

Given a runtime fetch completes  
When diagnostics are inspected  
Then diagnostics SHALL include `runtime_path = plugin_runtime`.

#### Scenario: migrated paths cannot bypass runtime

Given a dataset path is declared migrated  
When tests execute the path  
Then the path SHALL go through PluginRuntime or fail the regression test.

---

### Requirement: Phase 4 local service closure

The local data service SHALL expose a runtime-backed, data-read-only service surface.

#### Scenario: canonical endpoint uses runtime

Given the service receives `GET /v1/equity/ohlcv`  
When the request is handled  
Then the service SHALL call PluginRuntime and return a DataResult envelope.

#### Scenario: response envelope is stable

Given a service data request succeeds  
When the response is serialized  
Then it SHALL include `data`, `meta`, and `diagnostics`.

#### Scenario: provider endpoints use plugin registry

Given provider metadata endpoints are called  
When providers or capabilities are returned  
Then output SHALL be based on the plugin registry.

#### Scenario: service remains data-read-only

Given the local service is running  
When unavailable endpoint groups are requested  
Then the service SHALL return not-found or method-not-allowed responses.

---

### Requirement: Phase closure status document

A plugin architecture status document SHALL record closure state and future scope.

#### Scenario: status document records scores

Given the closure work is complete  
When `docs/PLUGIN_ARCHITECTURE_STATUS.md` is opened  
Then it SHALL show Phase 1, Phase 2, Phase 3, Phase 3.5, and Phase 4 as 97-99% closed or closure-ready.

#### Scenario: future work is separated

Given external plugin discovery or later platform features are not part of current closure  
When the status document is read  
Then those items SHALL be listed under future scope rather than counted against Phase 1-4 closure.
