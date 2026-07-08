# Review: Current gaps toward research intelligence

## Verdict

OpenStock has reached the foundation stage for a local research terminal, but it is not yet a full research intelligence system.

Current capability:

```text
- ingest market data
- build technical features
- score candidates
- generate daily watchlist
- explain persisted score record
- compare persisted scores
- auto-provision missing data for symbol analysis
```

Target capability:

```text
- deep symbol analysis
- market and sector context
- watchlist synthesis
- shortlist generation
- conditional research scenario planning
- historical evidence for setups
- grounded assistant workflows
```

## Current strengths

### 1. Data foundation

The system has local warehouse artifacts:

```text
market_ohlcv_raw
canonical_ohlcv
feature_snapshot
candidate_score
daily_watchlist
ingestion_run
```

This is sufficient for deterministic research workflows.

### 2. Feature foundation

Existing features cover the first layer of technical analysis:

```text
moving averages
MA slopes
volume ratio
ATR
returns
relative strength vs VNINDEX
distance to MA20
distance to 52-week high
base range
close strength
volatility
```

### 3. Scoring foundation

The current scoring model already separates:

```text
trend
relative strength
volume
base quality
breakout quality
risk quality
```

This is enough to start ranking candidates, but not enough for deep explanation or conditional scenario planning.

### 4. Assistant foundation

The assistant already has:

```text
intent classification
plan builder
local tool registry
executor
synthesizer
trace logging
```

This provides a good base for new research tools.

## Major gaps

### Gap 1: Deep symbol analysis is missing

Current `/explain` returns a score record and evidence. It does not produce a structured research view with trend, levels, setup quality, risk context, thesis, counter-thesis, and scenarios.

### Gap 2: Multi-timeframe analysis is shallow

Current features are mainly daily snapshot features. There is no dedicated weekly context, multi-window momentum, drawdown, days-in-base, or extendedness analysis.

### Gap 3: Support/resistance and key levels are missing

The system does not yet calculate key price zones, nearby resistance, nearby support, confirmation levels, or invalidation levels.

### Gap 4: Market regime is missing

The system has VNINDEX relative strength but not a broader market regime engine. It lacks trend regime, volatility regime, breadth, and risk-on/risk-off style context.

### Gap 5: Sector context is missing

The system does not yet have a sector/industry strength engine or sector rotation ranking.

### Gap 6: Watchlist synthesis is basic

Current watchlist generation is top-N from candidate scores. It does not summarise watchlist health, setup distribution, sector clusters, improving names, extended names, or next-session research focus.

### Gap 7: Shortlist generation is missing

There is no dedicated shortlist engine that ranks names by setup quality, proximity to trigger, risk/reward, sector alignment, and data quality.

### Gap 8: Conditional scenario planning is missing

The system does not yet produce scenario plans with confirmation, invalidation, risk/reward, checklist, caveats, and research-only wording.

### Gap 9: Historical evidence is missing

There is no setup outcome engine. The system cannot yet say how similar setups behaved historically, what the forward return distribution looked like, or how regime affected outcomes.

### Gap 10: Assistant intent/tool model is incomplete

Current intents do not cover deep analysis, shortlist, market regime, sector strength, scenario planning, or historical evidence.

### Gap 11: Evaluation is incomplete

There is no golden-set evaluation for research quality, factual grounding, scenario quality, safety language, or shortlist usefulness.

### Gap 12: Policy layer needs refinement

The assistant currently blocks execution-oriented requests. That must remain. But the system also needs a safe research-only language policy so conditional scenarios do not become execution instructions.

## Required gap matrix dimensions

The implementation gap map should score each capability across:

```text
Data availability
Feature coverage
Model/rule coverage
Command/API availability
Assistant support
TUI support
Observability
Tests/evaluation
Policy safety
```

## Recommended sequencing

```text
1. Deep symbol analysis engine
2. Market regime and sector context
3. Watchlist synthesis and shortlist
4. Research scenario plan engine
5. Historical evidence engine
6. Assistant research tools
7. TUI workflow polish
```

Deep analysis should come first because shortlist and scenario planning depend on it.

Market and sector context should come before shortlist because shortlist quality depends on context.

Historical evidence can follow the first planning engine, but final confidence scoring should depend on it.
