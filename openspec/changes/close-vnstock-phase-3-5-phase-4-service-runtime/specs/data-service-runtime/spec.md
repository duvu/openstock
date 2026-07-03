# Spec: Data Service Runtime Closure

## ADDED Requirements

### Requirement: Service data endpoints use PluginRuntime

All supported data endpoints SHALL execute through `PluginRuntime`.

#### Scenario: equity OHLCV endpoint uses runtime

Given the local service receives `GET /v1/equity/ohlcv?symbol=FPT`  
When the request is handled  
Then the service SHALL call `PluginRuntime.fetch("equity.ohlcv", ..., return_result=True)`.

#### Scenario: service does not use legacy dispatch

Given a supported data endpoint is requested  
When the service fetches data  
Then it SHALL NOT instantiate legacy UI objects or provider/explorer classes directly.

---

### Requirement: Canonical data endpoints

The service SHALL expose canonical read-only v1 data endpoints.

#### Scenario: equity endpoints exist

Given the service is running  
When a client calls `/v1/equity/ohlcv`, `/v1/equity/quote`, or `/v1/equity/intraday-trades`  
Then each endpoint SHALL map to the corresponding canonical dataset name.

#### Scenario: reference and company endpoints exist

Given the service is running  
When a client calls `/v1/reference/symbols` or `/v1/company/info`  
Then the service SHALL map the request to `reference.symbols` or `reference.company_info`.

#### Scenario: fundamental and fund endpoints exist

Given the service is running  
When a client calls fundamental or fund endpoints  
Then the service SHALL map them to canonical dataset names.

---

### Requirement: DataResult response envelope

All successful data endpoints SHALL return a stable response envelope with `data`, `meta`, and `diagnostics`.

#### Scenario: response includes metadata

Given a data request succeeds  
When the response is serialized  
Then `meta` SHALL include request ID, dataset, provider, quality status, fetched timestamp, source requested, and runtime path.

#### Scenario: response includes diagnostics

Given a data request succeeds  
When diagnostics are available  
Then the response SHALL include routing, provider, quality, and warning diagnostics where available.

#### Scenario: sensitive data is redacted

Given provider diagnostics or auth context contains sensitive fields  
When the response is serialized  
Then credential material SHALL NOT appear in the response.

---

### Requirement: Provider endpoints use plugin registry

Provider metadata endpoints SHALL use the plugin registry created by `default_plugin_registry()`.

#### Scenario: provider names come from plugin registry

Given the service handles `GET /v1/providers`  
When providers are listed  
Then provider names SHALL come from `PluginRegistry.names()`.

#### Scenario: capability matrix comes from plugin registry

Given the service handles `GET /v1/providers/capabilities`  
When capabilities are listed  
Then the response SHALL be based on `PluginRegistry.capability_matrix()`.

---

### Requirement: Auth status works safely

The service and CLI SHALL expose safe auth status only.

#### Scenario: auth status endpoint returns safe data

Given an auth manager is configured  
When `GET /v1/auth/status` is called  
Then the response SHALL include authentication status and SHALL NOT expose credential material.

#### Scenario: CLI auth status works

Given credentials may or may not exist  
When `vnstock-auth status` is executed  
Then the command SHALL complete without printing raw secrets.

---

### Requirement: Forbidden endpoints remain unavailable

The service SHALL NOT expose broker, trading, account, portfolio, transfer, margin, or REST login endpoints.

#### Scenario: REST login is unavailable

Given the service is running  
When a client calls REST login endpoints  
Then the service SHALL return 404 or 405.

#### Scenario: trading endpoint groups are unavailable

Given the service is running  
When a client calls order, account, portfolio, trade, transfer, margin, or portfolio execution endpoints  
Then the service SHALL return 404 or 405.

---

### Requirement: Runtime error mapping

Runtime errors SHALL be mapped to stable HTTP error envelopes.

#### Scenario: unsupported dataset

Given a client requests an unsupported dataset  
When the service cannot map or route it  
Then the response SHALL be 404 with an unsupported or not-found error.

#### Scenario: provider fetch failure

Given `PluginRuntime` raises a provider fetch error  
When the service handles the error  
Then the response SHALL be 502 with a provider fetch error envelope.

#### Scenario: contract validation failure

Given validation is strict and contract validation fails  
When the service handles the error  
Then the response SHALL be 422.

---

### Requirement: Roadmap does not approve REST login

The roadmap SHALL align with command-based local auth.

#### Scenario: roadmap lists auth status only

Given the roadmap describes the REST data service  
When auth endpoints are listed  
Then only safe status/provider endpoints SHALL be listed.

#### Scenario: roadmap forbids REST login

Given the roadmap describes service auth  
When implementation boundaries are listed  
Then REST login/logout endpoints SHALL be explicitly out of scope.
