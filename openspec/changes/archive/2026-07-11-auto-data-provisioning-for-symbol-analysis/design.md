# Design: Auto data provisioning for symbol analysis

## Design objective

When a user asks OpenStock to analyse a stock symbol, the system should automatically ensure the required local data artifacts exist before analysis.

The target is not a background batch pipeline. The target is a deterministic, minimal, one-symbol provisioning workflow.

## Core concept

Add a data readiness service:

```text
ensure_symbol_analysis_ready(symbol, target_date)
```

This service checks and creates the minimum required artifacts:

```text
symbol_master
raw OHLCV
canonical_ohlcv
benchmark canonical_ohlcv
feature_snapshot
candidate_score
```

It returns an explicit result object describing what happened.

## Proposed package

```text
vnalpha/src/vnalpha/data_availability/
├── __init__.py
├── models.py
├── policy.py
├── checks.py
├── ensure.py
└── observability.py
```

## Models

### EnsureDataStatus

```text
READY
PARTIAL
FAILED
```

### EnsureDataAction

```text
CHECK_SYMBOL_MASTER
CHECK_CANDIDATE_SCORE
CHECK_FEATURE_SNAPSHOT
CHECK_CANONICAL_OHLCV
CHECK_BENCHMARK_OHLCV
SYNC_SYMBOLS
SYNC_SYMBOL_OHLCV
SYNC_BENCHMARK_OHLCV
BUILD_CANONICAL_SYMBOL
BUILD_CANONICAL_BENCHMARK
BUILD_FEATURES_SYMBOL
SCORE_SYMBOL
```

### EnsureDataResult

Suggested fields:

```python
@dataclass
class EnsureDataResult:
    symbol: str
    target_date: str
    benchmark_symbol: str
    status: Literal["READY", "PARTIAL", "FAILED"]
    actions_taken: list[str]
    cache_hits: list[str]
    warnings: list[str]
    errors: list[str]
    freshness: dict[str, Any]
    lineage: dict[str, Any]
    score_available: bool
    feature_available: bool
    canonical_available: bool
    benchmark_available: bool
```

## Policy

Create `DataAvailabilityPolicy`:

```python
@dataclass
class DataAvailabilityPolicy:
    benchmark_symbol: str = "VNINDEX"
    lookback_days: int = 420
    min_required_bars: int = 120
    interval: str = "1D"
    auto_sync: bool = True
    refresh_stale: bool = True
    stale_after_calendar_days: int = 7
    source: str | None = None
```

Rationale:

- `ma100`, `return_60d`, `rs_60d`, and 52-week features need enough history.
- Use a calendar-day lookback wider than trading-day lookback.
- A stale data condition should be reported even if the system can still analyse using the latest available bar.

## Checks

Implement pure-ish checks in `checks.py`.

Suggested functions:

```python
get_symbol_master_status(conn, symbol) -> dict
get_candidate_score_status(conn, symbol, target_date) -> dict
get_feature_snapshot_status(conn, symbol, target_date) -> dict
get_canonical_ohlcv_status(conn, symbol, target_date, lookback_start, min_required_bars) -> dict
get_benchmark_status(conn, benchmark_symbol, target_date, lookback_start, min_required_bars) -> dict
```

Each check should return:

```text
exists
row_count
latest_bar_date
as_of_bar_date
is_stale
is_sufficient
lineage
warnings
```

## Ensure algorithm

Pseudo-code:

```python
def ensure_symbol_analysis_ready(conn, symbol, target_date, policy=None):
    normalize symbol/date
    compute lookback_start
    log DATA_ENSURE_STARTED

    if candidate_score exists and is fresh enough:
        log DATA_ENSURE_CACHE_HIT
        return READY

    check symbol master
    if missing and auto_sync:
        sync_symbols()

    check canonical data for symbol
    if missing/stale/insufficient and auto_sync:
        sync_ohlcv(universe=[symbol], start=lookback_start, end=target_date)
        build_canonical_ohlcv(symbol=symbol)

    check benchmark data
    if missing/stale/insufficient and auto_sync:
        sync_index_ohlcv(symbol=benchmark_symbol, start=lookback_start, end=target_date)
        build_canonical_ohlcv(symbol=benchmark_symbol)

    check feature snapshot
    if missing and canonical sufficient:
        build_features(universe=[symbol], target_date=target_date, benchmark_symbol=benchmark_symbol)

    check candidate score
    if missing and feature snapshot exists:
        generate_watchlist(universe=[symbol], date=target_date, top_n=1, min_score=0.0)

    final check candidate_score, feature, canonical, benchmark
    if candidate_score exists:
        log DATA_ENSURE_READY
        return READY
    if feature/canonical partially exist:
        log DATA_ENSURE_PARTIAL
        return PARTIAL
    log DATA_ENSURE_FAILED
    return FAILED
```

## Integration points

### `/explain SYMBOL`

Before calling `candidate.explain`, call ensure-data.

Result rendering should include an additional panel:

```text
Data Readiness
- status
- actions taken
- data freshness
- benchmark freshness
- warnings
- errors
```

If ensure-data returns FAILED, return a failed `CommandResult` with actionable errors.

### `/compare SYMBOL1 SYMBOL2 ...`

Ensure each symbol individually before calling `candidate.compare`.

If some symbols are ready and others fail, compare ready symbols and return warnings for failed symbols, or fail the command if zero symbols are ready.

### Assistant natural-language path

Do not ask the LLM to decide whether to sync data. Add deterministic pre-execution ensure-data logic before these tools:

```text
candidate.explain
candidate.compare
```

For `candidate.explain`, ensure one symbol.

For `candidate.compare`, ensure all symbols in the tool arguments.

The ensure-data result should be injected into tool output or assistant synthesis context so the answer can mention freshness and actions taken.

### `/scan`

Default `/scan` may continue to read the persisted watchlist.

Optional extension:

```text
/scan --auto-refresh
```

This should be separate because full-universe auto refresh can be slow.

## Observability

Add structured audit/domain events:

```text
DATA_ENSURE_STARTED
DATA_ENSURE_CACHE_HIT
DATA_ENSURE_SYMBOLS_SYNC_STARTED
DATA_ENSURE_SYMBOLS_SYNC_SUCCEEDED
DATA_ENSURE_SYMBOL_OHLCV_SYNC_STARTED
DATA_ENSURE_SYMBOL_OHLCV_SYNC_SUCCEEDED
DATA_ENSURE_SYMBOL_OHLCV_SYNC_FAILED
DATA_ENSURE_BENCHMARK_SYNC_STARTED
DATA_ENSURE_BENCHMARK_SYNC_SUCCEEDED
DATA_ENSURE_BENCHMARK_SYNC_FAILED
DATA_ENSURE_CANONICAL_BUILD_STARTED
DATA_ENSURE_CANONICAL_BUILD_SUCCEEDED
DATA_ENSURE_CANONICAL_BUILD_FAILED
DATA_ENSURE_FEATURE_BUILD_STARTED
DATA_ENSURE_FEATURE_BUILD_SUCCEEDED
DATA_ENSURE_FEATURE_BUILD_FAILED
DATA_ENSURE_SCORE_STARTED
DATA_ENSURE_SCORE_SUCCEEDED
DATA_ENSURE_SCORE_FAILED
DATA_ENSURE_READY
DATA_ENSURE_PARTIAL
DATA_ENSURE_FAILED
```

Each event should include:

```text
symbol
target_date
benchmark_symbol
lookback_start
action
status
row_count when relevant
latest_bar_date when relevant
error_type and error_message on failure
correlation_id
```

## Concurrency and idempotency

Implement a lightweight local lock:

```text
logs/locks/data-ensure-<symbol>-<date>.lock
```

or a warehouse-backed lock if available later.

Initial behavior:

```text
if lock exists and is fresh: wait briefly or return PARTIAL with retry message
if lock is stale: replace it and continue
always release lock in finally
```

All operations should be idempotent:

```text
sync inserts raw rows with INSERT OR IGNORE
canonical build upserts
feature build upserts
score upserts
```

## Failure handling

Failure modes should be explicit:

```text
vnstock-service unavailable
provider returned empty data
symbol not found
insufficient history after sync
benchmark unavailable
canonical build failed
feature build failed
score failed
```

The user-facing result should not crash. It should explain what failed and what manual command can be used for diagnosis.

## Testing strategy

Use dependency injection for sync/build/score functions where possible. Tests should not call real vnstock-service.

Required tests:

```text
cache hit: candidate_score exists -> no sync/build/score
missing score only -> score symbol
missing features -> build features then score
missing canonical -> sync OHLCV, build canonical, build features, score
missing benchmark -> sync index, build canonical benchmark, build features, score
provider empty data -> PARTIAL or FAILED with warning
service unavailable -> FAILED with clear error
/explain integrates ensure result panel
/compare ensures all symbols
assistant candidate.explain triggers ensure precondition
observability emits DATA_ENSURE_* events
lock prevents duplicate provisioning
```

## Documentation

Add docs:

```text
vnalpha/docs/auto-data-provisioning.md
```

Document:

```text
what auto-provisioning does
when it runs
how freshness is determined
how to disable auto-sync
how to diagnose failures
which manual commands correspond to automatic actions
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Add validation evidence for at least one mocked end-to-end `/explain FPT` flow where no candidate_score exists initially and the ensure-data service creates the missing artifacts.
