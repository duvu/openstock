# 09. Workspace application design

> **Status:** current terminal-first application design.
>
> The term “service” in this document means shared typed application services.
> It does not imply that a long-running FastAPI process or web dashboard is part
> of the current deployment.

## Purpose

`vnalpha` is a research workspace rather than a single scanner command. CLI,
TUI, assistant workflows and future read-only integrations should operate on the
same governed warehouse, readiness checks and application services.

```text
vnstock-service  = provider-independent data delivery
vnalpha          = research workspace and evidence engine
```

## Workspace responsibilities

The workspace owns:

- data/readiness inspection;
- canonical feature and benchmark evidence;
- deterministic scoring and watchlists;
- market breadth, regime and sector context;
- outcome evaluation and event studies;
- research artifacts, notes and bounded symbol memory;
- assistant classification, planning, tool execution and synthesis;
- operator diagnostics, repair evidence and deployment validation.

It does not own provider-specific authentication logic, crawling, broker/account
access, execution or unrestricted data acquisition.

## Shared application-service rule

Every capability should have one typed service contract:

```text
Typer CLI ─┐
Textual TUI ├─→ shared application service → warehouse/provider client
Assistant ─┤
Future API ─┘
```

A surface may format results differently, but it must not reimplement readiness,
selection, scoring, persistence or policy logic.

## Current workspace modules

### Market and data status

Users can inspect:

- provider and ingestion status;
- gaps, invalid observations and quarantine evidence;
- feature completeness;
- benchmark availability;
- market-regime and sector-context readiness.

Missing required evidence produces typed remediation rather than a fabricated or
partially labelled result.

### Daily watchlist

The watchlist is derived from exact-date feature rows that satisfy the scoring
profile. A row should expose:

```text
symbol
as_of_date
score and candidate class
setup/evidence fields
benchmark identity
risk flags and exclusion reasons
feature/build/methodology lineage
```

The watchlist is research evidence, not a trade instruction.

### Symbol workspace

A symbol workspace combines:

- canonical OHLCV lineage;
- feature and completeness evidence;
- relative strength versus an explicit benchmark;
- score/watchlist history;
- outcome and event-study artifacts;
- market/sector context;
- notes and bounded memory claims.

The requested date remains explicit. Current classifications or future data must
not leak into a historical view.

### Research validation

Current validation surfaces include forward-outcome evaluation and deterministic
offline event studies. A full Backtest Lab is a separate point-in-time capability
owned by issue #108 and its child issues. Until those contracts are complete,
the workspace must not label a fixed-horizon proxy as a complete backtest.

### Assistant workspace

The assistant operates through allowlisted tools and shared services. Answers
include evidence references, missing-data disclosure and caveats. The model
cannot directly modify warehouse policy, scores or deployment configuration.

### Research notes and artifacts

Research artifacts preserve input dataset references, parameters, metrics,
lineage, quality and caveats. Notes and symbol memory may reference artifacts but
remain untrusted until reconciled with structured evidence.

## Current interfaces

### Textual TUI

The TUI is the primary interactive workspace. It is installed on the operating
system and launched explicitly:

```bash
vnalpha tui
```

It reads the same configured DuckDB file used by pipeline jobs and delegates
commands to shared handlers.

### Typer CLI

The CLI is the explicit operational surface:

```bash
vnalpha sync ...
vnalpha data ...
vnalpha build ...
vnalpha score ...
vnalpha watchlist ...
vnalpha outcome ...
vnalpha eval ...
vnalpha repair ...
vnalpha validate ...
```

### Optional read-only API

A network API may be added for approved integrations when a concrete requirement
exists. It must:

- expose only bounded read/research operations;
- use the same services and response models as CLI/TUI;
- enforce local authentication and safe diagnostics;
- avoid direct provider calls;
- exclude all broker/account/execution routes.

An API design is a target contract, not evidence that endpoints already exist.

## Warehouse contract

The workspace reads and writes versioned research tables such as:

```text
ingestion_run
symbol_master and classification history
market_ohlcv_raw and canonical_ohlcv
ohlcv_quarantine and gap observations
feature_snapshot and relative_strength_snapshot
candidate_score and daily_watchlist
market_regime_snapshot and sector_strength_snapshot
candidate/watchlist outcome tables
research artifacts, sessions and traces
```

Schema definitions in `vnalpha/warehouse/schema.py` and migrations are the
implementation source of truth. Documentation must not duplicate an outdated
SQL schema as if it were current.

## Deployment model

The current single-host design is:

```text
Docker
├── vnstock-service
└── vnalpha-worker one-shot jobs

Host
├── /var/lib/openstock/warehouse/warehouse.duckdb
└── vnalpha Debian package → CLI/TUI
```

The TUI is not a background container. Pipeline writes are serialized because
DuckDB is an embedded file; interactive use is primarily read-only while jobs
are running.

## Design rules

1. Evidence precedes narrative.
2. Required missing evidence fails closed.
3. Historical operations remain point-in-time.
4. All surfaces share one typed service contract.
5. Provider-specific behavior remains in `vnstock`.
6. Current implementation and target architecture are labelled separately.
7. The workspace remains read-only research software.
