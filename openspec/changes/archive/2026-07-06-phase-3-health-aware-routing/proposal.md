# Change Proposal: Phase 3 — Health-aware Routing and Provider Diagnostics

## Change ID

`phase-3-health-aware-routing`

## Summary

Introduce health-aware provider routing and structured provider diagnostics for `vnstock`.

This phase upgrades `ProviderRouter` from simple provider resolution into a policy-driven routing layer that can evaluate:

- provider capability;
- provider health;
- freshness;
- recent failures;
- cooldown state;
- explicit source forcing;
- fallback behavior;
- diagnostics metadata.

This phase also expands provider comparison beyond basic OHLCV comparison and prepares the routing layer for later auth-aware routing, rate limiting, batch ingestion, API service, and MCP tools.

## Motivation

After Phase 1 and Phase 2, `vnstock` should have:

- dataset contracts;
- provider plugin interface;
- provider registry;
- provider router skeleton;
- `DataResult`;
- normalized internal provider plugins;
- provider capability declarations.

However, `source="auto"` still needs a robust decision layer.

Without health-aware routing, the platform may:

- select a degraded provider even when healthier providers exist;
- retry failing providers too aggressively;
- hide provider quality/freshness issues from downstream consumers;
- make batch ingestion unreliable;
- provide weak diagnostics to `vnalpha`, API, TUI, and MCP consumers.

The goal of Phase 3 is:

```text
Make provider selection explainable, health-aware, testable, and safe.
```

## Goals

### G1. Add provider health model

Define a structured provider health model with dataset-level health status.

Health should be tracked per:

```text
provider
dataset
optional endpoint or capability
```

### G2. Add health-aware routing

Upgrade `ProviderRouter` so that `source="auto"` selects a provider using:

- dataset support;
- provider health;
- cooldown state;
- freshness;
- configured priority;
- fallback policy.

### G3. Preserve explicit source behavior

If the user forces a provider with `source="TCBS"` or equivalent, the router should respect the request if the provider supports the dataset.

If the provider is degraded or failing, the call may still proceed, but diagnostics must include a warning.

### G4. Add routing diagnostics

Every routed request should include explainable diagnostics:

- requested dataset;
- requested source;
- selected provider;
- candidate providers;
- rejected providers;
- routing reason;
- fallback used;
- health snapshot;
- cooldown state;
- freshness note.

### G5. Add provider health store

Add an internal component to store/update provider health signals.

This does not need persistent storage in Phase 3. An in-memory health store is acceptable.

### G6. Add failure recording and cooldown

Provider failures should update health state and may place a provider in cooldown for a dataset.

Cooldown should prevent repeated immediate selection of known failing providers during auto routing.

### G7. Expand comparison APIs

Expand provider comparison beyond OHLCV.

Target comparison functions:

- `compare_ohlcv`
- `compare_quote`
- `compare_intraday_shape`
- `compare_coverage`
- `compare_freshness`

### G8. Keep public API backward-compatible

Existing public API calls must continue working.

### G9. Keep data-only boundary

No trading signals, stock recommendations, broker/account APIs, or order execution should be introduced.

## Non-goals

This phase does not implement:

- credential/auth-aware routing;
- provider login/session management;
- rate limiter;
- batch ingestion runtime;
- storage sinks;
- REST API;
- CLI/TUI;
- MCP server;
- external plugin packages;
- trading analysis;
- stock recommendation;
- broker execution;
- account APIs;
- order placement.

## Prerequisites

Phase 3 depends on:

```text
Phase 1 — Core contracts and internal plugin foundation
Phase 2 — Normalize existing providers as internal plugins
```

Minimum expected prerequisites:

- `DatasetContract` exists;
- `ProviderPlugin` exists;
- `ProviderRegistry` exists;
- `ProviderRouter` exists;
- `DataResult` exists;
- provider plugins declare capabilities;
- provider plugins expose diagnostics;
- provider plugins are registered in the registry.

## Scope

### In scope

```text
vnstock/core/provider/health.py
vnstock/core/provider/router.py
vnstock/core/provider/diagnostics.py
vnstock/core/provider/comparison.py
vnstock/core/provider/cooldown.py
tests/unit/core/provider/
tests/contracts/providers/
docs/PROVIDER_ROUTING.md
docs/PROVIDER_DIAGNOSTICS.md
```

### Out of scope

```text
vnstock/core/auth/
vnstock/core/rate_limit/
vnstock/api/
vnstock/mcp/
vnstock/tui/
vnstock/storage/
vnalpha/
```

## Proposed architecture

```text
Public UI / SDK call
        ↓
Dataset + params
        ↓
ProviderRouter
        ↓
ProviderRegistry
        ↓
ProviderHealthStore
        ↓
RoutingPolicy
        ↓
Selected ProviderPlugin
        ↓
ProviderPlugin.fetch()
        ↓
Validation / normalization
        ↓
DataResult + diagnostics
```

## Routing decision order

For `source="auto"`:

```text
1. Find providers that support the requested dataset.
2. Exclude providers in active cooldown.
3. Prefer HEALTHY providers.
4. Allow DEGRADED providers only if no HEALTHY provider is available.
5. Avoid FAILING providers unless no alternative exists and policy allows fallback.
6. Use configured provider priority as tie-breaker.
7. Attach routing diagnostics.
```

For explicit source:

```text
1. Resolve requested provider.
2. Confirm provider supports dataset.
3. Attach health warning if provider is DEGRADED or FAILING.
4. Proceed unless provider is hard-disabled.
```

## Success criteria

Phase 3 is complete when:

- provider health model exists;
- provider health store exists;
- router supports health-aware auto selection;
- router respects explicit source forcing;
- provider cooldown works;
- routing diagnostics are attached to `DataResult` or `DataFrame.attrs`;
- comparison APIs are expanded;
- unit tests simulate healthy, degraded, failing, and cooldown states;
- public API remains backward-compatible;
- data-only boundary remains enforced.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
