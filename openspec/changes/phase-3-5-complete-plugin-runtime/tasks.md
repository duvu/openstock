# Tasks: Phase 3.5 — Complete Plugin Runtime and Retire Legacy Dispatch

## 0. Prerequisite check

- [x] Confirm Phase 1 `DatasetContract` exists.
- [x] Confirm Phase 1 `ProviderPlugin` exists.
- [x] Confirm Phase 1 `PluginRegistry` exists.
- [x] Confirm Phase 1 `PluginRouter` exists.
- [x] Confirm Phase 1 `DataResult` exists.
- [x] Confirm Phase 2 provider plugins exist.
- [x] Confirm Phase 3 health-aware routing exists.
- [x] Confirm current public API paths that still bypass plugin runtime.
- [x] List all public methods that need migration.

## 1. Runtime package

- [x] Create `vnstock/core/runtime/`.
- [x] Add `vnstock/core/runtime/__init__.py`.
- [x] Add `vnstock/core/runtime/plugin_runtime.py`.
- [x] Add `vnstock/core/runtime/bootstrap.py`.
- [x] Add `vnstock/core/runtime/request.py`.
- [x] Add unit tests for runtime initialization.

## 2. DatasetRequest

- [x] Add `DatasetRequest` dataclass.
- [x] Include dataset name.
- [x] Include params.
- [x] Include source.
- [x] Include validate flag.
- [x] Include return_result flag.
- [x] Add tests for request construction.
- [x] Add tests for invalid dataset request.

## 3. Provider bootstrap

- [x] Add `default_plugin_registry()`.
- [x] Register KBS plugin.
- [x] Register VCI plugin.
- [x] Register DNSE plugin.
- [x] Register TCBS plugin.
- [x] Register FMarket plugin.
- [x] Register MSN plugin.
- [x] Register FMP plugin.
- [x] Add tests for default registry provider names.
- [x] Add tests for default registry capability matrix.

## 4. PluginRuntime core

- [x] Implement `PluginRuntime`.
- [x] Accept DatasetContractRegistry.
- [x] Accept PluginRegistry.
- [x] Accept PluginRouter.
- [x] Accept provider health store.
- [x] Implement `fetch(dataset, params, source, validate, return_result)`.
- [x] Resolve dataset contract.
- [x] Resolve provider through PluginRouter.
- [x] Call provider parameter validation.
- [x] Call provider fetch.
- [x] Wrap output in DataResult.
- [x] Attach routing diagnostics.
- [x] Attach provider diagnostics.
- [x] Attach runtime path diagnostics.
- [x] Return DataFrame by default.
- [x] Return DataResult when requested.

## 5. Health update integration

- [x] Record success after successful provider fetch and validation.
- [x] Record failure after provider fetch error.
- [x] Record failure after contract validation error.
- [x] Preserve routing diagnostics after failure where practical.
- [x] Add tests for success recording.
- [x] Add tests for failure recording.
- [x] Add tests for cooldown effect through runtime.

## 6. Contract validation integration

- [x] Validate output against DatasetContract when `validate=True`.
- [x] Support lightweight contract validation even when quality validation is disabled.
- [x] Ensure missing required columns fail clearly.
- [x] Ensure required metadata is attached.
- [x] Add tests for valid output.
- [x] Add tests for missing required columns.
- [x] Add tests for optional columns.

## 7. Public API migration — Market

- [x] Identify current `Market` implementation path.
- [x] Map `Market().equity.ohlcv(...)` to `equity.ohlcv`.
- [x] Map quote/price board methods to `equity.quote`.
- [x] Map intraday methods to `equity.intraday_trades`.
- [x] Route migrated methods through PluginRuntime.
- [x] Preserve public method signatures.
- [x] Preserve public DataFrame return type.
- [x] Add compatibility tests.
- [x] Add tests that migrated methods do not use legacy dispatch.

## 8. Public API migration — Reference

- [x] Identify current `Reference` implementation path.
- [x] Map symbol list to `reference.symbols`.
- [x] Map company info to `reference.company_info`.
- [x] Route migrated methods through PluginRuntime.
- [x] Add compatibility tests.
- [x] Add tests that migrated methods do not use legacy dispatch.

## 9. Public API migration — Fundamental

- [x] Identify current `Fundamental` implementation path.
- [x] Map balance sheet to `fundamental.balance_sheet`.
- [x] Map income statement to `fundamental.income_statement`.
- [x] Map cash flow to `fundamental.cash_flow`.
- [x] Map financial ratio to `fundamental.financial_ratio`.
- [x] Route migrated methods through PluginRuntime.
- [x] Add compatibility tests.
- [x] Add tests that migrated methods do not use legacy dispatch.

## 10. Public API migration — Retail/Fund

- [x] Identify current `Retail` implementation path.
- [x] Map fund NAV to `fund.nav`.
- [x] Route migrated methods through PluginRuntime.
- [x] Add compatibility tests.
- [x] Add tests that migrated methods do not use legacy dispatch.

## 11. Legacy fallback control

- [x] Add `allow_legacy_fallback` setting.
- [x] Default fallback to disabled for migrated datasets.
- [x] Emit diagnostics when fallback is used.
- [x] Add tests for fallback disabled.
- [x] Add tests for fallback explicit opt-in.
- [x] Add tests that migrated datasets never silently fallback.

## 12. Remove or quarantine legacy dispatch

- [x] Identify legacy dispatch modules.
- [x] Remove direct public calls for migrated datasets.
- [x] Rename internal-only legacy helpers where needed.
- [x] Add deprecation notes for legacy imports.
- [x] Add tests that public APIs use PluginRuntime.
- [x] Keep low-level provider client code only behind provider plugins.

## 13. DataResult and diagnostics

- [x] Ensure every runtime fetch creates DataResult.
- [x] Attach `dataset`.
- [x] Attach `provider`.
- [x] Attach `quality_status`.
- [x] Attach `quality`.
- [x] Attach `diagnostics`.
- [x] Attach `fetched_at`.
- [x] Attach `runtime_path`.
- [x] Add tests for DataFrame attrs.
- [x] Add tests for diagnostics completeness.
- [x] Add tests that diagnostics contain no credential material.

## 14. Comparison tests

- [x] Add plugin-vs-legacy comparison tests for migrated datasets before removing fallback.
- [x] Define acceptable differences.
- [x] Document schema normalization differences.
- [x] Remove comparison dependency once legacy path is retired.

## 15. Documentation

- [x] Add `docs/PLUGIN_RUNTIME_MIGRATION.md`.
- [x] Document plugin runtime architecture.
- [x] Document public API migration.
- [x] Document fallback policy.
- [x] Document how provider plugins wrap old clients.
- [x] Document Phase 4 dependency on PluginRuntime.
- [x] Document data-only boundary.

## 16. Validation

Run:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/integration/plugin_runtime tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

Phase 3.5 is complete when:

- [x] PluginRuntime exists;
- [x] default provider registry bootstrap exists;
- [x] public supported datasets route through PluginRuntime;
- [x] migrated datasets do not silently use legacy dispatch;
- [x] legacy clients are only used behind provider plugins;
- [x] DataResult metadata is consistently attached;
- [x] routing diagnostics are visible in `DataFrame.attrs`;
- [x] health update works through runtime;
- [x] compatibility tests pass;
- [x] legacy fallback is disabled by default for migrated datasets;
- [x] Phase 4 can build service endpoints on PluginRuntime only.
