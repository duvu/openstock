# Tasks: Close vnstock Plugin Platform Phases 1 to 4

## 0. Baseline confirmation

- [ ] Confirm `ProviderPlugin` protocol is present.
- [ ] Confirm `PluginRegistry` manages plugin instances.
- [ ] Confirm `PluginRouter` supports health-aware routing.
- [ ] Confirm auth-aware routing policies are available.
- [ ] Confirm `PluginRuntime` exists and wraps provider output into `DataResult`.
- [ ] Confirm `default_plugin_registry()` registers built-in providers.
- [ ] Confirm local service data path uses `PluginRuntime`.
- [ ] Confirm canonical data-service mapper and DataResult serializer exist.

## 1. Phase 1 closure: core contracts and plugin foundation

- [ ] Add/complete tests for `ProviderPlugin` runtime conformance using fake providers.
- [ ] Add/complete tests for `PluginRegistry.register()`.
- [ ] Add/complete tests for `PluginRegistry.get()`.
- [ ] Add/complete tests for `PluginRegistry.providers_for()`.
- [ ] Add/complete tests for `PluginRegistry.capability_matrix()` deterministic output.
- [ ] Add/complete tests for duplicate provider registration rejection.
- [ ] Add/complete tests for missing provider lookup error.
- [ ] Add/complete tests for `DataResult.to_dataframe()` preserving attrs.
- [ ] Add/complete tests for `DataResult` metadata fields.
- [ ] Verify initial dataset contracts are registered or explicitly documented as deferred.
- [ ] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 1.

## 2. Phase 2 closure: provider plugin normalization

- [ ] Add provider conformance test for every provider in `default_plugin_registry()`.
- [ ] Assert built-in provider names include KBS, VCI, DNSE, TCBS, FMARKET, MSN, and FMP if available.
- [ ] Assert every built-in provider has valid `capabilities()` output.
- [ ] Assert capability records contain `supported` and `status`.
- [ ] Assert capability statuses are in the allowed set.
- [ ] Assert supported dataset names are known dataset names.
- [ ] Assert unsupported dataset fetch is rejected explicitly.
- [ ] Assert provider diagnostics are dict-like and safe to serialize.
- [ ] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 2.

## 3. Phase 3 closure: health-aware and auth-aware routing

- [ ] Add test: auto routing picks preferred healthy provider.
- [ ] Add test: degraded provider is fallback only when configured.
- [ ] Add test: failing provider is excluded by default.
- [ ] Add test: disabled provider is never selected.
- [ ] Add test: cooldown is honored.
- [ ] Add test: explicit provider selection works.
- [ ] Add test: explicit degraded/failing provider emits diagnostics or warnings.
- [ ] Add test: routing decision contains selected provider and candidates.
- [ ] Add test: `record_success()` updates health store.
- [ ] Add test: `record_failure()` updates health store.
- [ ] Add test: auth policy `prefer_no_auth` orders public providers first.
- [ ] Add test: auth policy `forbid_authenticated` excludes authenticated providers.
- [ ] Add test: auth policy `require_authenticated` excludes public providers.
- [ ] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 3.

## 4. Phase 3.5 closure: PluginRuntime default execution path

- [ ] Add test: `PluginRuntime.fetch(..., return_result=True)` returns `DataResult`.
- [ ] Add test: runtime validates params before provider fetch.
- [ ] Add test: runtime records success after successful fetch.
- [ ] Add test: runtime records failure after provider fetch error.
- [ ] Add test: runtime attaches routing diagnostics.
- [ ] Add test: runtime attaches `runtime_path = plugin_runtime`.
- [ ] Add test: DataFrame return path preserves metadata attrs.
- [ ] Add test: strict contract validation raises expected error.
- [ ] Add test: migrated public SDK path has runtime metadata or is explicitly documented as not migrated.
- [ ] Add regression guard: migrated paths must not silently bypass PluginRuntime.
- [ ] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 3.5.

## 5. Phase 4 closure: local data service runtime

- [ ] Add test: `/v1/equity/ohlcv` calls injected fake runtime.
- [ ] Add test: `/v1/equity/ohlcv` returns `data`, `meta`, and `diagnostics`.
- [ ] Add test: service response includes `meta.dataset = equity.ohlcv`.
- [ ] Add test: service response includes `meta.runtime_path = plugin_runtime`.
- [ ] Add test: canonical endpoint mapper covers all Phase 4 endpoints.
- [ ] Add test: provider endpoint uses plugin registry output.
- [ ] Add test: provider capabilities endpoint uses capability matrix.
- [ ] Add test: auth status works with no auth manager.
- [ ] Add test: auth status works with mock auth manager.
- [ ] Add test: unavailable endpoint groups stay unavailable.
- [ ] Add test: CLI entrypoints exist in package metadata.
- [ ] Add docs for Docker/local-only service startup.
- [ ] Add `docs/PLUGIN_ARCHITECTURE_STATUS.md` section for Phase 4.

## 6. Documentation and roadmap alignment

- [ ] Create or update `vnstock/docs/PLUGIN_ARCHITECTURE_STATUS.md`.
- [ ] Include phase scorecard with 97-99% target status.
- [ ] Explain why external plugin discovery is future scope.
- [ ] Explain why rate limiter, storage sinks, MCP, and TUI are future phases.
- [ ] Update `vnstock/roadmap.md` to mark Phase 1-4 closed or closure-ready after tests pass.
- [ ] Ensure roadmap does not mix closed phase scope with future phase scope.

## 7. Validation

Run inside the `vnstock` submodule:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

- [ ] Phase 1 score can be raised to 97-99%.
- [ ] Phase 2 score can be raised to 97-99%.
- [ ] Phase 3 score can be raised to 97-99%.
- [ ] Phase 3.5 score can be raised to 97-99%.
- [ ] Phase 4 score can be raised to 97-99%.
- [ ] Remaining future work is clearly separated from closed phase scope.
