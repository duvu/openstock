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
market regime snapshot, if available
sector strength snapshot, if available
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
