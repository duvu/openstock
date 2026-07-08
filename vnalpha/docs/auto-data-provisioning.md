# Auto Data Provisioning

Deterministic data provisioning that runs automatically before symbol analysis.

## What it does

When a user asks `/explain FPT` or the assistant executor calls `candidate.explain`,
vnalpha checks whether all required data is present and fills gaps before running the
analysis. The pipeline is silent on success and appends a **Data Readiness** panel to
the output when provisioning took any action.

## Trigger points

| Entry point | When it runs |
|---|---|
| `/explain SYMBOL` command | Before `candidate.explain` |
| `/compare SYMBOL1 SYMBOL2` command | Before `candidate.compare` (per symbol) |
| Assistant executor `candidate.explain` step | Pre-execution hook |
| Assistant executor `candidate.compare` step | Pre-execution hook |

## Data pipeline

```
candidate_score fresh?  → READY (cache hit, no sync)
         │ no
         ▼
symbol_master present?  → sync_symbols if auto_sync=True
         │
         ▼
canonical_ohlcv ≥ min_required_bars?  → sync_ohlcv + build_canonical if needed
         │
         ▼
benchmark canonical ≥ min_required_bars?  → sync_index + build_canonical if needed
         │
         ▼
feature_snapshot present?  → build_features if canonical sufficient
         │
         ▼
candidate_score present?  → score_universe if features exist
         │
         ▼
       READY / PARTIAL / FAILED
```

## Policy

```python
from vnalpha.data_availability.policy import DEFAULT_POLICY, DataAvailabilityPolicy

DEFAULT_POLICY = DataAvailabilityPolicy(
    benchmark="VNINDEX",
    lookback_days=420,        # ~420 calendar days back from target_date
    min_required_bars=120,    # minimum canonical bars needed for features
    auto_sync=True,           # whether to call sync/build functions
    stale_after_calendar_days=7,  # candidate_score freshness window
)
```

Override per call:

```python
from vnalpha.data_availability import ensure_symbol_analysis_ready
from vnalpha.data_availability.policy import DataAvailabilityPolicy

result = ensure_symbol_analysis_ready(
    conn, "FPT", "2025-06-30",
    policy=DataAvailabilityPolicy(auto_sync=False),
)
```

## Result object

```python
@dataclass
class EnsureDataResult:
    symbol: str
    target_date: str
    status: EnsureDataStatus          # READY | PARTIAL | FAILED
    actions_taken: list[EnsureDataAction]
    warnings: list[str]
    errors: list[str]
    canonical_bars: int
    feature_snapshot_exists: bool
    candidate_score_exists: bool

    def to_panel_dict(self) -> dict:  # suitable for ResultPanel
        ...
```

## Failure modes

All steps are best-effort. A failure in one step degrades status to `PARTIAL` or
`FAILED` but never raises to the caller. Common failure modes:

| Failure | Status | Warning message |
|---|---|---|
| vnstock-service unreachable | PARTIAL or FAILED | `OHLCV sync failed: ...` |
| Symbol not in symbol_master, auto_sync=False | FAILED | `Symbol 'X' not found in symbol_master` |
| Insufficient canonical bars after sync | PARTIAL | `Insufficient canonical bars: N < 120` |
| Feature build fails | PARTIAL | `Feature build failed: ...` |
| Scoring fails | PARTIAL | `Scoring failed: ...` |

## Testing

Use dependency injection to replace real sync/build calls in unit tests:

```python
def _noop_sync_ohlcv(conn, universe, start, end, **kwargs):
    return {"inserted": 0}

result = ensure_symbol_analysis_ready(
    conn, "FPT", "2025-06-30",
    policy=DataAvailabilityPolicy(auto_sync=True),
    _sync_ohlcv_fn=_noop_sync_ohlcv,
    ...
)
```

All injected functions receive the same signature as the real implementations. Inject
only the hooks you need; the rest default to the real functions.

## Observability

Each step emits structured log events via `vnalpha.data_availability.observability`:

```
DATA_ENSURE_STARTED
DATA_ENSURE_CACHE_HIT
DATA_ENSURE_SYMBOLS_SYNC_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_SYMBOL_OHLCV_SYNC_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_CANONICAL_BUILD_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_BENCHMARK_SYNC_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_FEATURE_BUILD_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_SCORE_STARTED / _SUCCEEDED / _FAILED
DATA_ENSURE_READY / _PARTIAL / _FAILED
```

Events are logged via `log_audit` (best-effort, never crash the caller).
