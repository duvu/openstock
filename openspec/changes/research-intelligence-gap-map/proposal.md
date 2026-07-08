# Proposal: Research intelligence gap map

## Summary

Create a formal gap map for upgrading OpenStock from a score-based screener into a research decision-support system.

Target capabilities:

```text
1. Deep symbol analysis
2. Watchlist synthesis
3. Shortlist generation
4. Conditional research scenario planning
5. Historical evidence support
6. Market regime and sector context
7. Assistant intents/tools for the above
8. Policy guardrails to keep outputs research-only
```

This OpenSpec is a planning and gap-assessment change. It does not implement runtime analysis engines. It defines what gaps must be closed and how future implementation OpenSpecs should be split.

## Current product position

OpenStock currently has a useful foundation:

```text
- local OHLCV ingestion
- canonical OHLCV
- feature snapshots
- deterministic candidate scoring
- daily watchlist generation
- candidate explain and compare tools
- data provisioning before analysis
- assistant planner, executor, and synthesizer
- TUI workspace
- file-based observability
```

However, the current user-facing intelligence is still mostly:

```text
score-based screening
candidate class
setup type
risk flags
basic explain and compare
```

It is not yet a full research workflow that can deeply analyse a symbol, synthesise a watchlist, select a shortlist, and produce a conditional scenario plan for review.

## Problem statement

The system needs a structured gap assessment before adding more research features. Without a formal gap map, implementation may drift into isolated commands without a coherent workflow.

The desired end-to-end research workflow is:

```text
User asks for market or watchlist review
  -> system checks data freshness
  -> analyses market regime and sector strength
  -> summarises watchlist structure
  -> selects shortlist by setup quality, risk context, and data quality
  -> deep-analyses selected symbols
  -> generates conditional research scenarios
  -> grounds claims in historical evidence when available
  -> stays research-only and avoids execution-oriented instructions
```

## Goals

- Define a target capability model for research intelligence.
- Create a gap matrix comparing current implementation vs target state.
- Define minimum viable outputs for each capability.
- Define data/schema gaps.
- Define feature gaps.
- Define command/API gaps.
- Define assistant intent/tool gaps.
- Define TUI/UX gaps.
- Define observability/evaluation gaps.
- Define policy and language constraints for research-only scenario planning.
- Split the future work into implementation OpenSpecs.
- Produce a prioritised roadmap.

## Non-goals

- Do not implement deep analysis in this OpenSpec.
- Do not implement watchlist synthesis in this OpenSpec.
- Do not implement shortlist generation in this OpenSpec.
- Do not implement conditional scenario planning in this OpenSpec.
- Do not implement account, allocation, execution, or external platform integration.
- Do not generate personalised financial advice.
- Do not weaken safety or policy guardrails.
- Do not claim predictive certainty.

## Target capabilities

### Capability 1: Deep symbol analysis

The system should produce a structured analysis for one symbol:

```text
- data freshness and lineage
- trend context
- momentum and relative strength
- volume participation
- volatility and risk context
- setup quality
- support and resistance levels
- scenario analysis
- thesis and counter-thesis
- caveats and missing data
```

### Capability 2: Watchlist synthesis

The system should summarise a daily watchlist:

```text
- candidate distribution by class and setup
- strongest names
- improving names
- weak or extended names
- sector clustering
- market regime alignment
- watchlist health
- next-session research focus areas
```

### Capability 3: Shortlist generation

The system should reduce a watchlist to a smaller research shortlist:

```text
- top candidates by setup quality
- candidates near trigger conditions
- pullback candidates
- breakout candidates
- risk-adjusted ranking
- data-quality-aware ranking
- clear why-in and why-out explanation
```

### Capability 4: Conditional research scenario planning

The system should generate conditional research plans, not execution recommendations:

```text
- current setup state
- key levels
- confirmation conditions
- invalidation conditions
- risk/reward estimate
- scenario tree
- checklist
- caveats
- research-only language
```

### Capability 5: Historical evidence support

The system should ground setup claims in historical evidence where possible:

```text
- setup occurrence history
- forward return distribution
- favourable and adverse excursion statistics
- outcome rate
- regime-conditioned outcomes
- sample-size warning
```

### Capability 6: Market regime and sector context

The system should analyse context around a symbol or watchlist:

```text
- VNINDEX trend regime
- volatility regime
- breadth
- sector strength and rotation
- symbol vs sector vs index relative strength
```

## Future implementation OpenSpecs

Recommended split:

```text
1. deep-symbol-analysis-engine
2. market-regime-and-sector-context
3. watchlist-synthesis-and-shortlist
4. research-scenario-plan-engine
5. setup-historical-evidence-engine
6. assistant-research-intelligence-tools
7. tui-research-workflow-polish
```

## Success criteria for this gap-map OpenSpec

This change is complete when it adds:

```text
- a formal gap matrix
- target capability definitions
- required data/schema gap list
- command/API gap list
- assistant intent/tool gap list
- evaluation/test gap list
- policy guardrail gap list
- prioritised roadmap
- future OpenSpec split
```

## Completion principle

Do not mark the research intelligence program complete because candidate scoring exists. Completion requires dedicated engines for deep analysis, watchlist synthesis, shortlist generation, scenario planning, and historical evidence.
