# Tasks: Close vnstock Phase 3.5 and Phase 4 Service Runtime

## 0. Baseline audit

- [ ] Confirm `PluginRuntime` exists and returns `DataResult` when `return_result=True`.
- [ ] Confirm `default_plugin_registry()` registers built-in provider plugins.
- [ ] Confirm current service data endpoint bypasses `PluginRuntime`.
- [ ] Confirm current provider endpoints use legacy registry or return incomplete data.
- [ ] Confirm auth status call sites are consistent with `AuthManager.auth_status_all()`.
- [ ] Confirm forbidden endpoint tests currently pass.

## 1. Add service dataset mapper

- [ ] Create `vnstock/service/dataset_mapper.py`.
- [ ] Map canonical HTTP paths to dataset names.
- [ ] Preserve `source`, `validate`, and `quality_mode` query params.
- [ ] Reject unknown datasets clearly.
- [ ] Add tests for known paths.
- [ ] Add tests for unknown paths.

## 2. Add runtime dependency helper

- [ ] Create `vnstock/service/runtime_dependency.py`.
- [ ] Initialize `default_plugin_registry()`.
- [ ] Initialize `PluginRuntime`.
- [ ] Support test injection of fake runtime.
- [ ] Avoid direct legacy `Vnstock` initialization in service data path.

## 3. Add DataResult serializer

- [ ] Create `vnstock/service/serializers.py`.
- [ ] Implement `serialize_data_result(result, request_context)`.
- [ ] Convert DataFrame to records.
- [ ] Include `meta.request_id`.
- [ ] Include `meta.dataset`.
- [ ] Include `meta.provider`.
- [ ] Include `meta.quality_status`.
- [ ] Include `meta.fetched_at`.
- [ ] Include `meta.source_requested`.
- [ ] Include `meta.runtime_path`.
- [ ] Include diagnostics where available.
- [ ] Redact sensitive diagnostics.
- [ ] Add tests for envelope shape.
- [ ] Add tests for redaction.

## 4. Rewrite service data handlers

- [ ] Replace legacy `_handle_data()` behavior with PluginRuntime path.
- [ ] Add canonical path dispatch for `/v1/equity/*`.
- [ ] Add canonical path dispatch for `/v1/index/*`.
- [ ] Add canonical path dispatch for `/v1/reference/*`.
- [ ] Add canonical path dispatch for `/v1/company/*`.
- [ ] Add canonical path dispatch for `/v1/fundamental/*`.
- [ ] Add canonical path dispatch for `/v1/fund/*`.
- [ ] Parse query params into runtime params.
- [ ] Call `PluginRuntime.fetch(dataset, params, source=..., validate=..., quality_mode=..., return_result=True)`.
- [ ] Serialize returned `DataResult`.
- [ ] Add test that a fake runtime is called by `/v1/equity/ohlcv`.
- [ ] Add test that legacy `Vnstock` is not called by data endpoints.

## 5. Fix provider endpoints

- [ ] Replace legacy provider registry usage in service endpoints.
- [ ] `/v1/providers` should return `default_plugin_registry().names()`.
- [ ] `/v1/providers/capabilities` should return `default_plugin_registry().capability_matrix()`.
- [ ] `/v1/providers/health` should return safe health store data.
- [ ] Add tests proving provider list includes core providers where available.

## 6. Fix auth status compatibility

- [ ] Update `AuthManager.auth_status_all()` to accept `providers: list[str] | None = None` or update all call sites to pass a provider list.
- [ ] Ensure CLI `vnstock-auth status` works.
- [ ] Ensure service `GET /v1/auth/status` works when auth manager is configured.
- [ ] Ensure auth status responses do not expose credential material.
- [ ] Add regression tests for service auth status with mocked sensitive fields.

## 7. Keep forbidden boundary closed

- [ ] Keep forbidden gate for auth-login/order/account/portfolio/transfer/margin/trading paths.
- [ ] Add REST login path coverage.
- [ ] Add trading/account/portfolio execution path coverage.

## 8. Error handling

- [ ] Map unsupported dataset to 404.
- [ ] Map no healthy provider to 503.
- [ ] Map provider fetch error to 502.
- [ ] Map dataset contract error to 422.
- [ ] Map bad params to 400.
- [ ] Ensure error response includes `error`, `message`, `dataset`, and `request_id` where available.
- [ ] Add tests for unsupported dataset and provider fetch error.

## 9. Roadmap/docs alignment

- [ ] Update `vnstock/roadmap.md` to remove REST login/logout endpoints from REST API target.
- [ ] Mark Phase 3.5 as closable only after service path uses PluginRuntime.
- [ ] Mark Phase 4 as local data service runtime, not public broker-login backend.
- [ ] Keep `vnstock/docs/DATA_SERVICE_DESIGN.md` aligned with implementation.

## 10. Validation

Run inside the `vnstock` submodule:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core/runtime tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

- [ ] `/v1/equity/ohlcv` returns `data`, `meta`, and `diagnostics`.
- [ ] `meta.dataset == "equity.ohlcv"`.
- [ ] `meta.runtime_path == "plugin_runtime"`.
- [ ] service data endpoints use `PluginRuntime`.
- [ ] provider endpoints use new plugin registry.
- [ ] auth status works and leaks no secrets.
- [ ] forbidden endpoint groups stay unavailable.
- [ ] old REST login roadmap target is removed.
- [ ] Phase 3.5 and Phase 4 can be marked closed.
