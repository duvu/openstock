# Design: Deep Symbol Analysis Engine

## Architecture

```text
/analyze SYMBOL or assistant intent
  -> ensure_symbol_analysis_ready
  -> DeepAnalysisBuilder
  -> LevelExtractor
  -> SetupQualityEvaluator
  -> ContextAssembler
  -> SetupAnalysis repository
  -> command/TUI/assistant rendering
```

## Proposed modules

```text
vnalpha/research_intelligence/deep_analysis.py
vnalpha/research_intelligence/levels.py
vnalpha/research_intelligence/setup_quality.py
vnalpha/research_intelligence/confidence.py
vnalpha/commands/handlers/analyze.py
```

## Deterministic inputs

```text
canonical_ohlcv
feature_snapshot
candidate_score
daily_watchlist
quality status
lineage
market regime snapshot when requested or required
sector strength snapshot when requested or required
historical evidence snapshot, if available
```

## Output blocks

### Trend context

Describe multi-window trend structure from persisted data.

### Momentum context

Separate acceleration, persistence, and extendedness.

### Relative strength context

Compare symbol versus VNINDEX and sector when available.

### Volume context

Distinguish confirmation, dry-up, abnormal spikes, and weak participation.

### Volatility context

Frame stability, compression, and abnormal risk in research language.

### Support/resistance levels

Produce explicit derived levels with source/provenance.

### Setup quality

Provide decomposed quality dimensions:

```text
trend_alignment
base_quality
relative_strength_quality
volume_quality
level_quality
risk_penalty
```

### Confidence

Confidence must represent data completeness and evidence consistency, not certainty about future returns.

## Command contract

```text
/analyze SYMBOL [--date YYYY-MM-DD] [--with-sector] [--with-regime]
```

## Assistant integration

Add intent:

```text
deep_analyze_symbol
```

Add tool:

```text
analysis.deep_symbol
```

## Boundary

Scenario summaries must use conditional research language:

```text
confirmation condition
invalidation condition
monitoring checklist
missing evidence
```

They must not use execution language.

## Deep-analysis readiness orchestration

```text
/analyze SYMBOL or assistant intent
  -> DeepAnalysisReadinessService
  -> ensure_symbol_analysis_ready (symbol, benchmark, features, score)
  -> ensure market-regime snapshot when requested or required
  -> ensure sector-strength snapshot when requested or required
  -> typed readiness result and correlated audit events
  -> analysis.deep_symbol
  -> command/TUI/assistant rendering
```

`DeepAnalysisReadinessService` is deterministic application code. It owns the
provisioning decision and reuses the current one-symbol ensure service plus
the established regime/sector builders. The LLM planner only selects the
bounded read tool and never receives `data.fetch` capability.

The service returns one status per artifact: `READY`, `PROVISIONED`, `PARTIAL`,
`FAILED`, or `NOT_REQUESTED`, including requested and resolved as-of dates,
actions, freshness, lineage, warnings, errors, and correlation ID. The executor
must not log-and-continue after a failed required precondition. It can execute
only with an optional unavailable context explicitly represented in the result;
the rendered analysis must disclose it.

The default one-symbol path stays minimal and does not refresh the full
universe. A market or sector snapshot is built only when the command option or
deep contract requests it, and only through existing bounded builders.

## Explicit user data commands

One shared deterministic command service is exposed in both CLI and TUI:

```text
vnalpha data download symbols [--source PROVIDER]
vnalpha data download ohlcv SYMBOL [--start DATE] [--end DATE] [--source PROVIDER]
vnalpha data download index [SYMBOL] [--start DATE] [--end DATE] [--source PROVIDER]
vnalpha data build canonical SYMBOL
vnalpha data build features SYMBOL --date DATE
vnalpha data build score SYMBOL --date DATE
vnalpha data build market-regime --date DATE
vnalpha data build sector-strength --date DATE

/data download <symbols|ohlcv|index> ...
/data build <canonical|features|score|market-regime|sector-strength> ...
```

These are explicit user-initiated operational paths. They validate arguments,
reuse existing ingestion and builder services, render deterministic
actions/freshness/warnings, and emit correlated audit events. Existing `sync`
and `build` CLI commands remain supported; no provider-I/O implementation is
duplicated.
