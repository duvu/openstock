# Plugin Runtime Migration Guide

## Overview

Phase 3.5 introduces `PluginRuntime` — the central execution engine for all
dataset fetches in the vnstock platform layer. It replaces the legacy
`BaseUI._dispatch()` path for migrated datasets.

## Architecture

```
DatasetRequest
    → PluginRouter.resolve(dataset, source)
        → health-aware provider selection (Phase 3)
    → provider.validate_params(dataset, params)
    → provider.fetch(dataset, params)
    → health recording (success/failure)
    → DataResult
        → DataFrame with attrs (default)
        → DataResult (when return_result=True)
```

## New components

| Component | Location | Purpose |
|-----------|----------|---------|
| `PluginRuntime` | `vnstock/core/runtime/plugin_runtime.py` | Central fetch executor |
| `DatasetRequest` | `vnstock/core/runtime/request.py` | Structured fetch input |
| `default_plugin_registry()` | `vnstock/core/runtime/bootstrap.py` | Pre-populated 7-provider registry |
| `default_runtime()` | `vnstock/core/runtime/__init__.py` | Module-level singleton runtime |

## Usage

### Basic fetch

```python
from vnstock.core.runtime import default_runtime

rt = default_runtime()

# Returns DataFrame
df = rt.fetch("equity.ohlcv", {"symbol": "FPT", "start": "2024-01-01"})

# Explicit provider
df = rt.fetch("equity.ohlcv", {"symbol": "FPT"}, source="VCI")

# Full DataResult with diagnostics
result = rt.fetch("equity.ohlcv", {"symbol": "FPT"}, return_result=True)
print(result.provider)       # "KBS"
print(result.diagnostics)    # routing, latency, etc.
```

### Contract validation

```python
df = rt.fetch(
    "equity.ohlcv",
    {"symbol": "FPT"},
    validate=True,
    quality_mode="strict",  # raises DatasetContractError on failure
)
```

### Custom runtime

```python
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.core.runtime.plugin_runtime import PluginRuntime

registry = default_plugin_registry()
rt = PluginRuntime(registry=registry, runtime_path="my_pipeline")
df = rt.fetch("equity.ohlcv", {"symbol": "FPT"})
```

## Public API migration

The `BaseUI._plugin_dispatch()` method is the fail-closed routing boundary for
migrated canonical datasets. A migrated dataset either serves the request
through its canonical provider contract or raises a **typed** failure; it never
silently drops into legacy explorer dispatch.

### Migrated methods (fail-closed)

| Public method | Dataset | Legacy fallback |
|---------------|---------|-----------------|
| `Market().equity.ohlcv(...)` | `equity.ohlcv` | No — typed failure |
| `Market().equity.quote(...)` | `equity.quote` | No — typed failure |
| `Market().equity.trades(...)` | `equity.intraday_trades` | No — typed failure |

These methods call `_plugin_dispatch()` **without** `allow_legacy_fallback`, so
authentication, entitlement, rate-limit, invalid-request, schema/contract,
cooldown, disabled-provider and provider-fetch failures all propagate to the
caller as typed exceptions.

### Non-migrated methods

All other public methods continue to use `BaseUI._dispatch()` and the legacy
routing table in `vnstock/ui/_registry.py`. These will be migrated in future
phases.

## Compatibility boundary policy

`allow_legacy_fallback` is an **opt-in compatibility boundary for genuinely
non-migrated capabilities only**. Its semantics are deliberately narrow:

- Only a *capability-absence* signal — `UnsupportedDatasetError` or
  `NoProviderForDatasetError` (the plugin platform has no provider for the
  dataset at all) — may cross the boundary.
- It applies **only** when no explicit `source` was requested. An explicitly
  selected provider never falls back to another provider or to a legacy path.
- When the boundary is crossed, a `RuntimeWarning` tagged
  `COMPAT_LEGACY_DISPATCH` is emitted and `None` is returned so the caller can
  re-route through `_dispatch()`.
- Every other failure — authentication, entitlement, rate limit, invalid
  request, schema/contract drift, cooldown, disabled provider, provider fetch —
  always propagates as a typed exception, regardless of `allow_legacy_fallback`.

Migrated datasets do not set this flag; they are fully fail-closed.

## DataResult metadata

Every `PluginRuntime.fetch()` call attaches metadata to `df.attrs`:

```python
df.attrs["provider"]       # e.g. "KBS"
df.attrs["dataset"]        # e.g. "equity.ohlcv"
df.attrs["quality_status"] # "PASS" / "FAIL" / None
df.attrs["quality"]        # quality_report dict or None
df.attrs["diagnostics"]    # routing, latency, runtime_path
df.attrs["fetched_at"]     # UTC datetime
```

## Security

`DataResult` and `df.attrs` MUST NOT contain auth credentials.
The following keys are forbidden: `password`, `api_key`, `access_token`,
`refresh_token`, `cookie`, `authorization`.

## Phase 4 dependencies

Phase 4 (service endpoints) must build exclusively on `PluginRuntime`.
The legacy `BaseUI._dispatch()` path is internal-only and will not be
exposed in the service layer.
