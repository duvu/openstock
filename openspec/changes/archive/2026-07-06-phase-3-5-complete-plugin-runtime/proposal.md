# Change Proposal: Phase 3.5 — Complete Plugin Runtime and Retire Legacy Dispatch

## Change ID

`phase-3-5-complete-plugin-runtime`

## Summary

Make the plugin runtime the default execution path for `vnstock` public data APIs and retire the legacy dispatch path before implementing Phase 4 Auth-aware Local Data Service.

This phase bridges the gap between:

- Phase 1: core plugin contracts;
- Phase 2: provider plugins;
- Phase 3: health-aware routing;
- Phase 4: local service + command-based auth.

The goal is to ensure all public data access flows through the same platform boundary:

```text
Public API
→ Dataset request
→ PluginRuntime
→ PluginRegistry
→ PluginRouter
→ ProviderPlugin
→ DatasetContract validation
→ DataResult
→ DataFrame
```

After this phase, Phase 4 can safely add service/auth on top of the plugin runtime instead of supporting both plugin and legacy execution paths.

## Problem

The repository now has internal plugin architecture, provider plugins, and health-aware routing. However, some public APIs still route through legacy explorer/provider paths directly.

This creates several risks:

- Phase 4 service endpoints may bypass plugin routing.
- Auth-aware routing may need duplicate logic for legacy providers.
- Provider health/cooldown may not apply consistently.
- Diagnostics may be incomplete.
- DataResult metadata may not be attached uniformly.
- Public API behavior may diverge from service/API behavior.
- Legacy code may continue expanding outside the plugin boundary.

## Goals

### G1. Introduce PluginRuntime

Add a single runtime facade that all public data calls use.

Suggested module:

```text
vnstock/core/runtime/plugin_runtime.py
```

Responsibilities:

- resolve dataset contract;
- resolve provider through `PluginRouter`;
- call provider plugin;
- validate/normalize output;
- wrap result in `DataResult`;
- attach diagnostics;
- return backward-compatible `DataFrame`.

### G2. Make plugin runtime default for supported datasets

Public APIs such as `Market`, `Reference`, `Fundamental`, and `Retail` should route supported datasets through `PluginRuntime` by default.

### G3. Retire legacy dispatch path

Remove direct public routing through old provider/explorer dispatch for datasets already supported by plugins.

Legacy provider clients may remain as low-level implementation details behind provider plugins, but they must not be public dispatch paths.

### G4. Add compatibility layer

Maintain backward-compatible public signatures where practical.

Existing calls should continue to return `pandas.DataFrame`.

### G5. Add migration gate

Any unsupported dataset may temporarily use a controlled fallback, but fallback must be explicit, measured, and documented.

### G6. Add plugin runtime tests

Add integration tests proving public calls go through plugin runtime.

### G7. Prepare Phase 4

After this phase, Phase 4 service/auth should depend only on `PluginRuntime`, not legacy dispatch.

## Non-goals

This phase does not implement:

- AuthManager;
- CredentialStore;
- Docker runtime;
- REST API service;
- MCP server;
- external plugin packages;
- broker/account/order APIs;
- trading signals;
- stock recommendation;
- storage sinks;
- batch ingestion runtime.

## Scope

### In scope

```text
vnstock/core/runtime/
vnstock/core/runtime/plugin_runtime.py
vnstock/core/provider/plugin_registry.py
vnstock/core/provider/plugin_router.py
vnstock/providers/*/plugin.py
vnstock/explorer/* compatibility wrapping where needed
vnstock/market.py or equivalent public UI layer
vnstock/reference.py or equivalent public UI layer
vnstock/fundamental.py or equivalent public UI layer
tests/integration/plugin_runtime/
tests/unit/core/runtime/
docs/PLUGIN_RUNTIME_MIGRATION.md
```

### Out of scope

```text
vnstock/core/auth/
vnstock/service/
vnstock/mcp/
vnstock/tui/
vnstock/storage/
```

## Success criteria

This phase is complete when:

- `PluginRuntime` exists;
- supported public APIs route through `PluginRuntime`;
- public `Market().equity.ohlcv(...)` goes through plugin registry/router;
- direct legacy dispatch is removed for supported datasets;
- legacy provider clients are used only behind provider plugins;
- `DataResult` metadata is attached consistently;
- routing diagnostics are available through `DataFrame.attrs`;
- compatibility tests pass;
- fallback usage is explicit and observable;
- Phase 4 can build service endpoints on top of `PluginRuntime`.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/integration/plugin_runtime tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
