# Change Proposal: Phase 2 — Normalize Existing Providers as Internal Plugins

## Change ID

`phase-2-normalize-provider-plugins`

## Summary

Normalize existing provider implementations behind the Phase 1 internal plugin contracts.

This change specifies how current provider integrations should be organized as internal provider plugins before any external plugin package split.

Phase 2 focuses on:

- provider module normalization;
- provider capability declarations;
- dataset-to-method mapping;
- provider limitation metadata;
- normalizer boundaries;
- provider fixtures;
- provider contract tests;
- capability matrix generation;
- backward-compatible public API behavior.

## Code review context

A quick repository review before drafting this spec found:

- `README.md` positions the fork as a **data-only market data layer** and explicitly excludes broker execution, order placement, and trading execution.
- Current public usage is exposed through `Market`, `Reference`, `Fundamental`, and `Retail`.
- Current provider coverage includes KBS, VCI, DNSE, TCBS, FMarket, MSN, and FMP depending on dataset.
- Data quality validation exists for market datasets but remains opt-in.
- `pyproject.toml` still contains broad product wording around financial analysis/automation and includes a `vnstock-tcbs-login` script, so Phase 2 must keep provider normalization strictly data-only and defer auth/session redesign to later phases.
- Code search did not find Phase 1 symbols such as `ProviderPlugin`, `ProviderRegistry`, `ProviderRouter`, or `DataResult`; therefore Phase 2 depends on Phase 1 being completed first.

## Prerequisites

Phase 2 requires Phase 1 to be complete:

- dataset contracts exist;
- `ProviderPlugin` interface exists;
- `ProviderRegistry` exists;
- `ProviderRouter` skeleton exists;
- `DataResult` exists;
- at least one provider path has been adapted through the new internal flow.

## Motivation

The repository already supports multiple providers, but provider implementations need a consistent internal structure so that later phases can add:

- health-aware routing;
- auth-aware routing;
- provider-scoped rate limits;
- batch result envelopes;
- storage sinks;
- REST API;
- MCP data tools;
- external provider packages.

Without normalizing providers first, later platform services will either duplicate provider-specific logic or bypass the core governance layer.

## Goals

### G1. Normalize provider module layout

Target internal layout:

```text
vnstock/providers/
├── kbs/
│   ├── plugin.py
│   ├── client.py
│   ├── normalize.py
│   ├── capabilities.py
│   └── fixtures/
├── vci/
├── dnse/
├── tcbs/
├── fmarket/
├── msn/
└── fmp/
```

### G2. Add provider capability declarations

Each provider must declare supported datasets and limitations using the Phase 1 capability contract.

### G3. Add dataset-to-method mapping

Each provider plugin should expose a clear mapping from canonical dataset names to internal fetch methods.

Example:

```text
equity.ohlcv → fetch_equity_ohlcv()
equity.quote → fetch_equity_quote()
fundamental.balance_sheet → fetch_balance_sheet()
```

### G4. Add normalizer boundaries

Provider clients may return provider-native payloads, but provider plugins must return normalized `pandas.DataFrame` objects matching dataset contracts.

### G5. Add provider fixtures and contract tests

Each provider should have offline fixtures and tests for supported core datasets.

### G6. Generate provider capability matrix

The registry should produce a provider matrix from plugin capability declarations.

### G7. Preserve public API compatibility

Existing public calls must continue working through `Market`, `Reference`, `Fundamental`, and `Retail`.

## Non-goals

This phase does not implement:

- external provider package split;
- Python entry point discovery;
- credential/auth redesign;
- health-aware provider ranking;
- rate limiting;
- batch ingestion runtime;
- storage sinks;
- REST API;
- MCP server;
- TUI;
- trading signals;
- stock recommendations;
- broker/account/order APIs.

## Scope

### In scope

```text
vnstock/providers/*/plugin.py
vnstock/providers/*/capabilities.py
vnstock/providers/*/normalize.py
vnstock/providers/*/fixtures/
tests/contracts/providers/
tests/unit/core/provider/
docs/PROVIDER_PLUGIN_NORMALIZATION.md
```

### Out of scope

```text
vnstock-provider-* external packages
vnstock-api
vnstock-mcp
vnstock-tui
vnalpha research logic
credential/session management redesign
```

## Success criteria

Phase 2 is complete when:

- existing core providers are represented by internal `ProviderPlugin` implementations;
- each provider declares capabilities;
- each provider declares limitations;
- each provider maps canonical datasets to internal methods;
- provider outputs are normalized to dataset contracts;
- provider fixtures exist for core datasets;
- provider contract tests pass;
- capability matrix generation works;
- public API remains backward-compatible;
- data-only boundary remains enforced.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
