# Tasks: Phase 2 — Normalize Existing Providers as Internal Plugins

## 0. Prerequisite check

- [x] Confirm Phase 1 `DatasetContract` exists.
- [x] Confirm Phase 1 `ProviderPlugin` exists.
- [x] Confirm Phase 1 `ProviderRegistry` exists.
- [x] Confirm Phase 1 `ProviderRouter` exists.
- [x] Confirm Phase 1 `DataResult` exists.
- [x] Confirm at least one provider path is already routed through the internal platform boundary.

## 1. Provider module layout

- [x] Create or normalize `vnstock/providers/kbs/`.
- [x] Create or normalize `vnstock/providers/vci/`.
- [x] Create or normalize `vnstock/providers/dnse/`.
- [x] Create or normalize `vnstock/providers/tcbs/`.
- [x] Create or normalize `vnstock/providers/fmarket/`.
- [x] Create or normalize `vnstock/providers/msn/`.
- [x] Create or normalize `vnstock/providers/fmp/`.
- [x] Add `plugin.py` for each provider.
- [x] Add `capabilities.py` for each provider.
- [x] Add `normalize.py` for each provider where needed.
- [x] Preserve existing provider client code where possible.

## 2. Provider capability declarations

- [x] Define capability shape used by all providers.
- [x] Add KBS capability declaration.
- [x] Add VCI capability declaration.
- [x] Add DNSE capability declaration.
- [x] Add TCBS capability declaration.
- [x] Add FMarket capability declaration.
- [x] Add MSN capability declaration.
- [x] Add FMP capability declaration.
- [x] Include `supported` flag per dataset.
- [x] Include `status` per dataset.
- [x] Include `auth_required` per dataset.
- [x] Include supported intervals where applicable.
- [x] Include provider notes where applicable.

## 3. Provider limitations metadata

- [x] Add limitations metadata model or convention.
- [x] Add KBS limitations metadata.
- [x] Add VCI limitations metadata.
- [x] Add DNSE limitations metadata.
- [x] Add TCBS limitations metadata.
- [x] Add FMarket limitations metadata.
- [x] Add MSN limitations metadata.
- [x] Add FMP limitations metadata.
- [x] Explicitly mark broker/account/order capabilities as out of scope.

## 4. Dataset handler mapping

- [x] Add dataset-to-method mapping in each provider plugin.
- [x] Map `equity.ohlcv` where supported.
- [x] Map `equity.quote` where supported.
- [x] Map `equity.intraday_trades` where supported.
- [x] Map `index.ohlcv` where supported.
- [x] Map `reference.company_info` where supported.
- [x] Map `fundamental.balance_sheet` where supported.
- [x] Map `fund.nav` where supported.
- [x] Ensure unsupported datasets raise `UnsupportedDatasetForProviderError`.

## 5. Normalizers

- [x] Add or normalize `normalize_equity_ohlcv()` per provider where needed.
- [x] Add or normalize `normalize_equity_quote()` per provider where needed.
- [x] Add or normalize `normalize_intraday_trades()` per provider where needed.
- [x] Add or normalize `normalize_company_info()` per provider where needed.
- [x] Add or normalize `normalize_balance_sheet()` per provider where needed.
- [x] Ensure normalizers output required dataset contract columns.
- [x] Ensure normalizers fail clearly on missing required columns.
- [x] Ensure normalizers preserve useful provider metadata safely.

## 6. Provider registry integration

- [x] Register KBS provider plugin.
- [x] Register VCI provider plugin.
- [x] Register DNSE provider plugin.
- [x] Register TCBS provider plugin.
- [x] Register FMarket provider plugin.
- [x] Register MSN provider plugin.
- [x] Register FMP provider plugin.
- [x] Ensure provider names are case-insensitive.
- [x] Ensure duplicate registration fails.
- [x] Ensure `providers_for(dataset)` returns correct candidates.

## 7. First adapted dataset path

- [x] Adapt `equity.ohlcv` across core Vietnamese equity providers.
- [x] Confirm public `Market().equity.ohlcv(...)` remains compatible.
- [x] Confirm `source="KBS"` works where supported.
- [x] Confirm `source="VCI"` works where supported.
- [x] Confirm `source="DNSE"` works where supported.
- [x] Confirm `source="TCBS"` works where supported.
- [x] Confirm `source="auto"` uses Phase 1 router behavior.
- [x] Confirm `validate=True` still attaches quality metadata.

## 8. Fixtures

- [x] Add KBS fixtures for `equity.ohlcv`.
- [x] Add VCI fixtures for `equity.ohlcv`.
- [x] Add DNSE fixtures for `equity.ohlcv`.
- [x] Add TCBS fixtures for `equity.ohlcv`.
- [x] Add quote fixtures where supported.
- [x] Add intraday fixtures where supported.
- [x] Add valid response fixture.
- [x] Add empty but valid response fixture.
- [x] Add invalid symbol fixture.
- [x] Add missing optional fields fixture.
- [x] Add unexpected extra fields fixture.
- [x] Add schema drift sample fixture.

## 9. Contract tests

- [x] Add provider contract test helper.
- [x] Add KBS provider contract tests.
- [x] Add VCI provider contract tests.
- [x] Add DNSE provider contract tests.
- [x] Add TCBS provider contract tests.
- [x] Add FMarket provider contract tests where supported.
- [x] Add MSN/FMP provider contract tests where supported.
- [x] Test capability declarations.
- [x] Test unsupported dataset behavior.
- [x] Test fixture normalization.
- [x] Test required columns after normalization.
- [x] Test limitations metadata.
- [x] Test data-only capability boundary.

## 10. Capability matrix

- [x] Implement provider capability matrix output from registry.
- [x] Include provider name.
- [x] Include dataset name.
- [x] Include supported status.
- [x] Include capability status.
- [x] Include auth requirement.
- [x] Include intervals where applicable.
- [x] Add deterministic tests for matrix output.

## 11. Documentation

- [x] Add `docs/PROVIDER_PLUGIN_NORMALIZATION.md`.
- [x] Document provider module layout.
- [x] Document capability declaration format.
- [x] Document limitations metadata format.
- [x] Document fixture expectations.
- [x] Document contract test expectations.
- [x] Document migration strategy for current providers.
- [x] Document that external provider packages are deferred.

## 12. Validation

Run:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

Phase 2 is complete when:

- [x] existing core providers have internal plugin wrappers;
- [x] capabilities are declared for each provider;
- [x] limitations are declared for each provider;
- [x] dataset-to-method mapping exists;
- [x] provider outputs normalize to dataset contracts;
- [x] fixtures exist for core provider datasets;
- [x] provider contract tests pass;
- [x] capability matrix is generated from registry;
- [x] public API remains backward-compatible;
- [x] data-only boundary remains enforced;
- [x] docs are updated.
