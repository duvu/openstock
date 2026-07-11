# Design: Research intelligence gap map

## Design objective

Create a planning artifact that tells implementation agents exactly what is missing before OpenStock can become a research decision-support system.

The output of this OpenSpec should be a structured gap map, not runtime code.

## Deliverables

Add a dedicated gap map document:

```text
vnalpha/docs/research-intelligence-gap-map.md
```

The document should contain:

```text
1. Current capability inventory
2. Target capability model
3. Gap matrix
4. Data/schema gaps
5. Feature engineering gaps
6. Command/API gaps
7. Assistant intent/tool gaps
8. TUI workflow gaps
9. Observability gaps
10. Evaluation/test gaps
11. Policy/safety gaps
12. Prioritised roadmap
13. Future OpenSpec split
```

## Target capability model

### A. Deep symbol analysis

Minimum output:

```text
symbol
as_of_date
data freshness
lineage
trend context
momentum context
relative strength context
volume context
volatility context
setup quality
support/resistance levels
scenario summary
risks/caveats
missing data
confidence
```

### B. Market regime and sector context

Minimum output:

```text
market regime state
index trend
index volatility
breadth metrics
sector strength ranking
symbol sector alignment
risk context
```

### C. Watchlist synthesis

Minimum output:

```text
watchlist size
candidate class distribution
setup distribution
sector clustering
strongest names
near-trigger names
extended names
risk-flagged names
next-session research focus
```

### D. Shortlist generation

Minimum output:

```text
rank
symbol
setup type
setup quality
shortlist score
why shortlisted
why not immediate
data status
risk context
confirmation conditions
invalidation conditions
```

### E. Conditional research scenario planning

Minimum output:

```text
symbol
current setup
key levels
confirmation conditions
invalidation conditions
scenario tree
risk/reward estimate
checklist
confidence
caveats
research-only language
```

### F. Historical evidence

Minimum output:

```text
setup type
sample size
forward return distribution
favourable excursion statistics
adverse excursion statistics
outcome rate
regime split
caveat if sample is small
```

## Gap matrix format

The gap map should use this matrix:

```text
Capability | Current state | Target state | Gap | Priority | Future OpenSpec | Acceptance evidence
```

Example:

```text
Deep symbol analysis | /explain returns persisted score | structured analysis with levels/scenarios | missing analysis engine | P0 | deep-symbol-analysis-engine | /analyze FPT returns structured panels
```

## Priority levels

Use:

```text
P0 = required before meaningful research workflow
P1 = required before shortlist or scenario planning is reliable
P2 = important for quality and robustness
P3 = later enhancement
```

## Future OpenSpec structure

### 1. deep-symbol-analysis-engine

Scope:

```text
analysis models
technical context
support/resistance
setup quality
risk/reward basics
/analyze command
analysis.deep_symbol tool
assistant intent deep_analyze_symbol
```

### 2. market-regime-and-sector-context

Scope:

```text
market regime features
breadth metrics
sector mapping
sector strength snapshots
market.regime tool
sector.strength tool
```

### 3. watchlist-synthesis-and-shortlist

Scope:

```text
watchlist synthesis engine
shortlist scoring
shortlist output tables
/shortlist command
watchlist.summarize tool
shortlist.generate tool
```

### 4. research-scenario-plan-engine

Scope:

```text
conditional scenario plan model
confirmation/invalidation levels
risk/reward estimate
checklist
policy-safe language
/research-plan command
research_plan.generate tool
```

### 5. setup-historical-evidence-engine

Scope:

```text
setup event labelling
forward outcome calculation
favourable/adverse excursion stats
regime-conditioned evidence
backtest.setup_outcomes tool
```

### 6. assistant-research-intelligence-tools

Scope:

```text
new intents
new plan builders
new tool allowlist entries
new synthesis templates
grounded answer validation
```

### 7. tui-research-workflow-polish

Scope:

```text
TUI panels for deep analysis
TUI panels for shortlist
TUI panels for scenario planning
status/progress integration
history-friendly workflows
```

## Policy design

The gap map must distinguish between allowed research content and disallowed execution-oriented content.

Allowed:

```text
conditional scenario analysis
setup quality analysis
key level analysis
risk/reward estimate
research checklist
caveats and confidence
```

Disallowed:

```text
account-specific advice
allocation instructions
external platform actions
certainty claims
execution-oriented commands
```

## Evaluation design

Define evaluation artifacts:

```text
research_answer_golden_set.jsonl
shortlist_golden_set.jsonl
scenario_plan_golden_set.jsonl
policy_safety_golden_set.jsonl
```

Each evaluation item should check:

```text
groundedness
uses persisted data only
includes caveats
does not overclaim
does not include execution-oriented language
explains missing data
has useful structure
```

## Documentation design

The final gap map doc should be readable by both humans and coding agents. It should include enough implementation detail to create the future OpenSpecs without re-discovering the same gaps.

## Validation

Because this is a planning OpenSpec, validation means:

```text
- gap map doc exists
- tasks are explicit
- future OpenSpec split is clear
- no runtime tasks are falsely marked complete
- policy constraints are stated
```
