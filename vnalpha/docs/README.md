# vnalpha documentation

`vnalpha` is designed as an OpenBB-inspired AI-assisted Research Workspace and Pattern Detection Platform for Vietnamese equities.

The product is now explicitly split from the data layer:

```text
vnstock-service  = independent market data platform service
vnalpha-service  = independent research workspace service
```

`vnalpha` should not call provider-specific market data endpoints directly. It should consume validated, normalized, and diagnosable data from `vnstock-service`, then own the research workspace layer: features, patterns, outcomes, watchlists, AI explanations, dashboards, reports, and journals.

## Documentation map

The documentation is organized around the main engineering concerns:

1. **Vision and scope** — what the system should and should not do.
2. **System architecture** — service split, workspace architecture, data stores, and execution flow.
3. **Data pipeline** — how `vnstock-service` data is ingested, validated, canonicalized, and stored.
4. **Pattern engine** — how price/volume patterns are represented, detected, scored, and invalidated.
5. **Backtest and outcome tracking** — how every detected pattern is evaluated after 5/10/20/60 sessions.
6. **AI layer** — how LLMs are used safely for explanation, critique, reporting, and research assistance.
7. **Implementation roadmap** — the earlier implementation roadmap.
8. **Repository structure** — a practical starting layout for the codebase.
9. **Workspace service design** — service API, workspace modules, UI/API/agent boundaries.
10. **Phased roadmap** — the end-to-end phase plan from workspace foundation to ML ranking.
11. **Deployment architecture** — Docker data platform, DuckDB warehouse, and Debian terminal app deployment.

## Key documents

- [Vision and scope](01-vision-and-scope.md)
- [System architecture](02-system-architecture.md)
- [Data pipeline](03-data-pipeline.md)
- [Pattern engine](04-pattern-engine.md)
- [Backtest and outcome tracking](05-backtest-and-outcome.md)
- [AI layer](06-ai-layer.md)
- [Implementation roadmap](07-implementation-roadmap.md)
- [Initial repository structure](08-initial-repository-structure.md)
- [Workspace service design](09-workspace-service-design.md)
- [Phased roadmap](10-roadmap-phases.md)
- [Deployment architecture](11-deployment-architecture.md)
- [Research answer evaluation fixtures](research-answer-evaluation.md)

## Design stance

The project should start as an end-of-day research workspace service:

```text
vnstock-service
→ validated market data
→ vnalpha-service ingestion
→ canonical OHLCV
→ feature store
→ pivot engine
→ pattern engine
→ outcome tracker
→ watchlist API
→ workspace dashboard
→ AI explanation / risk critique / journal
```

It should not start as:

```text
LLM sees chart
→ LLM predicts price
→ bot places order
```

The second approach is hard to audit, easy to overfit, and unsafe for real-money trading.

## OpenBB-inspired direction

`vnalpha` should be closer to a research workspace than a single-purpose scanner.

The first useful workspace should allow a user to:

- open a market overview;
- inspect a pattern watchlist;
- drill into one symbol or pattern instance;
- view evidence features and chart context;
- review failed breakouts;
- compare outcomes by pattern type;
- generate grounded AI explanations;
- keep a research journal.

## First target outcome

The first useful version of `vnalpha` should produce a daily watchlist with clear evidence:

- ticker;
- pattern type;
- pattern score;
- setup status;
- base range;
- volume confirmation;
- relative strength;
- market regime;
- risk flags;
- invalidation level;
- AI-generated explanation;
- later forward outcome.

Example:

```text
Ticker: FPT
Pattern: ACCUMULATION_BREAKOUT
Score: 86
Status: CONFIRMED
Evidence:
- 38-session base, 8.7% range
- breakout volume 1.9x 20-session average
- close strength 0.84
- RS 20d +6.4% versus VN-Index
Risk:
- price 7.8% above MA20
- sector confirmation weak
Invalidation:
- close back below breakout level or MA20
```
