# Plugin architecture status

This document records the stable architecture and accepted closure state of the synchronous `vnstock` provider platform. It is not a live delivery roadmap; current priority and issue status are maintained in GitHub issue #90.

## Scorecard

| Area | Status |
|---|---|
| Core contracts and internal plugin foundation | Implemented |
| Built-in provider normalization | Implemented for the registered providers and their declared datasets |
| Health- and auth-aware routing | Implemented |
| `PluginRuntime` synchronous execution path | Implemented |
| Auth-aware localhost data service | Implemented |
| Commercial FiinQuantX provider | Partial/experimental; bounded explicit-only slice implemented, closure remains #193 |
| Streaming/WebSocket provider runtime | Not implemented |

## Core contracts

The platform uses:

- runtime-checkable `ProviderPlugin` for internal provider adapters;
- instance-based, case-insensitive `PluginRegistry`;
- `PluginRouter` for capability, auth, health, cooldown and explicit-source decisions;
- `PluginRuntime.fetch()` as the canonical synchronous execution path;
- `DataResult` for data, provider, dataset, quality, diagnostics and fetch time;
- canonical dataset contracts and strict/warn validation;
- safe provider diagnostics with no credentials or session material.

Initial registered contracts include:

```text
equity.ohlcv
equity.quote
equity.intraday_trades
index.ohlcv
reference.symbols
reference.company_info
fundamental.balance_sheet
fundamental.income_statement
fundamental.cash_flow
fundamental.financial_ratio
fund.nav
foreign_flow.daily
```

Additional reference contracts may be registered for approved provider slices, including current index/sector membership snapshots. Contract registration does not imply every provider supports the dataset.

## Registry split

Two registries coexist during migration:

- `vnstock/core/provider/plugin_registry.py::PluginRegistry` manages `ProviderPlugin` instances and is used by `PluginRouter`/`PluginRuntime`.
- `vnstock/core/registry.py::ProviderRegistry` is the legacy class-based registry used by older public UI dispatch paths.

New service/provider work must use the plugin runtime rather than create a third registry or direct SDK path.

## Registered provider set

The built-in registry currently includes:

| Provider | Status and purpose |
|---|---|
| KBS | Stable primary Vietnamese market provider |
| VCI | Stable secondary Vietnamese market/reference provider |
| DNSE | Vietnam equity market data with availability constraints |
| TCBS | Experimental market/reference/fundamental provider requiring provider-specific auth behavior |
| FMARKET | Fund NAV/fund data |
| MSN | Experimental selected global market data |
| FMP | Authenticated global data via API key |
| FIINQUANTX | Experimental licensed provider, explicit source only for bounded daily equity/index OHLCV and current index/sector membership snapshots |

The base package and default registry remain functional when FiinQuantX is not installed. The SDK is loaded lazily and is never vendored.

Current FiinQuantX limitations:

- exact approved SDK version and local credentials required;
- `VNSTOCK_FIINQUANTX_LICENSED=true` required as an operational acknowledgement;
- no automatic selection as a general default provider;
- no synchronous quote, company information, flow, fundamentals or broader contracts until separately verified and implemented;
- no streaming/WebSocket/order-book subscription path;
- commercial approval, session lifecycle and entitlement/quota closure remain in issue #193.

## Routing behavior

`PluginRouter` is health- and auth-aware.

Automatic routing tiers providers by usable capability and health, respects cooldown and auth policy, and records a `RoutingDecision` containing selected/rejected candidates, fallback status, reason and warnings.

Explicit source routing preserves provider identity:

- disabled provider → typed disabled failure;
- cooldown according to policy → typed cooldown failure;
- missing SDK/credentials/access for a commercial provider → typed provider failure;
- degraded/failing provider may proceed only according to explicit routing policy;
- explicit selection never silently substitutes another provider.

## Runtime behavior

`PluginRuntime.fetch(dataset, params, ...)`:

1. validates the dataset/provider request;
2. obtains a routing decision;
3. applies auth policy and provider parameter validation;
4. calls one selected provider plugin;
5. records latency and provider health outcome;
6. validates the canonical dataset contract when requested;
7. returns `DataResult` or a DataFrame carrying safe metadata.

Direct provider calls from the local service are architecture regressions.

The current runtime is synchronous. Streaming callbacks, reconnection, sequence, backpressure and subscription lifecycle require a separate architecture.

## Local data service

The `vnstock-serve` entry point exposes canonical read-only endpoints, normally bound to `127.0.0.1:6900`.

Responses use a bounded envelope:

```text
data
meta: dataset, provider, quality, runtime path, fetched time
diagnostics: routing and safe provider evidence
```

Provider metadata endpoints can expose capability and safe auth/install status. They must not expose credentials, tokens, cookies, account identifiers or raw auth responses.

Permanently forbidden endpoint families include:

```text
auth login through REST
broker/account
order
portfolio
transfer
margin
trading/execution
```

Credential configuration remains local and outside data query parameters.

## Validation expectations

Provider/platform closure evidence should include:

- protocol and registry conformance;
- dataset contract and schema-drift tests;
- explicit/auto routing tests;
- auth and secret-redaction tests;
- provider failure and valid-empty distinction;
- service runtime-path tests;
- base-package build without optional commercial SDKs;
- bounded opt-in live tests where permitted;
- exact version and license evidence for commercial providers.

A documented or mocked provider method is not licensed/live proof. Experimental capability remains partial until its linked issue acceptance criteria are met.

## Deferred architecture

Not part of the current synchronous provider platform:

- public third-party plugin marketplace/loading;
- hot reload of external plugins;
- generic version negotiation across arbitrary provider packages;
- streaming/WebSocket service runtime;
- persistent multi-process provider quota store;
- multi-tenant/public commercial data service;
- trading, broker or account functionality.

## Data-only boundary

`vnstock` is a data platform. It does not own research scoring, watchlist construction, backtesting, portfolio decisions or trading execution. Those research workflows belong in `vnalpha`, and all OpenStock components preserve the **read-only research boundary**.
