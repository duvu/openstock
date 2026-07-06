# Tasks: Close vnstock Plugin Platform Phases 1 to 4

## 0. Baseline confirmation

- [x] Confirm `ProviderPlugin` protocol is present.
- [x] Confirm `PluginRegistry` manages plugin instances.
- [x] Confirm `PluginRouter` supports health-aware routing.
- [x] Confirm auth-aware routing policies are available.
- [x] Confirm `PluginRuntime` exists and wraps provider output into `DataResult`.
- [x] Confirm `default_plugin_registry()` registers built-in providers.
- [x] Confirm local service data path uses `PluginRuntime`.
- [x] Confirm canonical data-service mapper and DataResult serializer exist.

## 1. Phase 1 closure: core contracts and plugin foundation

- [x] Add/complete tests for `ProviderPlugin` runtime conformance using fake providers.
- [x] Add/complete tests for `PluginRegistry.register()`.
- [x] Add/complete tests for `PluginRegistry.get()`.
- [x] Add/complete tests for `PluginRegistry.providers_for()`.
- [x] Add/complete tests for `PluginRegistry.capability_matrix()` deterministic output.
- [x] Add/complete tests for duplicate provider registration rejection.
- [x] Add/complete tests for missing provider lookup error.
- [x] Add/complete tests for `DataResult.to_dataframe()` preserving attrs.
- [x] Add/complete tests for `DataResult` metadata fields.
- [x] Verify initial dataset contracts are registered or explicitly documented as deferred.
- [x] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 1.

## 2. Phase 2 closure: provider plugin normalization

- [x] Add provider conformance test for every provider in `default_plugin_registry()`.
- [x] Assert built-in provider names include KBS, VCI, DNSE, TCBS, FMARKET, MSN, and FMP if available.
- [x] Assert every built-in provider has valid `capabilities()` output.
- [x] Assert capability records contain `supported` and `status`.
- [x] Assert capability statuses are in the allowed set.
- [x] Assert supported dataset names are known dataset names.
- [x] Assert unsupported dataset fetch is rejected explicitly.
- [x] Assert provider diagnostics are dict-like and safe to serialize.
- [x] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 2.

## 3. Phase 3 closure: health-aware and auth-aware routing

- [x] Add test: auto routing picks preferred healthy provider.
- [x] Add test: degraded provider is fallback only when configured.
- [x] Add test: failing provider is excluded by default.
- [x] Add test: disabled provider is never selected.
- [x] Add test: cooldown is honored.
- [x] Add test: explicit provider selection works.
- [x] Add test: explicit degraded/failing provider emits diagnostics or warnings.
- [x] Add test: routing decision contains selected provider and candidates.
- [x] Add test: `record_success()` updates health store.
- [x] Add test: `record_failure()` updates health store.
- [x] Add test: auth policy `prefer_no_auth` orders public providers first.
- [x] Add test: auth policy `forbid_authenticated` excludes authenticated providers.
- [x] Add test: auth policy `require_authenticated` excludes public providers.
- [x] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 3.

## 4. Phase 3.5 closure: PluginRuntime default execution path

- [x] Add test: `PluginRuntime.fetch(..., return_result=True)` returns `DataResult`.
- [x] Add test: runtime validates params before provider fetch.
- [x] Add test: runtime records success after successful fetch.
- [x] Add test: runtime records failure after provider fetch error.
- [x] Add test: runtime attaches routing diagnostics.
- [x] Add test: runtime attaches `runtime_path = plugin_runtime`.
- [x] Add test: DataFrame return path preserves metadata attrs.
- [x] Add test: strict contract validation raises expected error.
- [x] Add test: migrated public SDK path has runtime metadata or is explicitly documented as not migrated.
- [x] Add regression guard: migrated paths must not silently bypass PluginRuntime.
- [x] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 3.5.

## 5. Phase 4 closure: local data service runtime

- [x] Add test: `/v1/equity/ohlcv` calls injected fake runtime.
- [x] Add test: `/v1/equity/ohlcv` returns `data`, `meta`, and `diagnostics`.
- [x] Add test: service response includes `meta.dataset = equity.ohlcv`.
- [x] Add test: service response includes `meta.runtime_path = plugin_runtime`.
- [x] Add test: canonical endpoint mapper covers all Phase 4 endpoints.
- [x] Add test: provider endpoint uses plugin registry output.
- [x] Add test: provider capabilities endpoint uses capability matrix.
- [x] Add test: auth status works with no auth manager.
- [x] Add test: auth status works with mock auth manager.
- [x] Add test: unavailable endpoint groups stay unavailable.
- [x] Add test: CLI entrypoints exist in package metadata.
- [x] Add docs for Docker/local-only service startup.
- [x] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 4.

## 6. Documentation and roadmap alignment

- [x] Create or update `vnstock/docs/PLUGIN_ARCHITECTURE_STATUS.md`.
- [x] Include phase scorecard with 97-99% target status.
- [x] Explain why external plugin discovery is future scope.
- [x] Explain why rate limiter, storage sinks, MCP, and TUI are future phases.
- [x] Update `vnstock/roadmap.md` to mark Phase 1-4 closed or closure-ready after tests pass.
- [x] Ensure roadmap does not mix closed phase scope with future phase scope.

## 7. Validation

Run inside the `vnstock` submodule:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

- [x] Phase 1 score can be raised to 97-99%.
- [x] Phase 2 score can be raised to 97-99%.
- [x] Phase 3 score can be raised to 97-99%.
- [x] Phase 3.5 score can be raised to 97-99%.
- [x] Phase 4 score can be raised to 97-99%.
- [x] Remaining future work is clearly separated from closed phase scope.
