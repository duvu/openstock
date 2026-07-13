# Research-intelligence data model foundation

`vnalpha.research_models` defines durable, research-only contracts for these
objects:

- `MarketRegimeSnapshot`: market state, index context, breadth summary, and
  a reference to sector-strength evidence.
- `SectorStrengthSnapshot`: ranked sector-relative performance and breadth.
- `SymbolLevelSnapshot`: reproducible support, resistance, pivot, and source
  bar references for one symbol/date.
- `SetupAnalysis`: a caveated description of a symbol setup and its context.
- `ShortlistCandidate`: an explainable, bounded shortlist row for a run.
- `ResearchScenarioPlan`: conditional research scenarios, not instructions to
  execute a trade.
- `SetupEvidenceSnapshot`: sample-bounded setup history and distribution data.
- `ResearchAnswerAudit`: the assistant intent, tools, artifacts, freshness,
  groundedness, policy, missing data, caveats, and correlation ID.

Every persisted object has an explicit identifier, correlation ID, timestamp,
and validation at the repository boundary. Data-bearing objects also carry an
as-of date, freshness, lineage, methodology version, quality status, and
caveats. Scenario and evidence records require caveats. Validators reject
execution-oriented fields such as broker, order, account, portfolio, margin,
transfer, allocation, position, trade, and execution.

## Repository API

`ResearchModelsRepository` exposes `create_*`, `get_*`, and `list_*` methods
for each contract, as well as the generic `create`, `get`, and `list` methods.
It is the bounded persistence boundary for future deterministic commands,
tools, TUI rendering, and evaluations; assistant code must not use raw SQL.

Large or detailed computed data remains in approved artifacts. The records
store artifact references and structured summaries, not raw prompts or
unredacted logs.

## Migration strategy

`run_migrations()` creates seven additive research-record tables with a stable
identifier, indexed query fields, and a structured JSON payload. The existing
`research_answer_audit` table is extended additively with `research_session_id`
and `missing_data_json`; legacy audit rows remain readable. All DDL uses
`CREATE TABLE IF NOT EXISTS` or `ADD COLUMN IF NOT EXISTS`, so repeated runs are
idempotent and do not alter existing research-command tables.

## Dependent engines

`deep-symbol-analysis-engine` consumes symbol levels and setup analyses.
`research-scenario-plan-engine` consumes symbol levels, setup analyses, market
regime, and sector context. `setup-historical-evidence-engine` produces setup
evidence. `symbol-knowledge-memory` consumes only validated persisted models
and their artifact references. Shortlist, evaluation, and repair workflows use
the shortlist and audit contracts for traceable handoff.
