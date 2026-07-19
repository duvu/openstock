# vnalpha

`vnalpha` is an OpenBB-inspired, AI-assisted research workspace for Vietnamese equities.

It runs as the research layer of OpenStock and consumes normalized market data from `vnstock-service` instead of embedding provider-specific access logic.

```text
vnstock-service  = data-only market/reference/fundamental platform
vnalpha          = terminal-first research workspace and evidence engine
```

## Product objective

Build a trustworthy, reproducible workspace that helps a researcher:

- maintain provider-independent Vietnamese market data;
- produce evidence-backed daily watchlists and symbol analysis;
- inspect market regime, sector strength, technical setups and forward outcomes;
- test hypotheses and strategies with point-in-time data and explicit assumptions;
- use AI for explanation, critique and workflow assistance without allowing it to invent evidence or bypass deterministic policy.

The live delivery order is maintained in [the canonical roadmap](../ROADMAP.md) and GitHub issue [#238](https://github.com/duvu/openstock/issues/238).

## Architecture

```text
vnstock providers
→ PluginRuntime and canonical data contracts
→ vnstock local read-only service
→ vnalpha ingestion and validation
→ canonical DuckDB warehouse
→ features, scores, market/sector context and research artifacts
→ deterministic tools and application services
→ Typer CLI and Textual TUI
→ grounded AI synthesis with citations, caveats and audit evidence
```

`vnalpha` owns research datasets and workflows such as:

- canonical OHLCV and readiness evidence;
- feature snapshots and candidate scores;
- pattern/setup analysis and watchlists;
- market-regime and sector-strength snapshots;
- forward outcomes, event studies and the future point-in-time Backtest Lab;
- research artifacts, source references, journals and bounded symbol memory;
- CLI/TUI research workflows and optional read-only service interfaces.

## Primary interfaces

- **Textual TUI** — the main interactive workspace.
- **Typer CLI** — explicit data, build, analysis, evaluation and maintenance commands.
- **Deterministic local tools** — bounded read/research operations used by the assistant.
- **Optional read-only API** — for approved integrations; not a broker or execution surface.

## Core principles

1. **Evidence before narrative.** Current warehouse and validated tool output outrank summaries, memory and model prose.
2. **Fail closed.** Missing, stale, invalid or low-quality required inputs block the research operation or are disclosed as optional missing context.
3. **Point-in-time correctness.** Historical analysis must not use future classifications, publications, actions or observations.
4. **One service contract across surfaces.** CLI, TUI, assistant and API should delegate to the same typed application services.
5. **Auditable research.** Dates, providers, versions, assumptions, lineage, caveats and outcomes remain inspectable.
6. **Read-only research boundary.** No broker, account, order, portfolio mutation, allocation, margin, transfer or trading-execution capability.

AI is used for classification, explanation, comparison, critique and synthesis. It must not autonomously fetch unrestricted data, execute raw SQL/shell code, alter policy, or replace deterministic scoring and validation rules.

## Documentation

Start here:

- [Project overview](docs/README.md)
- [Project roadmap and governance](../ROADMAP.md)
- [Common implementation failures and prevention checklist](docs/common-implementation-failures.md)
- [Vision and scope](docs/01-vision-and-scope.md)
- [System architecture](docs/02-system-architecture.md)
- [Data pipeline](docs/03-data-pipeline.md)
- [Pattern engine](docs/04-pattern-engine.md)
- [Backtest and outcome tracking](docs/05-backtest-and-outcome.md)
- [AI layer](docs/06-ai-layer.md)
- [Workspace service design](docs/09-workspace-service-design.md)
- [Deployment architecture](docs/11-deployment-architecture.md)
- [Research answer evaluation fixtures](docs/research-answer-evaluation.md)

## Current technology direction

- Python 3.10+
- DuckDB warehouse and local filesystem artifacts
- Pandas/NumPy for deterministic data processing
- Typer CLI
- Textual TUI
- FastAPI only for bounded read-only service surfaces
- LiteLLM-compatible gateway for AI assistance
- pytest, Ruff, runtime replay and OpenSpec evidence for validation

## Compliance note

OpenStock is for research, education and market analysis. It does not provide investment advice or guarantee performance. The project permanently excludes automated order routing and trading execution, even when a data vendor SDK also contains broker or account functions.
