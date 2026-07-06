# Provider Routing

This document describes how the vnstock plugin platform routes dataset requests
to provider plugins, including health-aware auto routing, explicit source
selection, cooldown behavior, and routing policy configuration.

## Overview

The `PluginRouter` resolves a `(dataset, source)` request to a concrete
`ProviderPlugin` instance. It integrates with:

- `PluginRegistry` — the set of registered provider plugins
- `InMemoryProviderHealthStore` — runtime health tracking per `(provider, dataset)`
- `RoutingPolicy` — controls which health tiers are eligible

## Auto Routing

When `source=None` or `source="auto"`, the router selects a provider
automatically:

1. Collect all providers registered for the dataset.
2. Filter by health status according to policy (see below).
3. Within each health tier, use the per-dataset priority list as a tiebreaker.
4. Return the highest-priority eligible provider.

### Health tier order

| Status | Eligible by default | Notes |
|--------|---------------------|-------|
| HEALTHY | Yes | Preferred |
| UNKNOWN | Yes | Treated same as HEALTHY on first attempt |
| DEGRADED | Yes (fallback) | Only if no HEALTHY/UNKNOWN available |
| FAILING | No | Requires `allow_failing_fallback=True` in policy |
| DISABLED | Never | Administratively excluded |

### Cooldown

When a provider reaches the failure threshold (default: 3 consecutive
failures), it enters a cooldown period (default: 60 seconds). During
cooldown, the provider is skipped in auto routing when
`respect_cooldown=True` (default).

### Default provider priority

```python
DEFAULT_PROVIDER_PRIORITY = {
    "equity.ohlcv":  ["KBS", "VCI", "DNSE", "TCBS"],
    "index.ohlcv":   ["KBS", "VCI", "DNSE"],
    "equity.quote":  ["KBS", "VCI", "DNSE"],
    ...
}
```

Providers not in the list are appended alphabetically.

## Explicit Source Selection

When `source="KBS"` (or any named provider), the router:

1. Looks up the provider in the registry.
2. Verifies it supports the dataset.
3. Checks for DISABLED status — raises `ProviderDisabledError`.
4. Checks for active cooldown (if `respect_cooldown=True`) — raises `ProviderInCooldownError`.
5. If DEGRADED or FAILING, adds a warning to `RoutingDecision.warnings` but still
   returns the provider. Explicit requests are honoured.

## Routing Policy

```python
from vnstock.core.provider.routing import RoutingPolicy

# Default: HEALTHY first, DEGRADED fallback, no FAILING
policy = RoutingPolicy.default()

# Strict: only HEALTHY providers
policy = RoutingPolicy.strict()

# Permissive: FAILING providers allowed as last resort
policy = RoutingPolicy.permissive()

# Custom
policy = RoutingPolicy(
    prefer_healthy=True,
    allow_degraded=True,
    allow_failing_fallback=False,
    respect_cooldown=True,
    use_priority_tiebreaker=True,
)
```

## Routing Decision

Every `resolve()` call produces a `RoutingDecision`:

```python
provider = router.resolve("equity.ohlcv")
decision = router.last_decision

print(decision.selected_provider)   # "KBS"
print(decision.fallback)            # False
print(decision.warnings)            # []
print(decision.rejected)            # {"DNSE": "cooldown active"}
print(decision.health_snapshot)     # {"KBS": {"status": "HEALTHY", ...}}
```

The `router.last_diagnostics` property returns the same data as a plain dict
(backward-compatible alias).

## Error Reference

| Error | Raised when |
|-------|-------------|
| `NoProviderForDatasetError` | No provider registered for the dataset at all |
| `UnsupportedDatasetError` | Auto routing: candidates exist but none pass filters |
| `NoHealthyProviderError` | Auto routing: candidates exist but none are healthy enough |
| `UnsupportedDatasetForProviderError` | Explicit: named provider doesn't support dataset |
| `ProviderDisabledError` | Explicit: named provider is DISABLED |
| `ProviderInCooldownError` | Explicit: named provider is in cooldown |

## Usage Example

```python
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter
from vnstock.core.provider.health import InMemoryProviderHealthStore
from vnstock.core.provider.routing import RoutingPolicy
from vnstock.providers import REGISTRY

store = InMemoryProviderHealthStore()
policy = RoutingPolicy.default()
router = PluginRouter(REGISTRY, health_store=store, policy=policy)

# Auto select best provider for equity.ohlcv
provider = router.resolve("equity.ohlcv")
try:
    df = provider.fetch("equity.ohlcv", {"symbol": "FPT", "start": "2024-01-01"})
    router.record_success(provider.name, "equity.ohlcv", latency_ms=120.0)
except Exception as e:
    router.record_failure(provider.name, "equity.ohlcv", notes=str(e))
    raise
```

## Data-only Boundary

The routing layer is **data-only**. It does not handle:

- Authentication or token management
- Broker execution or order routing
- Rate limiting or throttling
- Persistent health state (use your own store for that)
