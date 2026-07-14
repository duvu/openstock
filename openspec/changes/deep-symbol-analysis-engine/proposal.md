# Proposal: Deep Symbol Analysis Engine

## Summary

Define the OpenSpec for a consolidated deep symbol analysis engine for OpenStock.

This change is being implemented incrementally. GitHub issue #75 narrows the
first executable slice to the existing one-symbol core contract: symbol
master, canonical symbol OHLCV, benchmark OHLCV, exact-date features, and
candidate score. Market-regime and sector-strength provisioning remain the
next ordered slice; this slice must disclose their absence rather than infer
or fabricate them.

## Motivation

Current `/explain SYMBOL` can explain a candidate score, but the target system needs a richer warehouse-grounded analysis object that combines trend, momentum, relative strength, volume, volatility, levels, setup quality, caveats, and confidence.

Deep analysis is the core object that later powers assistant answers, TUI drilldowns, shortlist rationale, scenario planning, and historical evidence lookup.

The existing data-availability service ensures symbol, benchmark, feature, and
score artifacts, but `/analyze` bypasses it and the assistant hook logs and
suppresses a failed ensure before executing the read tool. This can produce a
plausible-looking partial analysis. The first implementation slice therefore
introduces a typed, audited, fail-closed readiness gate for the core contract.

## Scope

Define requirements for:

```text
/analyze SYMBOL
analysis.deep_symbol tool
DeepSymbolAnalysis output contract
SymbolLevelSnapshot usage
SetupAnalysis persistence
multi-timeframe context
support/resistance levels
setup quality and confidence
research-only scenario summary
deterministic readiness for deep-analysis inputs
explicit CLI and TUI user commands for raw and derived data provisioning
structured provisioning status and audit events
```

## Capabilities

### Modified capabilities

- `auto-data-provisioning`: extend deterministic readiness from score inputs to
  the market-regime and sector-strength inputs requested by deep analysis.

### New capabilities

- `data-provisioning-commands`: expose bounded, explicit user commands for
  downloading raw inputs and building supported derived data types.

## Non-goals

- No buy/sell recommendation.
- No target price as investment advice.
- No order, broker, account, portfolio, allocation, margin, or live trading action.
- No unrestricted LLM-generated analysis without deterministic evidence.
- No assistant-selected or assistant-invoked `data.fetch` tool.
- No implicit full-universe refresh for one-symbol analysis unless the user
  explicitly requests a market or sector context build that requires it.

## Issue #75 critique and implementation boundary

Issue #75 correctly identifies the safety defect: readiness must be a
deterministic application-service decision, and failed required inputs must
block the read tool. The issue's phrase "every deep analysis" is implemented
at the command and assistant-executor boundaries, which are the supported
user-facing invocation paths. Direct Python helpers remain internal test and
composition functions, not an assistant capability.

The requested "Data Readiness" panel must be derived from the typed result,
not reconstructed from log text. A lock-contention or provisioning failure is
not a partial-success condition for the five core artifacts: it is a failed
gate with a concrete manual remediation command. Optional market and sector
context stays explicitly `NOT_REQUESTED`/unavailable in the research payload
until the subsequent context-readiness work supplies bounded builders.

## Issue #92 readiness-contract completion

Before market and sector readiness is extended, the five-core-artifact gate
must make its operational evidence trustworthy. Each artifact carries typed
availability, freshness, quality, lineage, and ordered remediation evidence;
rendered warnings are display-only and cannot determine control flow. The
remediation domain model is independent of CLI spelling, so it renders only
commands registered today until the later data-command namespace exists.

Readiness resolves one Vietnamese-market as-of date before the core ensure
call, establishes or reuses its correlation ID, and emits the start audit
event before any provisioning. Known and unexpected ensure exceptions both
produce a sanitized, fail-closed terminal result. This slice does not build
market-regime or sector-strength snapshots and does not add `vnalpha data`
commands; those remain issues #76 and #77.

## Target output

```text
symbol
as_of_date
data_freshness
lineage
trend_context
momentum_context
relative_strength_context
volume_context
volatility_context
setup_quality
support_resistance_levels
scenario_summary
risks_caveats
missing_data
confidence
```

## Dependencies

Depends on the accepted auto-data-provisioning and market-regime-and-sector-context
contracts. The active change is partial: the deep tool, assistant intent, and
baseline ensure service exist, but context readiness, explicit manual commands,
and fail-closed integration remain.
