# vnstock platform evolution reference

> **Status:** historical architecture reference, not a live roadmap.
>
> The canonical OpenStock roadmap is GitHub issue [#238 — OpenStock core data and knowledge loop](https://github.com/duvu/openstock/issues/238), linked through [`../ROADMAP.md`](../ROADMAP.md). GitHub Issues own priority, dependencies, delivery status and closure evidence.

This file preserves the stable architectural direction that evolved `vnstock` from a Python SDK into the data-only provider platform used by OpenStock. Detailed historical phase text remains available in Git history.

## Stable objective

`vnstock` is the provider-independent data platform layer for Vietnamese and selected global financial market data.

It serves:

```text
Python SDK
localhost read-only REST service
batch ingestion jobs
notebooks
vnalpha research workspace
approved data tools
```

It owns:

```text
provider plugins
canonical dataset contracts
provider-specific normalization
data quality validation
schema drift detection
provider comparison and health evidence
auth-aware and health-aware routing
credentialed data-provider sessions
bounded caching and service delivery
synthetic contract fixtures and opt-in live tests
```

It does not own:

```text
research scoring or stock recommendations
pattern/watchlist strategy logic
backtesting and research artifacts
broker or account access
portfolio mutation or allocation
orders, margin, transfers or execution
```

Research workflows belong in `vnalpha`.

## Current synchronous architecture

```text
Market / Reference / Fundamental UI
or localhost read-only service
→ PluginRuntime.fetch()
→ PluginRouter
→ PluginRegistry
→ selected ProviderPlugin
→ provider-specific normalizer
→ canonical DatasetContract and quality validation
→ DataResult with provider, quality, diagnostics and lineage
```

The accepted platform includes:

- runtime-checkable `ProviderPlugin`;
- instance-based `PluginRegistry`;
- health- and auth-aware `PluginRouter`;
- synchronous `PluginRuntime` as the service execution path;
- `DataResult` metadata envelope;
- canonical dataset contracts;
- schema drift, OHLCV comparison and health scoring;
- safe credential abstractions;
- localhost read-only service endpoints;
- forbidden broker/account/order/portfolio/trading routes.

See [`docs/PLUGIN_ARCHITECTURE_STATUS.md`](docs/PLUGIN_ARCHITECTURE_STATUS.md) for the current accepted status.

## Provider model

Built-in providers currently include KBS, VCI, DNSE, TCBS, MSN, FMP, FMARKET and an experimental optional FiinQuantX slice.

A provider capability is accepted only when it has:

1. explicit data-only scope;
2. reviewed access/auth contract;
3. positive method allowlist;
4. canonical parameters and field mapping;
5. unit/time/freshness semantics;
6. truthful empty/partial/failure outcomes;
7. synthetic fixtures and contract tests;
8. bounded live evidence where permitted;
9. safe diagnostics and secret redaction;
10. commercial persistence/exposure decisions where relevant.

Provider availability does not change the canonical data-quality roadmap. Optional commercial sources must conform to the same contracts used by public providers.

## Platform boundaries still requiring separate work

The synchronous plugin platform does not automatically provide:

- streaming/WebSocket subscription lifecycle;
- persistent cross-process quota accounting;
- complete quality contracts for every reference/fundamental dataset;
- public multi-tenant commercial data service;
- arbitrary third-party plugin marketplace/hot loading.

Each requires a focused GitHub issue and reviewed design before implementation.

## Governance

- Use [#238](https://github.com/duvu/openstock/issues/238) for current priority and dependency order.
- Use focused implementation issues for provider/dataset acceptance criteria.
- Use OpenSpec for linked requirements, design, tasks and validation evidence.
- Do not create a second phase queue in component documentation.
- Keep all data-provider work within the **read-only research boundary**.
