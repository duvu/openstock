# Proposal: Assistant Research Intelligence Tools

## Summary

Define the OpenSpec for extending the OpenStock assistant from first-generation research Q&A to deep, warehouse-grounded research intelligence workflows.

This is an OpenSpec-only change.

## Motivation

The assistant currently supports bounded intents such as scan, filter, compare, explain, quality, lineage, note, history, and fetch data. The target system needs assistant support for deep symbol analysis, market regime, sector context, watchlist synthesis, shortlist generation, scenario planning, and setup evidence.

The assistant must expand by adding deterministic tools and synthesis templates, not by giving the LLM direct warehouse, filesystem, broker, or execution access.

## Scope

Define requirements for:

```text
deep_analyze_symbol
review_market_regime
review_sector_strength
summarize_watchlist_deep
generate_shortlist
generate_research_scenario
review_setup_evidence
research answer audit
groundedness validation
policy guardrail tests
```

## Non-goals

- No autonomous trading.
- No broker/order/account/portfolio/margin/trading execution tools.
- No unbounded LLM SQL or filesystem access.
- No personalized financial advice.

## Target behavior

Assistant answers must be:

```text
warehouse grounded
tool-traced
caveated
policy checked
auditable
research-only
```
