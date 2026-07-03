# Tasks: Close vnstock Phase 3.5 and Phase 4 Service Runtime

## 0. Baseline audit

- [x] Confirm `PluginRuntime` exists and returns `DataResult` when `return_result=True`.
- [x] Confirm `default_plugin_registry()` registers built-in provider plugins.
- [x] Confirm current service data endpoint bypasses `PluginRuntime`.
- [x] Confirm current provider endpoints use legacy registry or return incomplete data.
- [x] Confirm auth status call sites are consistent with `AuthManager.auth_status_all()`.
- [x] Confirm forbidden endpoint tests currently pass.

## 1. Add service dataset mapper

- [x] Create `vnstock/service/dataset_mapper.py`.
- [x] Map canonical HTTP paths to dataset names.
- [x] Preserve `source`, `validate`, and `quality_mode` query params.
- [x] Reject unknown datasets clearly.
- [x] Add tests for known paths.
- [x] Add tests for unknown paths.

## 2. Add runtime dependency helper

- [x] Create `vnstock/service/runtime_dependency.py`.
- [x] Initialize `default_plugin_registry()`.
- [x] Initialize `PluginRuntime`.
- [x] Support test injection of fake runtime.
- [x] Avoid direct legacy `Vnstock` initialization in service data path.

## 3. Add DataResult serializer

- [x] Create `vnstock/service/serializers.py`.
- [x] Implement `serialize_data_result(result, request_context)`.
- [x] Convert DataFrame to records.
- [x] Include `meta.request_id`.
- [x] Include `meta.dataset`.
- [x] Include `meta.provider`.
- [x] Include `meta.quality_status`.
- [x] Include `meta.fetched_at`.
- [x] Include `meta.source_requested`.
- [x] Include `meta.runtime_path`.
- [x] Include diagnostics where available.
- [x] Redact sensitive diagnostics.
- [x] Add tests for envelope shape.
- [x] Add tests for redaction.

## 4. Rewrite service data handlers

- [x] Replace legacy `_handle_data()` behavior with PluginRuntime path.
- [x] Add canonical path dispatch for `/v1/equity/*`.
- [x] Add canonical path dispatch for `/v1/index/*`.
- [x] Add canonical path dispatch for `/v1/reference/*`.
- [x] Add canonical path dispatch for `/v1/company/*`.
- [x] Add canonical path dispatch for `/v1/fundamental/*`.
- [x] Add canonical path dispatch for `/v1/fund/*`.
- [x] Parse query params into runtime params.
- [x] Call `PluginRuntime.fetch(dataset, params, source=..., validate=..., quality_mode=..., return_result=True)`.
- [x] Serialize returned `DataResult`.
- [x] Add test that a fake runtime is called by `/v1/equity/ohlcv`.
- [x] Add test that legacy `Vnstock` is not called by data endpoints.

## 5. Fix provider endpoints

- [x] Replace legacy provider registry usage in service endpoints.
- [x] `/v1/providers` should return `default_plugin_registry().names()`.
- [x] `/v1/providers/capabilities` should return `default_plugin_registry().capability_matrix()`.
- [x] `/v1/providers/health` should return safe health store data.
- [x] Add tests proving provider list includes core providers where available.

## 6. Fix auth status compatibility

- [x] Update `AuthManager.auth_status_all()` to accept `providers: list[str] | None = None` or update all call sites to pass a provider list.
- [x] Ensure CLI `vnstock-auth status` works.
- [x] Ensure service `GET /v1/auth/status` works when auth manager is configured.
- [x] Ensure auth status responses do not expose credential material.
- [x] Add regression tests for service auth status with mocked sensitive fields.

## 7. Keep forbidden boundary closed

- [x] Keep forbidden gate for auth-login/order/account/portfolio/transfer/margin/trading paths.
- [x] Add REST login path coverage.
- [x] Add trading/account/portfolio execution path coverage.

## 8. Error handling

- [x] Map unsupported dataset to 404.
- [x] Map no healthy provider to 503.
- [x] Map provider fetch error to 502.
- [x] Map dataset contract error to 422.
- [x] Map bad params to 400.
- [x] Ensure error response includes `error`, `message`, `dataset`, and `request_id` where available.
- [x] Add tests for unsupported dataset and provider fetch error.

## 9. Roadmap/docs alignment

- [x] Update `vnstock/roadmap.md` to remove REST login/logout endpoints from REST API target.
- [x] Mark Phase 3.5 as closable only after service path uses PluginRuntime.
- [x] Mark Phase 4 as local data service runtime, not public broker-login backend.
- [x] Keep `vnstock/docs/DATA_SERVICE_DESIGN.md` aligned with implementation.

## 10. Validation

Run inside the `vnstock` submodule:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core/runtime tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

- [x] `/v1/equity/ohlcv` returns `data`, `meta`, and `diagnostics`.
- [x] `meta.dataset == "equity.ohlcv"`.
- [x] `meta.runtime_path == "plugin_runtime"`.
- [x] service data endpoints use `PluginRuntime`.
- [x] provider endpoints use new plugin registry.
- [x] auth status works and leaks no secrets.
- [x] forbidden endpoint groups stay unavailable.
- [x] old REST login roadmap target is removed.
- [x] Phase 3.5 and Phase 4 can be marked closed.
