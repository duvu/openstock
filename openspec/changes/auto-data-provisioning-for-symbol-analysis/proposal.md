# Proposal: Auto data provisioning for symbol analysis

## Summary

Add an implementation-focused OpenSpec change for automatic data provisioning before symbol analysis.

Target user experience:

```text
User asks: /explain FPT
or:       đánh giá FPT hôm nay

System:
1. checks whether FPT can be analysed for the target date
2. if needed, fetches missing OHLCV data from vnstock-service
3. if needed, fetches benchmark data such as VNINDEX
4. builds canonical OHLCV
5. builds feature snapshots
6. generates candidate score for the requested symbol
7. returns the analysis with freshness, lineage, and warnings
```

The user should not have to manually run:

```text
vnalpha sync ohlcv
vnalpha sync index
vnalpha build canonical
vnalpha build features
vnalpha score
```

before analysing one stock symbol.

This change is OpenSpec-only. Runtime implementation will be done in a later PR.

## Current state

The codebase already has the manual primitives:

```text
vnalpha sync symbols
vnalpha sync ohlcv
vnalpha sync index
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
/explain SYMBOL
/scan
```

But the current analysis path is artifact-first:

```text
/explain SYMBOL -> read candidate_score -> if missing, tell user to run score manually
/scan          -> read daily_watchlist -> if empty, tell user to run score manually
assistant      -> calls read tools only; it does not create missing data artifacts
```

## Problem statement

OpenStock can fetch and build data, but the user-facing analysis flow does not automatically ensure data readiness.

When a user asks to evaluate a symbol, the system should perform deterministic precondition work before explanation:

```text
candidate_score missing?
feature_snapshot missing?
canonical_ohlcv missing or stale?
benchmark missing or stale?
```

If artifacts are missing, the system should provision only the required data for the requested symbol and date, not require a manual full-universe pipeline.

## Goals

- Add a deterministic data readiness layer.
- Add `ensure_symbol_analysis_ready()` for one-symbol analysis.
- Check candidate score, feature snapshot, canonical OHLCV, benchmark OHLCV, and symbol master status.
- Auto-fetch missing OHLCV for the requested symbol.
- Auto-fetch missing benchmark OHLCV where needed.
- Build canonical OHLCV for the requested symbol and benchmark.
- Build feature snapshot for the requested symbol.
- Generate candidate score for the requested symbol.
- Integrate with `/explain SYMBOL`.
- Integrate with `/compare SYMBOL1 SYMBOL2 ...` by ensuring each symbol.
- Integrate with natural-language assistant paths before `candidate.explain` and `candidate.compare` tool execution.
- Emit structured observability events for every ensure-data decision and action.
- Return data freshness, lineage, actions taken, warnings, and errors in analysis results.
- Avoid auto-refreshing the entire universe for one-symbol analysis.

## Non-goals

- No full-universe auto-sync by default for `/explain SYMBOL`.
- No background scheduler in this change.
- No live streaming quote engine.
- No portfolio/account functionality.
- No external workflow orchestrator requirement.
- No dependency on cloud services beyond the configured local vnstock-service endpoint.
- No change to the read-only research boundary.

## Proposed change

Add a new service layer:

```text
vnalpha/src/vnalpha/data_availability/
├── __init__.py
├── models.py
├── checks.py
├── ensure.py
└── policy.py
```

Main API:

```python
def ensure_symbol_analysis_ready(
    conn,
    symbol: str,
    target_date: str,
    *,
    benchmark_symbol: str = "VNINDEX",
    lookback_days: int = 420,
    auto_sync: bool = True,
    source: str | None = None,
) -> EnsureDataResult:
    ...
```

Expected result object:

```text
EnsureDataResult
- symbol
- target_date
- status: READY | PARTIAL | FAILED
- actions_taken
- data_status
- warnings
- errors
- lineage
- freshness
```

## Desired flow for `/explain SYMBOL`

```text
handle_explain
  -> normalize symbol/date
  -> ensure_symbol_analysis_ready(symbol, date)
  -> if status FAILED: return clear CommandResult failure
  -> call candidate.explain
  -> include ensure result panel: actions taken, freshness, warnings, lineage
```

## Desired flow for assistant natural language

```text
User asks natural-language question about FPT
  -> intent classified as explain_symbol or compare_symbols
  -> plan built as today
  -> before candidate.explain/candidate.compare tool execution:
       ensure required data exists
  -> execute read tools
  -> synthesize answer with data freshness and lineage
```

This should be deterministic. The LLM should not decide whether data should be synced.

## Success criteria

This change is complete only when:

```text
- /explain FPT works even when candidate_score is initially absent, provided vnstock-service can supply data.
- /explain FPT does not re-sync if candidate_score and supporting data are already fresh enough.
- Missing canonical OHLCV triggers symbol OHLCV sync and canonical build.
- Missing benchmark OHLCV triggers benchmark sync and canonical build.
- Missing feature snapshot triggers feature build.
- Missing candidate_score triggers symbol scoring.
- /compare FPT MWG ensures both symbols before comparison.
- Natural-language analysis path triggers the same deterministic ensure-data logic.
- Every ensure-data action is logged through DATA_ENSURE_* events.
- Failure modes are clear and non-crashing.
- Tests cover cache-hit, missing-score, missing-features, missing-canonical, missing-benchmark, service-unavailable, empty-provider-data, compare, assistant path, and observability.
```

## Completion principle

Do not mark this change complete because manual sync/build/score commands exist. Completion requires user-facing analysis paths to provision the required data automatically when safe and necessary.
