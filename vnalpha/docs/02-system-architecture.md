# 02. System architecture

> **Status:** current architecture.
>
> Delivery priority and completion status are owned by the root `ROADMAP.md` and
> [GitHub issue #238](https://github.com/duvu/openstock/issues/238). The current
> queue-backed provisioning successor is [#317](https://github.com/duvu/openstock/issues/317).
> This document describes stable component boundaries and the implementation
> direction; it is not a second roadmap.

## Architecture goal

`vnalpha` is a terminal-first, AI-assisted research workspace for Vietnamese
equities. It consumes provider-independent data from `vnstock-service`, persists
research evidence in DuckDB and exposes one typed application layer through the
Typer CLI, Textual TUI and any future read-only API.

```text
vnstock-service = provider access, routing, normalization and data contracts
vnalpha         = research warehouse, deterministic analysis and workspace UX
```

The system permanently remains inside a read-only research boundary. Broker,
account, order, allocation, transfer, margin and execution capabilities are not
part of the architecture.

## Current high-level architecture

```text
External market/reference providers
        ↓
vnstock ProviderPlugin implementations
        ↓
PluginRegistry → PluginRouter → PluginRuntime
        ↓
canonical read-only vnstock-service contracts
        ↓
vnalpha client and bounded ingestion services
        ↓
raw evidence → validation/quarantine → canonical DuckDB tables
        ↓
features → completeness evidence → scores/context/outcomes/artifacts
        ↓
typed application services and deterministic tools
        ↓
Typer CLI + Textual TUI + optional read-only integration adapters
        ↓
grounded assistant classification, planning and synthesis
```

## Component ownership

### `vnstock-service`

Owns:

- provider plugins and provider-specific normalization;
- credentialed data-provider authentication and session handling;
- capability, auth and health-aware routing;
- canonical dataset contracts and quality validation;
- bounded localhost read-only HTTP delivery;
- safe provider diagnostics and provenance.

Does not own research scoring, watchlists, outcomes, backtests, journals or AI
research narratives.

### `vnalpha`

Owns:

- ingestion runs and raw provider evidence received from `vnstock-service`;
- canonical OHLCV selection and quarantine evidence;
- symbol lifecycle and point-in-time taxonomy history;
- feature snapshots and feature-completeness contracts;
- benchmark-relative strength, scoring, watchlists and context snapshots;
- outcome evaluation, event studies and research artifacts;
- assistant/tool/session traces and bounded symbol memory;
- CLI and TUI workflows.

`vnalpha` must not call provider-specific endpoints or SDKs directly. A missing
dataset requires a provider-independent contract in `vnstock`, not an adapter in
the research layer.

## Queue-backed provisioning

The supported single-host write path is deliberately small:

```text
read warehouse readiness
→ close the read connection
→ submit or join one typed SQLite goal
→ one sequential provisioner claims it
→ one global DuckDB writer lock protects a bounded stage
→ terminal job evidence and optional session finalization
```

The queue is local SQLite at
`/var/lib/openstock/queue/provisioning.sqlite3`. The provisioner is one
long-running sequential service, not an interactive TUI process or a pool of
workers. Current-symbol CLI, TUI and assistant callers use the same
`WAIT_UP_TO`, `WAIT_UNTIL_TERMINAL` and `DETACH` policy: the default is bounded
wait, explicit `--wait` waits to a terminal state, and `--no-wait` detaches.
Maintenance production always detaches and session finalization is a separate
typed goal.

Historical replay and backtests never auto-enqueue current acquisition work.
Redis, RabbitMQ, Kafka, multiple workers and a generic DAG are intentionally
out of scope: one host, one durable local queue and one DuckDB writer provide
the required operational boundary without a distributed-systems claim.

## Current application structure

The implementation is a modular monolith. Important packages include:

```text
vnalpha/
├── assistant              # intent, planner, gateway, synthesis and traces
├── cli_app                # Typer command groups
├── clients/vnstock        # provider-independent service client
├── commands               # shared slash-command registry and handlers
├── data_availability      # typed readiness checks and remediation
├── data_provisioning      # shared download/build orchestration
├── features               # feature calculation and completeness policy
├── ingestion              # raw storage, validation and canonical promotion
├── model_routing          # model profiles, fallback policy and observability
├── outcome                # forward-outcome evaluation
├── research_automation    # event studies and reusable research artifacts
├── research_intelligence  # market breadth, regime and sector context
├── scoring                # deterministic candidate scoring and watchlists
├── tui                    # Textual workspace
└── warehouse              # DuckDB schema, migrations and repositories
```

A future split into network services is allowed only after a real concurrency or
multi-user requirement exists. It must not duplicate business rules already
owned by the typed application layer.

## Primary interfaces

### Typer CLI

The CLI is the explicit operational and automation surface. Current command
groups include:

```text
vnalpha init
vnalpha sync ...
vnalpha data ...
vnalpha build ...
vnalpha score
vnalpha watchlist
vnalpha outcome ...
vnalpha eval ...
vnalpha repair ...
vnalpha deploy ...
vnalpha validate ...
vnalpha tui
```

### Textual TUI

The TUI is the main interactive research workspace. It delegates to shared
command handlers, provisioning services and readiness contracts rather than
implementing separate data or scoring logic.

### Optional read-only API

An API is a later integration adapter, not the core architecture. Any endpoint
must delegate to the same typed application services used by CLI/TUI and remain
read-only. No standalone FastAPI service or web dashboard is required for the
current terminal-first product.

## Data and research truthfulness

Every research operation must preserve:

- requested and effective as-of dates;
- provider and ingestion-run lineage;
- canonical validation and quarantine status;
- feature profile and missing-evidence status;
- benchmark identity and methodology version;
- price basis and future adjustment lineage when implemented;
- deterministic rule and artifact versions;
- caveats and remediation when required evidence is missing.

Existing rows without a modern contract remain readable only as legacy evidence
and must fail closed at capability boundaries.

## AI boundary

AI may classify requests, propose bounded plans, explain deterministic output,
compare evidence and produce caveated summaries. It may not:

- fetch unrestricted or provider-specific data;
- execute arbitrary SQL or shell commands;
- alter policy, validation or scoring rules;
- invent missing evidence;
- present aliases or proxies as completed backtests;
- create or execute trading instructions.

## Implemented versus planned

Implemented architecture includes the terminal app, DuckDB warehouse, canonical
OHLCV pipeline, feature/scoring/context contracts, research artifacts and
assistant workflow infrastructure.

Planned capabilities such as adjusted prices, the point-in-time Backtest Lab,
publication-aware fundamentals, official-document retrieval and an optional API
remain owned by their linked GitHub issues. Their target designs do not imply
that a runtime surface already exists.
