# Change Proposal: Phase 5 Alpha Discovery TUI MVP

## Change ID

`phase-5-alpha-discovery-tui-mvp`

## Summary

Implement the first end-to-end `openstock` research workflow:

```text
vnstock-service
→ vnalpha data sync
→ DuckDB research warehouse
→ feature store v1
→ alpha scoring v1
→ daily watchlist
→ TUI workspace
```

This phase starts `vnalpha` implementation with a TUI-first workflow. It intentionally avoids Streamlit, web dashboard work, AI-generated signals, broker integration, portfolio execution, and real-time trading.

## Background

`vnstock` Phase 1-4 creates the market data foundation: plugin runtime, provider registry, health/auth-aware routing, DataResult envelope, and local read-only service endpoints.

`vnalpha` should now become the research layer that consumes `vnstock-service`, computes deterministic features, scores candidate setups, and presents a daily watchlist in a terminal UI.

## Problem

The system currently has a strong data-platform foundation but not yet a usable research output.

The first useful system-level output should answer:

```text
Which Vietnamese equities should be monitored today, why, and what are the risks?
```

## Goals

### G1. openstock orchestration

Create a unified local workflow to run `vnstock-service`, execute `vnalpha` jobs, and open the TUI.

### G2. vnstock operational contract

Harden and document the minimum `vnstock-service` endpoints required by `vnalpha`.

Required endpoints:

```text
GET /v1/reference/symbols
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/providers/health
GET /v1/providers/capabilities
```

### G3. vnalpha core skeleton

Create the minimal executable `vnalpha` package with config, logging, CLI, and test structure.

### G4. vnstock client

Implement a typed client for `vnalpha` to consume `vnstock-service` without direct provider-specific logic.

### G5. Local research warehouse

Use DuckDB and Parquet-friendly schemas for local research storage.

### G6. Feature store v1

Compute deterministic features from canonical OHLCV.

### G7. Alpha scoring v1

Generate explainable candidate scores and risk flags.

### G8. Daily watchlist

Persist and expose a daily candidate watchlist.

### G9. TUI workspace

Implement a TUI for daily research workflow.

## Non-goals

This phase does not implement:

- Streamlit;
- web frontend;
- broker login in `vnalpha`;
- account APIs;
- order placement;
- portfolio execution;
- auto-trading;
- AI-only prediction;
- advanced pattern engine;
- full backtest lab;
- ML ranking;
- production scheduler;
- full historical warehouse optimization.

## MVP universe

Start with:

```text
VN30
```

Then expand to:

```text
HOSE liquid universe
all listed symbols
```

## Success criteria

Phase 5 is complete when:

1. `openstock` starts `vnstock-service` locally.
2. `vnalpha` CLI runs.
3. `vnalpha` can call `vnstock-service`.
4. VN30 symbols and OHLCV can be synced.
5. DuckDB warehouse is created.
6. `canonical_ohlcv` is built.
7. `feature_snapshot` is built.
8. `candidate_score` is generated.
9. `daily_watchlist` is generated.
10. TUI opens and displays daily watchlist.
11. TUI can drill into symbol detail.
12. Candidate records include score breakdown, evidence, risk flags, and lineage.
13. No buy/sell/order/portfolio language appears in API, CLI, or TUI.

## Validation commands

From `openstock`:

```bash
make up-vnstock
make sync
make features
make score
make tui
```

Inside `vnalpha`:

```bash
ruff check .
ruff format --check .
pytest -q
vnalpha --help
vnalpha tui --help
```
