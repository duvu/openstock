# Tasks: Phase 1 — Core Contracts and Internal Plugin Foundation

## 1. Dataset contracts

- [x] Create `vnstock/core/contracts/`.
- [x] Add `DatasetContract` model.
- [x] Add `DatasetContractRegistry`.
- [x] Define `equity.ohlcv` contract.
- [x] Define `equity.quote` contract.
- [x] Define `equity.intraday_trades` contract.
- [x] Define `index.ohlcv` contract.
- [x] Define `reference.symbols` contract.
- [x] Define `reference.company_info` contract.
- [x] Define `fundamental.balance_sheet` contract.
- [x] Define `fundamental.income_statement` contract.
- [x] Define `fundamental.cash_flow` contract.
- [x] Define `fundamental.financial_ratio` contract.
- [x] Define `fund.nav` contract.
- [x] Define `foreign_flow.daily` contract.
- [x] Add tests for contract registration.
- [x] Add tests for duplicate dataset registration.
- [x] Add tests for unknown dataset lookup.

## 2. Provider plugin interface

- [x] Create `vnstock/core/provider/plugin.py`.
- [x] Define `ProviderPlugin` protocol/interface.
- [x] Define standard capability metadata shape.
- [x] Define allowed provider capability status values:
  - `stable`
  - `experimental`
  - `partial`
  - `deprecated`
  - `unsupported`
- [x] Add tests for provider capability shape.
- [x] Add a fake provider plugin for tests.

## 3. Provider registry

- [x] Create `vnstock/core/provider/registry.py`.
- [x] Implement `register(provider)`.
- [x] Implement `get(name)`.
- [x] Implement `providers_for(dataset)`.
- [x] Implement `names()`.
- [x] Implement `capability_matrix()`.
- [x] Ensure provider names are case-insensitive.
- [x] Add duplicate provider registration error.
- [x] Add tests for registry lookup.
- [x] Add tests for dataset candidate lookup.
- [x] Add tests for capability matrix output.

## 4. Provider router skeleton

- [x] Create `vnstock/core/provider/router.py`.
- [x] Implement `ProviderRouter`.
- [x] Implement explicit source resolution.
- [x] Implement `source=None` and `source="auto"` behavior.
- [x] Add default provider priority config hook.
- [x] Add routing diagnostics object.
- [x] Add error for unknown provider.
- [x] Add error for provider that does not support requested dataset.
- [x] Add tests for explicit source routing.
- [x] Add tests for auto source routing.
- [x] Add tests for unsupported dataset routing.
- [x] Add tests for routing diagnostics.

## 5. DataResult

- [x] Create `vnstock/core/result.py`.
- [x] Add `DataResult` dataclass.
- [x] Add `to_dataframe()` method.
- [x] Ensure metadata is attached to `DataFrame.attrs`.
- [x] Ensure no auth secrets are added to metadata.
- [x] Add tests for metadata propagation.
- [x] Add tests for empty quality report.
- [x] Add tests for diagnostics propagation.

## 6. Error model

- [x] Add base platform exception.
- [x] Add `DatasetContractError`.
- [x] Add `ProviderNotFoundError`.
- [x] Add `UnsupportedDatasetError`.
- [x] Add `UnsupportedDatasetForProviderError`.
- [x] Add `ProviderFetchError`.
- [x] Add tests for expected errors.

## 7. Backward compatibility

- [x] Confirm current `Market` import remains unchanged.
- [x] Confirm `Market().equity.ohlcv(...)` remains unchanged.
- [x] Confirm `validate=True` behavior remains compatible.
- [x] Confirm `df.attrs["quality"]` remains compatible.
- [x] Add at least one compatibility test for existing OHLCV call path.
- [x] Add migration notes for internal maintainers.

## 8. First provider path adaptation

- [x] Select first provider path for internal plugin routing.
- [x] Recommended: `equity.ohlcv`.
- [x] Add internal provider wrapper for selected provider.
- [x] Route selected path through `ProviderRegistry`.
- [x] Route selected path through `ProviderRouter`.
- [x] Return current public `DataFrame`.
- [x] Preserve provider/quality metadata.
- [x] Add tests.

## 9. Documentation

- [x] Add `docs/PLUGIN_ARCHITECTURE.md`.
- [x] Add `docs/DATASET_CONTRACTS.md`.
- [x] Add `docs/PROVIDER_PLUGIN_INTERFACE.md`.
- [x] Add examples for provider capability declaration.
- [x] Add examples for `DataResult`.
- [x] Add note that external package split is not part of Phase 1.

## 10. Validation

Run:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

Phase 1 is complete when:

- [x] dataset contract registry exists;
- [x] provider plugin interface exists;
- [x] provider registry exists;
- [x] provider router skeleton exists;
- [x] `DataResult` exists;
- [x] at least one provider path is adapted internally;
- [x] public API remains backward-compatible;
- [x] unit tests pass;
- [x] contract tests pass;
- [x] build passes;
- [x] docs are updated.
