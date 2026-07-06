# Change Proposal: Close vnstock Plugin Platform Phases 1 to 4

## Change ID

`close-vnstock-plugin-platform-phases-1-to-4`

## Summary

Close the remaining hardening gaps for vnstock Phase 1, Phase 2, Phase 3, Phase 3.5, and Phase 4.

The codebase already has the main plugin-platform primitives:

- `ProviderPlugin` protocol;
- plugin registry;
- plugin router;
- provider health model;
- auth-aware routing policy;
- `PluginRuntime`;
- `DataResult`;
- default built-in provider bootstrap;
- local data service path through PluginRuntime;
- canonical data-service endpoint mapper;
- DataResult service envelope.

The remaining gap is not feature absence. The remaining gap is closure quality: stronger tests, explicit phase status documentation, stricter no-legacy regression guards, provider capability verification, and roadmap alignment.

## Why Phase 1 was not marked 100 percent

Phase 1 has the core architecture, but it should not be marked fully closed until these are proven:

1. all initial dataset contracts are registered and tested;
2. `DataResult` metadata round-trip is tested through runtime and public outputs;
3. the plugin registry and legacy registry boundary is documented and regression-tested;
4. every migrated public data path is guarded against falling back to legacy dispatch;
5. a phase closure status document states what is closed and what remains future scope.

Without those closure guards, the architecture exists but is not yet locked.

## Target closure score

This change aims to bring the phases to:

```text
Phase 1   Core contracts and plugin foundation      97-99%
Phase 2   Provider plugin normalization             97-99%
Phase 3   Health-aware and auth-aware routing       97-99%
Phase 3.5 PluginRuntime default execution path      97-99%
Phase 4   Auth-aware local data service runtime     97-99%
```

This does not mean every future platform feature is complete. It means the defined phase scope is closed, tested, documented, and protected from regression.

## Goals

### G1. Close Phase 1: core contracts and plugin foundation

- Verify `ProviderPlugin` conformance.
- Verify `PluginRegistry` behavior.
- Verify `DataResult` metadata and DataFrame attrs behavior.
- Verify dataset contracts for initial supported datasets.
- Document the boundary between plugin registry and legacy registry.

### G2. Close Phase 2: provider plugin normalization

- Verify all built-in providers are registered through `default_plugin_registry()`.
- Verify built-in provider capability declarations are valid and honest.
- Verify unsupported datasets are explicitly unsupported, not silently claimed.
- Verify provider plugins conform to the `ProviderPlugin` protocol.

### G3. Close Phase 3: routing and diagnostics

- Verify auto routing, explicit routing, fallback, cooldown, and health behavior.
- Verify auth policy filtering behavior.
- Verify routing diagnostics are stable and serializable.
- Verify provider success/failure updates health state.

### G4. Close Phase 3.5: PluginRuntime default path

- Verify runtime fetch returns `DataResult` with provider, dataset, data, quality status, diagnostics, and fetched timestamp.
- Verify service data endpoints call `PluginRuntime`.
- Verify migrated public SDK paths attach runtime metadata.
- Verify tests fail if migrated paths bypass runtime.

### G5. Close Phase 4: local data service runtime

- Verify canonical v1 data endpoints route through PluginRuntime.
- Verify service responses use the stable `data/meta/diagnostics` envelope.
- Verify provider metadata endpoints use plugin registry.
- Verify auth status is safe and functional.
- Verify data-only boundaries remain closed.
- Verify Docker/local service entrypoints remain valid.

## Non-goals

This change does not implement:

- external third-party plugin package discovery;
- plugin marketplace;
- semantic version negotiation for external plugins;
- new providers;
- rate limiter and batch ingestion;
- archive/storage sinks;
- MCP server;
- TUI;
- strategy scanner;
- portfolio or trading execution.

External plugin ecosystem work belongs to a future phase after the internal plugin platform is closed.

## Success criteria

The change is successful when:

1. each phase has explicit closure criteria;
2. each phase has tests tied to those criteria;
3. `docs/PLUGIN_ARCHITECTURE_STATUS.md` records current status and future scope;
4. service and runtime tests prove runtime-first execution;
5. provider capability tests cover all built-in providers;
6. roadmap no longer implies unfinished work inside closed phase scope;
7. remaining items are explicitly moved to future phases.

## Validation commands

Run inside the `vnstock` submodule:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
