# openstock System Roadmap

## Product thesis

`openstock` is a local-first Vietnamese equity research system.

The system exists to answer:

```text
Which stocks are worth monitoring today, why, what evidence supports the view,
and what risks or data-quality issues should the user review?
```

The system is not a trading execution platform.

It must not:

```text
- place orders
- connect to broker execution APIs
- manage brokerage accounts
- manage user portfolios
- present deterministic scores as investment advice
- present LLM-generated analysis as a guaranteed prediction
```

---

## Repository and product boundaries

`openstock` owns orchestration, cross-repo roadmap, OpenSpec changes, local runbooks, and end-to-end acceptance criteria.

```text
openstock
├── vnstock   # data-only market data service
└── vnalpha   # stock research workspace
```

The long-term boundary is:

```text
vnstock   = simple data platform/service
vnalpha   = programmable stock research workspace
openstock = source-of-truth for roadmap/specs/integration
```

---

## Target architecture

```text
User
├── CLI slash commands
├── TUI workspace
└── Natural-language research prompt

vnalpha: Stock Research Workspace
├── Command Router
│   ├── slash command parser
│   ├── natural-language intent router
│   └── command history
│
├── Agent Controller
│   ├── LLM Gateway client
│   ├── planner
│   ├── guardrails
│   ├── tool executor
│   └── tool/code trace
│
├── Research Core
│   ├── DuckDB research warehouse
│   ├── canonical OHLCV
│   ├── feature store
│   ├── deterministic scoring engine
│   ├── daily watchlist generator
│   ├── outcome tracking
│   └── backtest lab
│
├── Python Research Sandbox
│   ├── generated analysis code
│   ├── isolated execution
│   ├── read-only data access by default
│   ├── package allowlist
│   ├── timeout and memory limits
│   └── chart/table/artifact output
│
├── Tool Layer
│   ├── vnalpha local tools
│   ├── vnstock REST client
│   ├── DuckDB query tools
│   ├── feature/scoring tools
│   ├── backtest tools
│   └── MCP client later
│
└── Review Surfaces
    ├── watchlist
    ├── symbol detail
    ├── research note
    ├── data quality
    ├── outcome review
    ├── code execution result
    └── tool trace

vnstock: Data-only Market Data Service
├── provider plugins
├── provider health/auth routing
├── local credential handling for data providers
├── dataset contracts
├── normalized response envelope
└── read-only REST API
```

---

## Boundary rules

### `vnstock` stays simple and data-only

`vnstock` should remain a focused local market data service.

Allowed in `vnstock`:

```text
- provider plugin architecture
- provider registry and router
- provider health checks
- provider capability discovery
- local provider authentication where required for data access
- normalized dataset contracts
- read-only REST endpoints
- data/meta/diagnostics response envelope
```

Forbidden in `vnstock`:

```text
- alpha scoring
- watchlist generation
- backtesting
- Python research sandbox
- LLM planner or analyst layer
- natural-language UX
- portfolio management
- brokerage order execution
- account/trading workflow
```

### `vnalpha` becomes the stock research workspace

`vnalpha` is the user-facing research environment.

Allowed in `vnalpha`:

```text
- CLI and TUI workspace
- slash commands
- natural-language research prompt
- DuckDB research warehouse
- canonical market data model
- feature engineering
- deterministic scoring
- watchlist generation
- evidence and risk explanation
- outcome tracking
- backtesting
- generated Python analysis in a sandbox
- LLM-assisted planning and explanation
- MCP tool interoperability later
```

Forbidden by default in `vnalpha` product mode:

```text
- brokerage order execution
- account management
- autonomous trading
- LLM-only final signals
- uncontrolled SQL execution
- unrestricted file-system access
- unrestricted internet access from generated code
- self-modifying application code
```

Developer mode may later allow codebase mutation, but it must be explicitly separated from product research mode.

---

## Interface contracts

### `vnstock` service contract

`vnstock` exposes data through local read-only APIs.

Required endpoints:

```text
GET /v1/reference/symbols
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/providers/health
GET /v1/providers/capabilities
```

Required response envelope:

```text
data
meta
diagnostics
```

Auth boundary:

```text
- CLI auth is allowed for data-provider credentials, especially TCBS local interactive auth.
- REST login is forbidden.
- Broker/account/order/portfolio APIs are forbidden.
```

### `vnalpha` workspace contract

`vnalpha` consumes `vnstock` data and builds research artifacts.

Core artifacts:

```text
symbol_master
market_ohlcv_raw
canonical_ohlcv
feature_snapshot
candidate_score
daily_watchlist
rejected_symbol
candidate_outcome
research_session
research_artifact
tool_trace
code_execution_trace
```

Core command surfaces:

```text
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
vnalpha tui
```

Future workspace commands:

```text
/scan
/filter
/compare
/explain
/quality
/lineage
/outcome
/backtest
/python
/ask
```

---

## Phase 1-4 — vnstock data-only foundation

Phase 1-4 belong mainly to `vnstock`.

The goal is not to make `vnstock` a research engine. The goal is to make it a reliable, simple, read-only data foundation for `vnalpha`.

### Phase 1 — Core contracts and plugin foundation

Goal:

```text
Define the internal plugin architecture: ProviderPlugin, PluginRegistry, DatasetContract, DataResult.
```

Closure target:

```text
97-99% once conformance tests, contract tests, and status docs are complete.
```

### Phase 2 — Provider plugin normalization

Goal:

```text
Normalize built-in providers behind ProviderPlugin and default_plugin_registry().
```

Built-in providers:

```text
KBS
VCI
DNSE
TCBS
FMARKET
MSN
FMP
```

### Phase 3 — Health-aware and auth-aware routing

Goal:

```text
Route dataset requests by provider capability, priority, health, cooldown, and auth policy.
```

### Phase 3.5 — PluginRuntime default execution path

Goal:

```text
Make PluginRuntime the default execution path for migrated datasets.
```

### Phase 4 — Auth-aware local data service runtime

Goal:

```text
Expose vnstock as a local-first, read-only market data service.
```

Definition of Done:

```text
- vnstock-service starts locally.
- core read-only endpoints work.
- responses include data/meta/diagnostics.
- provider health and capability endpoints work.
- local provider auth works where required for data access.
- no trading/account/order/portfolio API exists.
- no research/scoring/backtest/LLM responsibility exists in vnstock.
```

---

## Phase 5 — End-to-End Alpha Discovery MVP with TUI

Phase 5 is the first system-level phase owned by `openstock`, implemented primarily in `vnalpha`, and dependent on `vnstock` as the data service.

### Goal

Create the first useful deterministic research workflow:

```text
vnstock-service
→ vnalpha sync
→ DuckDB research warehouse
→ canonical OHLCV
→ feature store
→ scoring engine
→ daily watchlist
→ TUI workspace
```

### Output

A daily alpha discovery watchlist:

```text
symbol
score
candidate_class
setup_type
evidence
risk_flags
provider lineage
data quality status
```

### User interface

Use TUI, not Streamlit.

Recommended stack:

```text
Textual   # TUI framework
Rich      # tables, panels, console rendering
Typer     # CLI commands
DuckDB    # local research database
Pandas    # feature engineering
Plotext   # optional terminal charts
```

### Phase 5 modules

```text
5.0 openstock orchestration
5.1 vnstock operational contract
5.2 vnalpha core skeleton
5.3 vnstock client
5.4 DuckDB research warehouse
5.5 canonical OHLCV builder
5.6 feature store v1
5.7 alpha scoring v1
5.8 daily watchlist TUI
```

### Minimum commands

```bash
make up-vnstock
make sync
make features
make score
make tui

vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui
```

### Minimum TUI screens

```text
Home / Market Overview
Daily Watchlist
Symbol Detail
Rejected Symbols
Provider / Data Quality
```

### Minimum scoring model

```text
Trend score              25
Relative strength score  25
Volume score             15
Base/compression score   15
Breakout proximity       10
Risk/data quality        10
```

Candidate classes:

```text
STRONG_CANDIDATE  score >= 80
WATCH_CANDIDATE   65 <= score < 80
WEAK_CANDIDATE    50 <= score < 65
IGNORE            score < 50
```

Setup types v1:

```text
ACCUMULATION_BASE
BREAKOUT_ATTEMPT
MOMENTUM_CONTINUATION
PULLBACK_TO_TREND
MEAN_REVERSION
UNCLASSIFIED
```

### Definition of Done

```text
- openstock can start vnstock-service locally.
- vnalpha CLI runs.
- vnalpha can call vnstock-service.
- VN30 symbols and OHLCV can be synced or loaded from fixtures in CI.
- DuckDB warehouse is created.
- canonical_ohlcv is built.
- feature_snapshot is built.
- candidate_score is generated.
- daily_watchlist is generated.
- TUI opens daily watchlist.
- TUI can drill into symbol detail.
- each candidate has score breakdown, evidence, risk flags, lineage, and data quality status.
- no buy/sell/order/portfolio language appears in API or TUI.
```

---

## Phase 5.8 — Research Workspace Command Layer

Goal:

```text
Turn vnalpha from a pipeline/TUI into a command-driven research workspace.
```

Scope:

```text
slash command parser
command registry
local tool registry
research session history
tool trace screen
command result renderer
```

Initial slash commands:

```text
/scan
/filter
/compare
/explain
/quality
/lineage
/note
```

Example:

```text
/scan VN30 --setup ACCUMULATION_BASE --min-score 70
```

Definition of Done:

```text
- slash commands are parsed deterministically.
- commands call typed vnalpha tools.
- every command writes a research_session entry.
- every tool call is visible in tool_trace.
- command outputs can render tables, panels, and saved notes.
```

---

## Phase 5.9 — Natural-Language Research Assistant

Goal:

```text
Allow the user to ask research questions in natural language while vnalpha maps the request to controlled tools.
```

Architecture:

```text
natural-language prompt
→ intent router
→ planner
→ allowed tool calls
→ deterministic data/query/scoring tools
→ explanation with lineage and trace
```

Allowed:

```text
parse user intent
build a research plan
call allowed vnalpha/vnstock tools
explain deterministic results
critique risks
summarize watchlists
produce research notes
```

Forbidden:

```text
generate AI-only signals
override deterministic score
hide tool calls
claim certainty
issue buy/sell instructions
place orders
```

Definition of Done:

```text
- LLM Gateway client works through configuration.
- prompt router maps natural language into a tool plan.
- tool allowlist is enforced.
- every LLM plan and tool call is traced.
- answers cite data lineage and executed tools.
- unsupported or unsafe requests are refused cleanly.
```

---

## Phase 6 — Outcome Tracking and Feedback Loop

Goal:

```text
Measure whether candidates actually work after fixed forward horizons.
```

Horizon windows:

```text
5 sessions
10 sessions
20 sessions
60 sessions
```

Tables:

```text
candidate_outcome
watchlist_outcome
score_bucket_performance
setup_type_performance
```

Metrics:

```text
forward_return
excess_return_vs_vnindex
max_gain
max_drawdown
hit_rate
failure_rate
average_return_by_score_bucket
```

Reason:

```text
Without outcome tracking, scoring remains an unverified heuristic.
```

Definition of Done:

```text
- historical watchlists can be evaluated after forward windows complete.
- scores can be calibrated by realized outcome.
- weak setup types and false positives can be identified.
- outcome review is visible in CLI/TUI.
```

---

## Phase 7 — Python Research Sandbox

Goal:

```text
Allow vnalpha to generate and execute temporary Python analysis code safely.
```

Use cases:

```text
custom factor analysis
symbol/sector comparison
correlation analysis
quick statistical tests
chart/table generation
research notebook snippets
```

Sandbox requirements:

```text
isolated execution
no external network by default
read-only warehouse access by default
package allowlist
short timeout
memory limit
artifact output
code trace
result trace
```

Allowed packages v1:

```text
pandas
numpy
duckdb
scipy
matplotlib
plotext
```

Definition of Done:

```text
- /python command can run generated code in an isolated sandbox.
- generated code, input data references, output, and errors are stored.
- user can inspect code and result.
- sandbox cannot write arbitrary files or access external network by default.
- sandbox cannot modify vnalpha source code in product mode.
```

---

## Phase 8 — Backtest Lab v1

Goal:

```text
Validate scoring and setup rules historically through a structured backtest engine instead of ad-hoc Python only.
```

Scope:

```text
setup-type backtests
score-bucket backtests
market-regime split
threshold sensitivity
transaction-cost assumption
look-ahead-bias checks
walk-forward split
report generation
```

Definition of Done:

```text
- backtests are reproducible from a versioned strategy spec.
- transaction cost and slippage assumptions are explicit.
- look-ahead bias checks exist.
- reports include return, drawdown, hit rate, and sample size.
- backtest output remains research support, not trading instruction.
```

---

## Phase 9 — Reliable Batch Ingestion and Warehouse Hardening

Goal:

```text
Harden data ingestion after the research loop proves useful.
```

Scope:

```text
rate limiter
retry policy
incremental sync
raw archive
Parquet/DuckDB optimization
data gap detector
provider failover report
scheduled jobs
warehouse migration discipline
```

Reason:

```text
Do not over-engineer ingestion before the watchlist/outcome loop proves useful.
```

---

## Phase 10 — MCP Client and Tool Interoperability

Goal:

```text
Let vnalpha interoperate with external tools through MCP while keeping REST/DuckDB as the deterministic data plane.
```

Principle:

```text
REST/DuckDB = data plane
MCP         = tool interoperability plane
LLM Gateway = planner/explainer
Research Core = deterministic source of truth
```

Scope:

```text
MCP client
MCP tool registry
vnstock MCP adapter wrapping REST if needed
tool allowlist
timeout/cancel
permission model
tool-call audit
```

Definition of Done:

```text
- vnalpha can call approved MCP tools.
- MCP calls are traced.
- MCP cannot bypass deterministic scoring rules.
- MCP cannot expose order execution paths.
```

---

## Phase 11 — AI Analyst Workflows

Goal:

```text
Use AI to explain, critique, and package deterministic research artifacts, not to create independent trading signals.
```

Allowed workflows:

```text
market overview
sector rotation summary
candidate discovery explanation
symbol deep dive
risk critique
daily research brief
weekly outcome review
research note generation
```

Forbidden:

```text
AI-only prediction
buy/sell instruction
order generation
portfolio execution
```

Definition of Done:

```text
- AI workflows are grounded in warehouse data, watchlists, outcomes, or backtests.
- every answer exposes tool/data lineage.
- AI analysis can be traced and reproduced as far as possible.
- unsupported claims are flagged rather than hidden.
```

---

## Phase 12 — Advanced Pattern Engine

Goal:

```text
Add richer deterministic pattern families after candidate outcome data exists.
```

Candidate patterns:

```text
VCP
healthy pullback
failed breakout
distribution day
base-on-base
relative strength new high
sector rotation confirmation
```

Definition of Done:

```text
- each pattern has an explicit formula.
- each pattern can be backtested.
- each pattern exposes evidence and failure cases.
- pattern scores feed the deterministic scoring engine.
```

---

## Phase 13 — ML Ranking

Goal:

```text
Train ranking models only after enough outcome history exists.
```

Scope:

```text
feature set versioning
label construction
train/validation/test split
walk-forward validation
model explainability
model drift monitoring
comparison against deterministic baseline
```

Output must remain ranking/research support, not prediction guarantee or investment advice.

Definition of Done:

```text
- ML ranking beats or usefully complements deterministic baseline on out-of-sample tests.
- feature and label leakage checks exist.
- model output includes confidence/uncertainty and explanation.
- ML output cannot bypass research-only safety boundaries.
```

---

## Operating principles

### Build the smallest useful research loop first

```text
VN30
→ OHLCV
→ canonical data
→ features
→ score
→ watchlist
→ TUI
→ outcome tracking
```

### Keep responsibilities separated

```text
vnstock   = data only
vnalpha   = research workspace
openstock = specs/roadmap/orchestration
```

### Keep LLMs subordinate to deterministic research artifacts

```text
LLM can plan, call tools, explain, critique, and summarize.
LLM must not create final signals outside deterministic scoring.
```

### Keep Python powerful but controlled

```text
Generated Python is for sandboxed research analysis.
It must not become unrestricted code execution or self-modifying app behavior.
```

### Do not optimize late-stage complexity too early

Do not prioritize ingestion hardening, MCP, AI analyst workflows, advanced patterns, or ML ranking before the daily watchlist and outcome loop work reliably.
