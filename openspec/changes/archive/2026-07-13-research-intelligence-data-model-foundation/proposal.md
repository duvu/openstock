# Proposal: Research Intelligence Data Model Foundation

## Summary

Create the shared persisted data model required by the next OpenStock research-intelligence engines.

This is an OpenSpec-only change. It does not implement migrations or runtime code.

## Motivation

OpenStock already has a useful research warehouse: canonical OHLCV, feature snapshots, candidate scores, daily watchlists, notes, sessions, assistant traces, and outcome tracking. The next target system needs deeper research objects that are reusable across commands, assistant workflows, TUI rendering, sandbox automation, validation, and closed-loop repair.

Without a shared foundation, future engines will create incompatible ad-hoc tables and artifacts.

## Target system alignment

This change supports the OpenStock target system:

```text
opencode-like auto research workspace
warehouse-grounded research intelligence
sandboxed computation
closed-loop validation and repair
no broker/order/account/portfolio/margin/trading execution
```

## Scope

Define schemas, contracts, repositories, and validation expectations for:

```text
market_regime_snapshot
sector_strength_snapshot
symbol_level_snapshot
setup_analysis
shortlist_candidate
research_scenario_plan
setup_evidence_snapshot
research_answer_audit
```

## Non-goals

- No market regime engine implementation.
- No sector ranking engine implementation.
- No deep symbol analysis implementation.
- No shortlist/scenario/evidence runtime logic.
- No assistant intent expansion.
- No broker/order/account/portfolio/margin/trading execution.

## Acceptance direction

Implementation PRs must add migrations, models, repository APIs, tests, docs, and validation evidence before any tasks are marked complete.

## Dependencies

Should be implemented after Phase A control-plane hardening and before the deep research-intelligence engines.
