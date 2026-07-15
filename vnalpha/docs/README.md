# vnalpha documentation

`vnalpha` is the terminal-first, AI-assisted research workspace in OpenStock. It consumes normalized data from `vnstock-service` and owns research evidence, analysis workflows and user interaction.

```text
vnstock-service  = independent data-only market platform
vnalpha          = independent research workspace and evidence engine
```

`vnalpha` must not call provider-specific data endpoints directly. Provider access, authentication and normalization belong in `vnstock`; `vnalpha` consumes canonical service contracts and then owns ingestion evidence, the DuckDB warehouse, features, patterns, outcomes, watchlists, research artifacts, grounded AI explanations and journals.

## Canonical roadmap

The live delivery queue is maintained only in:

- [root ROADMAP.md](../../ROADMAP.md);
- GitHub issue [#90 — OpenStock unified product roadmap](https://github.com/duvu/openstock/issues/90).

Documents such as `07-implementation-roadmap.md` and `10-roadmap-phases.md` preserve earlier design history. They are non-authoritative and must not be used to infer current priority, dependency or completion status.

## Document status convention

Current architecture documents begin with an explicit `Status` block. Target capabilities are labelled as planned and linked to their owning issues. Historical documents are retained for context only. A target design must not be interpreted as evidence that a runtime surface already exists.

## Documentation map

1. **Vision and scope** — product objective and permanent boundaries.
2. **System architecture** — service split, warehouse, application services and execution flow.
3. **Data pipeline** — ingestion, validation, canonicalization, readiness and provenance.
4. **Pattern engine** — structured price/volume pattern evidence.
5. **Backtest and outcome tracking** — forward outcomes, event studies and the target point-in-time Backtest Lab.
6. **AI layer** — safe classification, planning, deterministic tools and grounded synthesis.
7. **Workspace interfaces** — Typer CLI, Textual TUI and optional read-only API boundaries.
8. **Operations and hardening** — logging, packaging, evaluation, repair and implementation guardrails.
9. **Historical planning documents** — earlier roadmaps retained for context only.

## Key documents

### Current architecture and operation

- [Vision and scope](01-vision-and-scope.md)
- [System architecture](02-system-architecture.md)
- [Data pipeline](03-data-pipeline.md)
- [Pattern engine](04-pattern-engine.md)
- [Backtest and outcome tracking](05-backtest-and-outcome.md)
- [AI layer](06-ai-layer.md)
- [Initial repository structure](08-initial-repository-structure.md)
- [Workspace application design](09-workspace-service-design.md)
- [Deployment architecture](11-deployment-architecture.md)
- [Common implementation failures and prevention checklist](common-implementation-failures.md)
- [Sandboxed compute](sandbox-compute.md)
- [Research automation](research-automation.md)
- [Research answer evaluation fixtures](research-answer-evaluation.md)
- [Four-phase hardening guide](four-phase-hardening.md)
- [Hardening branch protection](branch-protection.md)
- [Closed-loop repair and validation](closed-loop-repair.md)
- [Symbol knowledge memory](symbol-memory.md)

### Historical, non-authoritative planning

- [Earlier implementation roadmap](07-implementation-roadmap.md)
- [Earlier phased roadmap](10-roadmap-phases.md)

## Stable architecture

```text
vnstock provider plugins
→ PluginRuntime and canonical contracts
→ local read-only vnstock service
→ vnalpha ingestion and validation
→ raw evidence + validation-gated canonical warehouse
→ feature, score, regime, sector and outcome builders
→ research-artifact and source-reference stores
→ deterministic application services and tools
→ Typer CLI + Textual TUI + optional read-only API
→ grounded assistant synthesis
```

The Textual TUI is the main interactive workspace. The CLI is the explicit operational and research command surface. Any API remains read-only and delegates to the same typed application services.

## Research workflow direction

A useful OpenStock workspace should allow the user to:

- inspect market and data-readiness status;
- build and review evidence-backed watchlists;
- drill into one symbol or setup;
- see trend, momentum, volume, relative strength, levels, regime and sector evidence;
- review invalid or quarantined data and repair guidance;
- compare outcomes and historical setup evidence;
- run reproducible point-in-time research and backtests when their prerequisites are complete;
- generate grounded AI explanations with source references and caveats;
- maintain bounded, auditable research notes and symbol memory.

## Example research output

```text
Ticker: FPT
As of: 2026-07-14
Setup: accumulation breakout
Evidence:
- canonical history passed validation
- breakout volume versus a declared baseline
- relative strength versus an explicit benchmark
- market-regime and sector snapshots with methodology/version lineage
Risks:
- missing or stale evidence is disclosed
- invalidation conditions are deterministic
Sources:
- provider, ingestion run, builder versions and artifact references
```

The labels and numbers in a real result must come from actual computation. Fixed-horizon proxies, aliases or incomplete methodology must not be presented as a completed backtest or investment recommendation.

## Permanent boundary

OpenStock remains inside the **read-only research boundary**. It does not expose broker login, order placement, account access, portfolio mutation, allocation, margin, transfers or trading execution. Stored documents, memory and model output remain untrusted evidence and cannot modify policies, tools or approval requirements.
