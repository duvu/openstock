# Design: Complete Phase 5 Alpha Discovery MVP

## Current Implementation Snapshot

The current `vnalpha` implementation contains working parts of the Phase 5 stack:

```text
CLI
├── init
├── sync symbols
├── sync ohlcv
├── build canonical
├── build features
├── score
├── watchlist
└── tui

Warehouse
├── ingestion_run
├── symbol_master
├── market_ohlcv_raw
├── canonical_ohlcv
├── feature_snapshot
├── candidate_score
├── daily_watchlist
└── rejected_symbol

Pipeline
├── sync_symbols
├── sync_ohlcv
├── build_canonical_ohlcv
├── build_features
├── score_universe
├── save_watchlist
└── generate_watchlist

TUI
├── HomeScreen
├── WatchlistScreen
├── DetailScreen
├── RejectedScreen
└── QualityScreen
```

Phase 5 completion should build on this implementation, not replace it.

## Target Phase 5 Flow

```text
make up-vnstock
make sync
make features
make score
make tui
```

Equivalent direct commands:

```bash
vnalpha init
vnalpha sync symbols --universe VN30
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha sync index --symbol VNINDEX --start 2024-01-01
vnalpha build canonical --interval 1D
vnalpha build features --date <date> --benchmark VNINDEX
vnalpha score --date <date>
vnalpha watchlist --date <date>
vnalpha tui --date <date>
```

The exact command names may differ, but the user-facing contract must be consistent between CLI, Makefile, roadmap, and runbook.

## Design Area 1: CLI Contract Hardening

### Problem

`Makefile` expects a `--universe` option for `vnalpha sync ohlcv`, but the current CLI exposes `--symbols`.

### Design

Support both concepts explicitly:

```text
--universe VN30        named universe resolution
--symbols FPT,CMG,CTR explicit symbol list
```

Resolution order:

```text
1. if --symbols is supplied, use explicit symbols.
2. else if --universe is supplied, resolve named universe.
3. else use active symbols from symbol_master.
```

Minimum named universe support for Phase 5:

```text
VN30
```

If a named universe cannot be resolved, the command must fail clearly.

## Design Area 2: Benchmark Data Handling

### Problem

`build_features()` uses `VNINDEX` as the default benchmark, but normal equity sync may not load index OHLCV.

### Design

Add one of these supported flows:

### Option A: Add explicit index sync command

```bash
vnalpha sync index --symbol VNINDEX --start 2024-01-01
```

The command calls `VnstockClient.get_index_ohlcv()` and writes into `market_ohlcv_raw` using the same schema, then canonicalization promotes it into `canonical_ohlcv`.

### Option B: Extend `sync ohlcv` with benchmark option

```bash
vnalpha sync ohlcv --universe VN30 --benchmark VNINDEX --start 2024-01-01
```

This syncs equities and the benchmark in one run.

### Recommendation

Use Option A first because it keeps equity and index data semantics explicit.

## Design Area 3: Watchlist Artifact Completion

### Problem

`candidate_score` stores evidence and lineage, but `daily_watchlist` stores a thinner subset. Phase 5 output requires evidence and data-quality status at the review surface.

### Design

Use one of two patterns:

### Option A: Extend `daily_watchlist`

Add columns:

```text
evidence_json
data_quality_status
quality_flags_json
```

When `save_watchlist()` writes rows, copy evidence/risk/lineage/quality from `candidate_score` and supporting feature/canonical data.

### Option B: Keep `daily_watchlist` thin but expose a query view

Create a repository query that joins:

```text
daily_watchlist
JOIN candidate_score USING (symbol, date)
LEFT JOIN feature_snapshot USING (symbol, date)
LEFT JOIN latest canonical quality metadata
```

Return a rich watchlist view object containing:

```text
symbol
rank
score
candidate_class
setup_type
evidence_json
risk_flags_json
lineage_json
data_quality_status
```

### Recommendation

Use Option B for Phase 5 because it avoids unnecessary data duplication while satisfying CLI/TUI review requirements.

## Design Area 4: Data Quality Contract

### Problem

`market_ohlcv_raw` and `canonical_ohlcv` have `quality_status`, but `feature_snapshot` and watchlist views do not surface a clear data-quality result.

### Design

Define `data_quality_status` for Phase 5 watchlist review:

```text
PASS
WARN
FAIL
UNKNOWN
```

Derive it from:

```text
canonical_ohlcv.quality_status
minimum history length
missing OHLCV values
missing benchmark data
stale latest bar
feature NaN rate
```

Symbols with severe quality issues should either:

```text
- receive risk flag POOR_DATA_QUALITY, or
- be inserted into rejected_symbol with reason.
```

## Design Area 5: TUI Navigation

### Problem

Screen classes exist, but `VnAlphaApp` must register or instantiate all bound screens correctly.

### Design

Update `VnAlphaApp` to import all screen classes:

```python
from vnalpha.tui.screens.home import HomeScreen
from vnalpha.tui.screens.rejected import RejectedScreen
from vnalpha.tui.screens.quality import QualityScreen
```

Then either register named screens:

```python
self.install_screen(HomeScreen(), name="home")
self.install_screen(RejectedScreen(target_date=self.target_date), name="rejected")
self.install_screen(QualityScreen(), name="quality")
```

Or push instances directly:

```python
self.push_screen(HomeScreen())
self.push_screen(RejectedScreen(target_date=self.target_date))
self.push_screen(QualityScreen())
```

The TUI must support:

```text
Home
Watchlist
Symbol Detail
Rejected Symbols
Provider / Data Quality
```

## Design Area 6: Canonical Ontology Enforcement

### Problem

Legacy enum aliases exist in shared types. They are useful for backward compatibility but should not be accepted as new persisted Phase 5 values.

### Design

Define explicit canonical sets:

```python
CANONICAL_CANDIDATE_CLASSES = {
    "STRONG_CANDIDATE",
    "WATCH_CANDIDATE",
    "WEAK_CANDIDATE",
    "IGNORE",
}

CANONICAL_SETUP_TYPES = {
    "ACCUMULATION_BASE",
    "BREAKOUT_ATTEMPT",
    "MOMENTUM_CONTINUATION",
    "PULLBACK_TO_TREND",
    "MEAN_REVERSION",
    "UNCLASSIFIED",
}
```

Add persistence guards before writing `candidate_score` and `daily_watchlist`.

Add tests that assert persisted rows never use legacy aliases.

## Design Area 7: E2E Fixture Test

### Test Fixture

Create deterministic OHLCV fixtures:

```text
VNINDEX benchmark
FPT strong candidate
VNM weak/ignored candidate
BAD missing/poor-quality candidate
```

Minimum history:

```text
120 daily bars
```

### E2E Test Flow

```text
1. create in-memory DuckDB
2. run migrations
3. insert fixture symbols
4. insert raw OHLCV for symbols and VNINDEX
5. build canonical OHLCV
6. build features for target date
7. score candidates
8. generate watchlist
9. assert persisted tables
10. assert watchlist rich view includes evidence, risk, lineage, quality
```

### CLI Contract Test

Use Typer CliRunner or subprocess-style test to assert:

```text
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
```

is accepted by the CLI.

### TUI Smoke Test

Construct the app and screens without requiring an interactive terminal:

```text
VnAlphaApp(date="2024-01-02")
WatchlistScreen(target_date="2024-01-02")
DetailScreen(symbol="FPT", target_date="2024-01-02")
RejectedScreen(target_date="2024-01-02")
QualityScreen()
```

## Design Area 8: Research-Only Safety Guard

Phase 5 must remain research-only.

Add a static test that scans CLI help text, TUI labels, docs, and relevant source strings for prohibited execution-oriented language.

Forbidden terms in user-facing command names or primary labels:

```text
buy
sell
order
execute trade
place order
portfolio execution
broker account
```

Contextual mentions inside safety documentation are allowed when explicitly framed as forbidden.

## Implementation Order

1. Fix CLI/Makefile mismatch.
2. Add benchmark sync path.
3. Add watchlist rich view query.
4. Add data-quality derivation.
5. Fix TUI navigation.
6. Add ontology persistence guards.
7. Add E2E, CLI contract, and TUI smoke tests.
8. Update runbook and roadmap references.
