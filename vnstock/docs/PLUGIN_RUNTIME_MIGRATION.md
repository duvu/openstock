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

The `BaseUI._plugin_dispatch()` method routes calls through `PluginRuntime`.
Migrated methods use `_plugin_dispatch` with `allow_legacy_fallback=True` to
ensure backward compatibility during the transition period.

### Migrated methods (Phase 3.5)

| Public method | Dataset | Legacy fallback |
|---------------|---------|-----------------|
| `Market().equity.ohlcv(...)` | `equity.ohlcv` | Yes (temporary) |
| `Market().equity.quote(...)` | `equity.quote` | Yes (temporary) |
| `Market().equity.trades(...)` | `equity.intraday_trades` | Yes (temporary) |

### Non-migrated methods

All other public methods continue to use `BaseUI._dispatch()` and the legacy
routing table in `vnstock/ui/_registry.py`. These will be migrated in future
phases.

## Legacy fallback policy

- `allow_legacy_fallback=True` — PluginRuntime failure is caught, a
  `RuntimeWarning` is emitted, and the caller falls back to `_dispatch()`.
  This is the default for migrated public methods during Phase 3.5.
- `allow_legacy_fallback=False` — PluginRuntime failure propagates to the
  caller. Use this in batch/ingestion pipelines where silent fallback is
  unacceptable.

Migrated datasets will move to `allow_legacy_fallback=False` once all
providers are stable (Phase 4+).

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
