# Plugin Architecture Status

This document records the closure status for Phases 1–4 of the vnstock plugin
platform. It is the authoritative reference for what is closed, what is
in-scope for these phases, and what has been deferred to future phases.

---

## Scorecard

| Phase | Description | Closed? | Score |
|-------|-------------|---------|-------|
| Phase 1 | Core contracts and internal plugin foundation | Yes | 98% |
| Phase 2 | Provider plugin normalization | Yes | 98% |
| Phase 3 | Health-aware and auth-aware routing | Yes | 97% |
| Phase 3.5 | PluginRuntime default execution path | Yes | 99% |
| Phase 4 | Auth-aware local data service runtime | Yes | 98% |

Score interpretation:

- 97% = production-shaped internal architecture, fully tested for defined scope
- 98% = public/service runtime paths are guarded against regression
- 99% = phase scope documented, no hidden ambiguity, future work separated

---

## Phase 1: Core contracts and internal plugin foundation

**Status: CLOSED**

### What is closed

- `ProviderPlugin` is the canonical provider adapter interface. All internal
  provider adapters must satisfy this runtime-checkable Protocol.
- `PluginRegistry` manages provider plugin instances (not classes). Lookups
  are case-insensitive. Duplicate registration raises `ValueError`.
- `DataResult` is the canonical internal result envelope. It wraps a
  `DataFrame` with provider name, dataset, quality status, diagnostics, and
  fetch timestamp. Auth secrets are never written to `DataResult` or
  `DataFrame.attrs`.
- Dataset contracts for the initial twelve datasets are registered in
  `CONTRACT_REGISTRY`:
  - `equity.ohlcv`
  - `equity.quote`
  - `equity.intraday_trades`
  - `index.ohlcv`
  - `reference.symbols`
  - `reference.company_info`
  - `fundamental.balance_sheet`
  - `fundamental.income_statement`
  - `fundamental.cash_flow`
  - `fundamental.financial_ratio`
  - `fund.nav`
  - `foreign_flow.daily`
- `CAPABILITY_STATUSES` frozenset defines the allowed status values:
  `stable`, `experimental`, `partial`, `deprecated`, `unsupported`.

### What is NOT part of Phase 1

- External plugin package discovery (Phase 10)
- Plugin version negotiation
- Public user registration of custom providers
- Third-party marketplace or plugin loading

### Registry split

There are two separate registries in this codebase. Do not confuse them:

- `vnstock/core/provider/plugin_registry.py::PluginRegistry` — the plugin
  platform registry, manages `ProviderPlugin` instances. Used by
  `PluginRouter` and `PluginRuntime`.
- `vnstock/core/registry.py::ProviderRegistry` — the legacy class-based
  registry used by `vnstock/base.py` and the Unified UI dispatch layer.

The two registries coexist during the migration period.

---

## Phase 2: Provider plugin normalization

**Status: CLOSED**

### What is closed

- All seven built-in providers are registered through `default_plugin_registry()`:
  - `KBS` — primary Vietnamese market data provider (stable)
  - `VCI` — secondary Vietnamese market data provider (stable)
  - `DNSE` — DNSE chart API (geographic restriction applies)
  - `TCBS` — TCBS market data (requires bearer token auth)
  - `FMARKET` — FMarket fund platform (fund data only)
  - `MSN` — MSN Money market data (experimental)
  - `FMP` — Financial Modeling Prep API (requires `FMP_API_KEY`)
- All built-in providers satisfy the `ProviderPlugin` protocol.
- Every capability declaration contains `supported` and `status` fields.
- Capability status values are restricted to `CAPABILITY_STATUSES`.
- Supported dataset names are restricted to known dataset names.
- Unsupported dataset fetches raise `UnsupportedDatasetForProviderError`.
- Provider `diagnostics()` output is dict-like, JSON-serializable, and
  contains no sensitive credential keys.
- The capability matrix is deterministic (sorted by provider name).

### What is NOT part of Phase 2

- Provider hot-reload or runtime plugin swapping
- Provider version pinning
- Provider capability drift detection at startup
- Marketplace or external provider loading

---

## Phase 3: Health-aware and auth-aware routing

**Status: CLOSED**

### What is closed

- `PluginRouter` resolves dataset requests to provider plugins using health
  status, routing policy, auth policy, and priority tiebreakers.
- Auto routing tier hierarchy: HEALTHY/UNKNOWN → DEGRADED (fallback) →
  FAILING (last resort, only when `allow_failing_fallback=True`).
- DISABLED providers are never selected regardless of policy.
- Cooldown is honored when `respect_cooldown=True` in `RoutingPolicy`.
- Explicit `source=` routing returns the named provider with health checks:
  - DISABLED raises `ProviderDisabledError`.
  - Cooled-down raises `ProviderInCooldownError`.
  - DEGRADED/FAILING adds warnings to the routing decision but proceeds.
- Auth policy variants:
  - `PREFER_NO_AUTH` — public providers first, authenticated as fallback.
  - `FORBID_AUTHENTICATED` — exclude all providers requiring authentication.
  - `REQUIRE_AUTHENTICATED` — only providers requiring authentication.
  - `ALLOW_AUTHENTICATED` — no auth filter.
- Every routing call produces a `RoutingDecision` with `selected_provider`,
  `candidates`, `rejected`, `fallback`, `reason`, and `warnings`.
- `record_success()` and `record_failure()` update the `InMemoryProviderHealthStore`.
- Health transitions: UNKNOWN → HEALTHY (success), HEALTHY → DEGRADED (first
  failure), DEGRADED/consecutive failures → FAILING + cooldown.

### What is NOT part of Phase 3

- Persistent health store (database-backed or Redis-backed)
- Rate limiting per provider
- Circuit breaker pattern (only cooldown is implemented)
- Multi-region routing or geo-routing

---

## Phase 3.5: PluginRuntime default execution path

**Status: CLOSED**

### What is closed

- `PluginRuntime.fetch(dataset, params, ...)` is the single execution path
  for all supported dataset fetches.
- `return_result=True` returns a `DataResult`; default returns a `DataFrame`.
- `DataResult.to_dataframe()` preserves provider, dataset, diagnostics,
  quality_status, and fetched_at in `DataFrame.attrs`.
- `runtime_path` is always attached to `DataResult.diagnostics`.
- Routing diagnostics from `PluginRouter.last_decision` are embedded in
  `DataResult.diagnostics["routing"]`.
- `latency_ms` is recorded and included in diagnostics.
- Provider success is recorded to the health store after every successful fetch.
- Provider failure is recorded after any `ProviderFetchError` or unexpected
  exception.
- Contract validation is supported: `validate=True` checks required columns;
  `quality_mode="strict"` raises `DatasetContractError` on failure.
- Parameter validation via `provider.validate_params()` raises
  `VnstockPlatformError` on invalid params.

### What is NOT part of Phase 3.5

- Caching layer integration at the runtime level (cache is at `_dispatch()`)
- Batch fetching across multiple datasets in one call
- Streaming / async data fetch paths
- SDK migration of all legacy Unified UI methods (in progress separately)

---

## Phase 4: Auth-aware local data service runtime

**Status: CLOSED**

### What is closed

- The `vnstock-serve` CLI entrypoint starts the local data service on
  `127.0.0.1:6900` (default).
- Canonical read-only data endpoints under `/v1/<domain>/<dataset>` route
  all fetches through `PluginRuntime.fetch(..., return_result=True)`.
- Responses use the `data / meta / diagnostics` envelope:
  - `data` — list of records from the DataFrame
  - `meta` — dataset, provider, quality_status, runtime_path, fetched_at
  - `diagnostics` — routing and provider diagnostics
- Provider metadata endpoints use the plugin registry:
  - `GET /v1/providers` — list of registered provider names
  - `GET /v1/providers/capabilities` — full capability matrix
- Auth status endpoint `GET /v1/auth/status` works with and without an
  auth manager. Sensitive fields (tokens, passwords, API keys) are
  never returned.
- Permanently forbidden endpoint groups return 404:
  - `/v1/auth/login` and `/v1/auth/login/oauth`
  - `/v1/order` and order sub-paths
  - `/v1/account` and account sub-paths
  - `/v1/portfolio` and portfolio sub-paths
  - `/v1/transfer`, `/v1/margin`, `/v1/trading`
- `PluginRuntime` is injectable via `runtime_dependency.override_runtime()`
  for test isolation.
- Docker and localhost-only deployment: default binding is `127.0.0.1`.

### CLI entrypoints

Declared in `pyproject.toml [project.scripts]`:

```
vnstock-serve   = "vnstock.cli.serve:main"
vnstock-auth    = "vnstock.cli.auth:main"
vnstock-tcbs-login = "vnstock.cli.tcbs_login:main"
```

### What is NOT part of Phase 4

- REST login / logout endpoints (auth is CLI-only)
- Broker, account, order, portfolio, transfer, and margin endpoints
- Public-facing deployment (TLS termination, reverse proxy config)
- Multi-tenant or multi-user service model
- Rate limiting at the HTTP layer
- WebSocket or streaming endpoints

---

## Future work (not part of Phases 1–4)

The following items are explicitly deferred to future phases:

| Item | Planned Phase |
|------|--------------|
| External plugin package discovery (`pip install vnstock-myprovider`) | Phase 10 |
| Plugin version negotiation and compatibility matrix | Phase 10 |
| Marketplace or third-party provider loading | Phase 10 |
| Rate limiter per provider | Phase 5 |
| Batch ingestion and partial failure envelope | Phase 5 |
| Storage sinks (Parquet, databases) | Phase 6 |
| MCP (Model Context Protocol) integration | Phase 8 |
| TUI (terminal user interface) | Phase 9 |
| Quality engine v2 with configurable rules | Phase 7 |
| SDK migration of all legacy Unified UI methods | Ongoing |
| Async / streaming fetch paths | Phase 5+ |

---

## Data-only boundary

The plugin platform and local service are data-extraction-only:

- No trading execution, order management, or broker API calls
- No charting, visualization, or notification delivery
- No portfolio tracking or account management
- No third-party integrations outside of public data providers and
  the FMP commercial API

---

## Runtime-first rule

Any data fetch that reaches the service layer MUST route through
`PluginRuntime`. Direct provider calls that bypass `PluginRuntime` are
considered regressions. Tests in `test_service_runtime_closure.py` guard
this invariant.
