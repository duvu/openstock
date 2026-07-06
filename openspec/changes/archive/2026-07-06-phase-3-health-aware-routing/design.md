# Design: Phase 3 — Health-aware Routing and Provider Diagnostics

## Overview

Phase 3 upgrades provider routing from simple provider resolution into health-aware provider selection.

The design introduces:

- `ProviderHealth`
- `ProviderHealthStore`
- `RoutingPolicy`
- `RoutingDecision`
- routing diagnostics
- provider cooldown
- provider comparison utilities

The implementation must remain compatible with Phase 1 core contracts and Phase 2 provider plugin normalization.

## Design principles

### Explain provider decisions

Every automatic route should explain why a provider was selected and why other providers were skipped.

### Preserve explicit source behavior

When a caller explicitly requests a provider, the router must not silently replace it with another provider. It may attach warnings if the requested provider has known issues.

### Keep health dataset-specific

A provider can be healthy for one dataset and degraded for another. Health should be tracked at least by `provider + dataset`.

### Keep storage simple

Phase 3 should use an in-memory health store. Persistent health history belongs to later platform phases.

### Keep data-only boundary

Provider health and diagnostics are data reliability features only. They must not become trading analysis or recommendation features.

## Core model

`ProviderHealth` should track:

- provider
- dataset
- status
- latency
- freshness
- last success
- last failure
- success count
- failure count
- cooldown timestamp
- notes

Allowed statuses:

- `HEALTHY`
- `DEGRADED`
- `FAILING`
- `UNKNOWN`
- `DISABLED`

## Health store

`ProviderHealthStore` should support:

- get health by provider and dataset
- set health
- record success
- record failure
- list health by dataset

Phase 3 should implement `InMemoryProviderHealthStore`.

## Routing policy

The default routing policy should:

- prefer healthy providers
- allow degraded providers only when needed
- avoid failing providers by default
- respect cooldown for automatic routing
- use configured provider priority as a tie-breaker
- attach diagnostics to results

## Automatic routing

For `source=None` or `source="auto"`, the router should:

1. Find providers that support the requested dataset.
2. Attach health state.
3. Skip providers in active cooldown.
4. Prefer healthy providers.
5. Fall back to degraded providers only when policy allows.
6. Avoid failing providers unless policy explicitly allows it.
7. Use priority as a tie-breaker.
8. Attach routing diagnostics.

## Explicit routing

For explicit source, the router should:

1. Resolve the requested provider.
2. Confirm the provider supports the dataset.
3. Attach health warning if needed.
4. Proceed unless the provider is disabled or unsupported.

Explicit source must not be silently replaced.

## Routing diagnostics

Routing diagnostics should include:

- dataset
- requested source
- selected provider
- candidate providers
- rejected providers
- routing reason
- fallback flag
- health snapshot
- warnings

Diagnostics should be safe to attach to `DataResult` and `DataFrame.attrs`.

## Provider comparison

Phase 3 should expand comparison utilities:

- `compare_ohlcv`
- `compare_quote`
- `compare_intraday_shape`
- `compare_coverage`
- `compare_freshness`

The initial comparison goal is reliability assessment, not investment analysis.

## DataResult integration

Routing diagnostics should be attached to `DataResult.diagnostics`.

For public DataFrame returns, diagnostics should be available through `df.attrs["diagnostics"]` while existing quality metadata remains compatible.

## Error model

Phase 3 should add or extend these platform errors:

- `NoProviderForDatasetError`
- `NoHealthyProviderError`
- `ProviderInCooldownError`
- `ProviderDisabledError`

Auto routing errors should include candidate and rejection context where practical.

## Configuration

Phase 3 should support lightweight provider priority by dataset.

Initial priority intent:

- `equity.ohlcv`: KBS, VCI, DNSE, TCBS
- `equity.quote`: KBS, VCI, DNSE, TCBS
- `equity.intraday_trades`: KBS, VCI, DNSE
- `fund.nav`: FMarket

Future config may move to YAML or environment variables.

## Test strategy

Tests should cover:

- health model
- health store
- cooldown behavior
- automatic routing
- explicit routing
- routing diagnostics
- comparison utilities
- DataFrame metadata compatibility

Key scenarios:

- automatic routing selects healthy provider
- automatic routing skips cooldown provider
- automatic routing falls back to degraded provider
- automatic routing rejects failing provider by default
- explicit routing preserves requested provider
- success updates health
- failure updates health
- diagnostics include selected and rejected providers

## Migration strategy

1. Add health models, store, and diagnostics models.
2. Wire router to read health store while defaulting missing health to `UNKNOWN`.
3. Implement priority-based routing with health ordering.
4. Attach routing diagnostics to results.
5. Record success and failure around fetch calls.
6. Add cooldown behavior.
7. Expand comparison utilities.

## Open questions

1. Should `UNKNOWN` rank above or below `DEGRADED`?
2. Should explicit source ignore cooldown by default?
3. Should provider health update after fetch success or after validation success?
4. What are the first freshness thresholds per dataset?
5. Should comparison mismatch automatically mark a provider as degraded?
6. Should provider priority be hardcoded first or configured externally?
