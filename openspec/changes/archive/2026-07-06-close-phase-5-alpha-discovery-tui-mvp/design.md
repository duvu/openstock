# Design: Close Phase 5 Alpha Discovery TUI MVP

## Current State

Phase 5 has useful skeletons:

- `vnalpha` package structure.
- DuckDB warehouse schema.
- `vnstock` REST client.
- Price feature functions.
- Deterministic scoring functions.
- Textual TUI skeleton.
- Makefile targets for local operation.

The phase is not closable yet because the main workflow is not executable end-to-end. Several CLI commands still return placeholder behavior or are not connected to the implemented modules.

## Target State

Phase 5 should become a deterministic, local-first alpha discovery MVP:

```text
User
  ├── CLI
  │   ├── init
  │   ├── sync symbols
  │   ├── sync ohlcv
  │   ├── build canonical
  │   ├── build features
  │   ├── score
  │   ├── watchlist
  │   └── tui
  │
  └── TUI workspace
      ├── Daily Watchlist
      ├── Symbol Detail
      ├── Rejected Symbols
      └── Data Quality

vnalpha
  ├── vnstock REST client
  ├── ingestion pipeline
  ├── DuckDB warehouse
  ├── canonicalization pipeline
  ├── feature engine
  ├── scoring engine
  ├── watchlist generator
  └── Textual TUI

vnstock-service
  └── local read-only market data service
```

## Design Principles

1. Deterministic core first.
   - Features, scores, classes, evidence, and watchlist generation must be reproducible.

2. Local-first.
   - Default storage is local DuckDB.
   - Default data source is local `vnstock-service`.

3. Research-only.
   - Phase 5 is a research/watchlist product, not an execution product.

4. Data quality is first-class.
   - Every candidate should expose data quality and provider lineage.

5. CLI and TUI share backend services.
   - The TUI must not duplicate scoring logic.

6. Tests close the phase.
   - A task is done only when executable tests or validation commands verify it.

## CLI Design

`vnalpha/src/vnalpha/cli.py` should route commands to implementation modules.

### `vnalpha init`

- Create DuckDB database if missing.
- Apply schema DDL.
- Print warehouse path and schema status.

### `vnalpha sync symbols --universe VN30`

- Resolve configured universe.
- Call `VnstockClient.get_symbols()` or a local universe provider.
- Upsert rows into `symbol_master`.
- Record `ingestion_run`.

### `vnalpha sync ohlcv --universe VN30`

- Resolve symbols from `symbol_master` or configured universe.
- Call `VnstockClient.get_equity_ohlcv()`.
- Write raw provider data into `market_ohlcv_raw`.
- Record provider, endpoint, retrieval timestamp, and diagnostics.

### `vnalpha build canonical`

- Read `market_ohlcv_raw`.
- Normalize into `canonical_ohlcv`.
- Enforce one row per symbol/date.
- Write quality flags for missing, duplicate, stale, or invalid rows.

### `vnalpha build features`

- Read `canonical_ohlcv`.
- Compute Phase 5 price/volume features.
- Write one `feature_snapshot` row per symbol/as_of_date.

### `vnalpha score`

- Read latest `feature_snapshot` rows.
- Compute component scores and composite score.
- Map final score to `candidate_class`.
- Map observed pattern to `setup_type`.
- Write `candidate_score` and `daily_watchlist`.

### `vnalpha watchlist`

- Query latest or specified `daily_watchlist` rows.
- Render a Rich table.
- Include symbol, score, candidate class, setup type, risk flags, lineage, and data quality status.

### `vnalpha tui`

- Launch `VnAlphaApp().run()`.
- Display watchlist from DuckDB-backed query services.
- Provide symbol detail view.
- Show explicit empty states when no warehouse or no watchlist exists.

## Warehouse and Query Services

Use dedicated query/service functions instead of embedding SQL in TUI screens.

Suggested modules:

```text
vnalpha/warehouse/connection.py
vnalpha/warehouse/schema.py
vnalpha/warehouse/queries.py
vnalpha/pipeline/canonical.py
vnalpha/pipeline/features.py
vnalpha/pipeline/scoring.py
vnalpha/watchlist/generator.py
vnalpha/watchlist/queries.py
```

The exact names may differ, but responsibilities should remain separated.

## Feature Snapshot Design

Each feature snapshot should include:

- symbol
- as_of_date
- trend features
- relative strength features
- volume/liquidity features
- base/range features
- breakout/proximity features
- quality fields
- provider lineage

The implementation may store structured evidence as JSON/text if schema support already exists.

## Scoring Design

Scoring should be deterministic and transparent.

Required score components:

- trend score
- relative strength score
- volume score
- base score
- breakout score
- risk/quality score
- composite score

Canonical mapping:

```text
candidate_class:
  STRONG_CANDIDATE
  WATCH_CANDIDATE
  WEAK_CANDIDATE
  IGNORE

setup_type:
  ACCUMULATION_BASE
  BREAKOUT_ATTEMPT
  MOMENTUM_CONTINUATION
  PULLBACK_TO_TREND
  MEAN_REVERSION
  UNCLASSIFIED
```

`candidate_class` is final priority. `setup_type` is the observed setup. These must not be conflated.

## TUI Design

The TUI should expose these Phase 5 screens:

- Daily Watchlist
- Symbol Detail
- Rejected Symbols, or a clear placeholder
- Data Quality, or a clear placeholder

Watchlist detail should include:

- score breakdown
- evidence summary
- risk flags
- provider lineage
- data quality status

TUI screens should call shared query services, not reimplement scoring.

## Test Design

Add fixture-backed tests that do not require external providers.

Minimum fixture requirements:

- At least 3 symbols.
- Enough OHLCV history to compute Phase 5 features.
- At least one candidate that should become non-`IGNORE`.
- At least one data-quality issue to test flagging or rejection.

Minimum E2E assertions:

- schema initialized
- symbols loaded
- raw OHLCV loaded
- canonical OHLCV generated
- feature snapshots generated
- candidate scores generated
- daily watchlist generated
- at least one non-`IGNORE` candidate exists
- CLI commands are not stubs
- public surfaces stay research/watchlist oriented

## Repo Boundary Decision

Before closure, choose one:

### Option A: `vnalpha` is a separate implementation repo

This matches the original architecture:

```text
openstock = orchestration/source-of-truth roadmap/specs
vnstock   = data platform service
vnalpha   = research engine + TUI workspace
```

In this option, Phase 5 implementation should be committed to `duvu/vnalpha`, while `openstock` references it through orchestration, docs, or submodule configuration.

### Option B: `vnalpha` is vendored under `openstock`

If this is intentional, then `docs/ROADMAP.md`, Makefile paths, test commands, and runbook must state that `openstock/vnalpha` is the implementation location.

## Deferred Work

MCP and LLM Gateway work are not required to close Phase 5.

They should be captured in later changes:

- Phase 5.8: Natural Language Research Assistant Skeleton.
- Phase 5.9: MCP Client + `vnstock` MCP Adapter.

Phase 5 deterministic scoring must remain independent of LLM-generated signals.
