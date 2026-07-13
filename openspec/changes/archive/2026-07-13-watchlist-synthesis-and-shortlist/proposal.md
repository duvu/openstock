# Proposal: Watchlist Synthesis and Shortlist

## Summary

Define the OpenSpec for turning OpenStock's daily watchlist into a synthesized research agenda and a narrower shortlist artifact.

This is an OpenSpec-only change.

## Motivation

OpenStock already creates a ranked `daily_watchlist`. The target system needs to explain the list as a set of research situations, not just a score table.

Users need to know:

```text
what setups dominate today
which names are near confirmation
which names are extended
which sectors cluster
which names deserve deeper review
what risks should be monitored next session
```

## Scope

Define requirements for:

```text
/watchlist-summary
/shortlist
watchlist synthesis artifact
shortlist run and shortlist candidate records
class/setup/sector/risk distributions
near-trigger and extended groups
research focus for next session
assistant tools/intents
TUI render contracts
```

## Non-goals

- No buy/sell list.
- No capital allocation or ranking as portfolio instruction.
- No automated trading.
- No broker/order/account integration.

## Target output

Watchlist summary:

```text
watchlist_size
class_distribution
setup_distribution
sector_clustering
strongest_names
near_trigger_names
extended_names
risk_flagged
next_session_focus
```

Shortlist candidate:

```text
rank
symbol
setup_type
setup_quality
shortlist_score
why_shortlisted
why_restrained
confirmation_conditions
invalidation_conditions
data_status
risk_context
```
