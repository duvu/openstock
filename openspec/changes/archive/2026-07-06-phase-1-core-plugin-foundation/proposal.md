# Change Proposal: Phase 1 — Core Contracts and Internal Plugin Foundation

## Change ID

`phase-1-core-plugin-foundation`

## Summary

Introduce the internal platform contracts required to evolve `vnstock` from a data SDK into a plugin-based financial data platform.

This phase does not split provider packages externally yet. It creates the internal architecture foundation:

- dataset contracts;
- provider plugin interface;
- provider registry;
- provider router skeleton;
- structured `DataResult`;
- metadata propagation;
- backward-compatible public API behavior.

## Motivation

`vnstock` already supports multiple market data providers and has data quality/provider hardening capabilities. However, provider integration is still too coupled to internal implementation details.

To support future platform capabilities such as:

- health-aware routing;
- credential-aware providers;
- batch ingestion;
- storage sinks;
- REST API;
- CLI/TUI;
- MCP data tools;
- integration with `vnalpha`;

the core data layer needs stable internal contracts.

The main architectural goal is:

```text
Public API remains stable.
Internal execution becomes plugin-based, contract-driven, and metadata-rich.
```

## Goals

### G1. Add dataset contracts

Define canonical dataset contracts for major data types:

- `equity.ohlcv`
- `equity.quote`
- `equity.intraday_trades`
- `index.ohlcv`
- `reference.symbols`
- `reference.company_info`
- `fundamental.balance_sheet`
- `fundamental.income_statement`
- `fundamental.cash_flow`
- `fundamental.financial_ratio`
- `fund.nav`
- `foreign_flow.daily`

Each dataset contract should define:

- dataset name;
- required columns;
- optional columns;
- dtype rules;
- time format;
- timezone policy;
- symbol policy;
- quality validator binding;
- provider capability declaration.

### G2. Add `ProviderPlugin` interface

Define a common internal interface for all provider adapters.

The interface should support:

- capability declaration;
- dataset fetch;
- parameter validation;
- diagnostics;
- provider metadata.

### G3. Add `ProviderRegistry`

Introduce a registry to manage available providers and select provider candidates by dataset.

### G4. Add `ProviderRouter` skeleton

Introduce a router abstraction that resolves:

```text
dataset + source + params → provider plugin
```

Phase 1 only needs the skeleton and compatibility behavior. Health-aware routing comes later.

### G5. Add `DataResult`

Introduce a structured internal result envelope.

The current public API may continue returning `pandas.DataFrame`, but internal flows should use `DataResult` or equivalent metadata attached to `DataFrame.attrs`.

### G6. Preserve backward compatibility

Existing public usage must continue working:

```python
from vnstock import Market

market = Market()

bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    validate=True,
)
```

## Non-goals

This phase does not implement:

- external provider packages;
- Python entry point discovery;
- health-aware routing;
- credential/login providers;
- API service;
- MCP server;
- CLI/TUI;
- storage sinks;
- batch ingestion;
- trading signals;
- recommendation engine;
- broker/account/order APIs.

## Scope

### In scope

```text
vnstock/core/contracts/
vnstock/core/provider/plugin.py
vnstock/core/provider/registry.py
vnstock/core/provider/router.py
vnstock/core/result.py
tests/unit/core/provider/
tests/contracts/
```

### Out of scope

```text
vnstock-api
vnstock-mcp
vnstock-tui
vnstock-storage-*
vnstock-provider-* external packages
vnalpha research logic
```

## Proposed architecture

```text
Market / Reference / Fundamental / Retail UI
        ↓
ProviderRouter
        ↓
ProviderRegistry
        ↓
ProviderPlugin
        ↓
DatasetContract
        ↓
QualityValidator
        ↓
DataResult
        ↓
DataFrame or structured response
```

## User-facing behavior

No breaking change is expected for existing users.

Existing calls should continue returning `DataFrame` unless a future explicit API requests `DataResult`.

Internal metadata should be attached via `df.attrs` where appropriate:

```python
df.attrs["dataset"] = "equity.ohlcv"
df.attrs["provider"] = "KBS"
df.attrs["quality_status"] = "PASS"
df.attrs["diagnostics"] = {...}
```

No secrets, tokens, cookies, or auth headers may be placed into `DataFrame.attrs`.

## Risks

### R1. Over-engineering

Adding contracts too broadly may slow implementation.

Mitigation:

- implement only core dataset contracts first;
- keep provider plugins internal;
- avoid external package split in Phase 1.

### R2. Backward compatibility break

Refactoring provider paths may break existing `Market`, `Reference`, `Fundamental`, or `Retail` calls.

Mitigation:

- add compatibility tests;
- keep existing public function signatures;
- route internal implementation gradually.

### R3. Weak dataset contracts

If contracts are too loose, plugin architecture will not provide real safety.

Mitigation:

- define required columns and dtypes;
- bind each dataset to a validator;
- add contract tests with fixtures.

## Success criteria

Phase 1 is complete when:

- dataset contracts exist for the initial dataset list;
- `ProviderPlugin` interface exists;
- `ProviderRegistry` exists;
- `ProviderRouter` skeleton exists;
- `DataResult` exists;
- at least one existing provider path is adapted through the new internal flow;
- public API remains backward-compatible;
- contract tests pass;
- package build passes.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
