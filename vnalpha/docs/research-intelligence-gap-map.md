# Research Intelligence Gap Map

## Scope statement

This document is a planning and gap assessment artifact for `vnalpha` research intelligence. It does not claim that any runtime capability described in the target model already exists. It does not introduce code, execution logic, or operational completion statements.

The purpose is to map the current end of day research workspace against the minimum capability needed for a stronger research intelligence layer. The focus is on grounded analysis workflows, data and schema readiness, assistant and TUI workflows, observability, and future OpenSpec decomposition.

This document is limited to research, watchlist, and scenario analysis workflows. It is not a runtime delivery report. It is not a trading system design. It does not authorize account actions, order routing, capital allocation, or any execution oriented behavior.

Planning assumptions:

- Current capabilities are grounded in the existing `vnalpha` codebase and docs.
- Future capabilities must remain deterministic where possible, auditable, and warehouse grounded.
- Assistant outputs must remain research only, conditional, caveated, and policy constrained.
- Any future implementation work should be split into focused OpenSpec changes instead of one large runtime initiative.

## Current capability inventory

### 1. Data ingestion

The current ingestion layer already covers the basic research warehouse feed for Vietnamese equity data through the `vnstock` client and DuckDB persistence.

Observed capabilities:

- `sync_symbols.py` fetches reference symbols from the `vnstock-service` compatible client and upserts symbol metadata into warehouse tables.
- `sync_ohlcv.py` fetches equity OHLCV per symbol, creates ingestion runs, and stores raw bars with provider and quality metadata.
- `sync_index.py` exists in the ingestion inventory and provides benchmark or index level synchronization needed for relative performance calculations.
- `build_canonical.py` promotes raw market data into canonical research ready OHLCV tables.
- Ingestion records source service, source endpoint, run identifiers, parameter payloads, and finish status.
- Current design is clearly end of day and batch oriented, not intraday or streaming.

Research meaning:

- The warehouse already has an auditable source of symbol and bar data.
- The ingestion layer is good enough to support research watchlists and derived features.
- The ingestion layer is not yet a complete research intelligence substrate because it does not directly persist market regime snapshots, sector context snapshots, support or resistance levels, or scenario plans.

### 2. Warehouse

The warehouse is DuckDB based and already has a meaningful research schema foundation.

Grounded components:

- `connection.py` manages DuckDB connectivity.
- `migrations.py` applies schema evolution.
- `schema.py` defines warehouse structures.
- `repositories.py` contains persistence and query access for core research workflows.

Confirmed warehouse tables and stores called out by current code and task context:

- `canonical_ohlcv`
- `feature_snapshot`
- `candidate_score`
- `daily_watchlist`
- assistant persistence through `assistant_repo`
- chat persistence through `chat_repo`
- session persistence through `session_repo`

Related session and tracing structures observed in code:

- `research_session`
- `tool_trace`
- `research_note`
- assistant session and LLM trace persistence referenced in assistant docs

Research meaning:

- The current warehouse is already more than a raw market data store.
- It supports data lineage, scored candidates, watchlists, notes, session history, and assistant traces.
- It still lacks dedicated schema support for deep analysis outputs, shortlist records, market regime snapshots, sector ranking snapshots, scenario plans, and evidence summaries.

### 3. Feature engineering

The feature layer is already capable of generating a daily technical and relative strength snapshot for symbols.

Current feature families:

- Price features: `close`, `ma20`, `ma50`, `ma100`, `ma20_slope`, `ma50_slope`
- Volume features: `volume_ma20`, `volume_ratio`
- Volatility features: `atr14`, `volatility_20d`, `base_range_30d`
- Relative strength features: `rs_20d_vs_vnindex`, `rs_60d_vs_vnindex`
- Distance and condition features: `distance_to_ma20`, `distance_to_52w_high`, `close_strength`
- Return windows observed in score input: `return_20d`, `return_60d`
- Lineage propagation from feature snapshot into candidate scoring

Research meaning:

- The existing feature set is enough for first pass trend, momentum, compression, and extension analysis.
- The feature set remains daily only and mostly symbol local.
- Breadth, sector rotation, multi timeframe structure, support or resistance level extraction, and historical setup evidence features are not yet first class.

### 4. Scoring and classification

The current scoring layer already converts feature snapshots into a structured candidate record.

Current composite score model:

- Composite score built from `trend_score`, `relative_strength_score`, `volume_score`, `base_score`, and `proximity_score`
- Rules mentioned in the task and reflected by current design include:
  - `price_above_ma20`
  - `price_above_ma50`
  - `ma20_above_ma50`
  - `ma50_above_ma100`
  - `positive_ma20_slope`
  - `near_52w_high`
  - `volume_expansion`
  - `close_near_high`
  - `base_compression`
- Risk flags are computed and persisted.
- `CandidateClass` currently includes:
  - `STRONG_CANDIDATE`
  - `WATCH_CANDIDATE`
  - `WEAK_CANDIDATE`
  - `IGNORE`
- `SetupType` currently includes:
  - `ACCUMULATION_BASE`
  - `BREAKOUT_ATTEMPT`
  - `MOMENTUM_CONTINUATION`
  - `PULLBACK_TO_TREND`
  - `MEAN_REVERSION`
  - `UNCLASSIFIED`
- Risk flags currently include values such as `THIN_VOLUME`, `HIGH_ATR`, `NEAR_RESISTANCE`, `OVERBOUGHT`, and `EXTENDED_FROM_MA`

Research meaning:

- The platform already has a deterministic candidate ranking core.
- Setup labeling exists, but setup quality is still shallow and primarily score driven.
- There is not yet a richer analysis object that separates setup quality, regime fit, level map, scenario conditions, and evidence confidence.

### 5. Watchlist generation

The watchlist pipeline is implemented and persisted.

Current watchlist workflow:

- `generate_watchlist.py` runs `score_universe()` on all symbols from `feature_snapshot`.
- `score_universe()` writes authoritative results to `candidate_score`.
- `save_watchlist()` reads persisted candidate rows and writes `daily_watchlist`.
- Watchlist defaults observed in code:
  - minimum score `0.40`
  - top `30`
- Watchlist eligible classes are `STRONG_CANDIDATE`, `WATCH_CANDIDATE`, and `WEAK_CANDIDATE`.
- Logging hooks already emit watchlist start, success, and failure events.

Research meaning:

- The project already produces a daily shortlist like artifact.
- The current output is a ranking and persistence layer, not yet a deep synthesis layer.
- There is no native watchlist clustering, near trigger grouping, extendedness bucket, or session focus synthesis yet.

### 6. Commands

The command layer is already present and registered through `setup.py`.

Current registered command surface:

- `/scan`
- `/filter`
- `/compare`
- `/explain`
- `/quality`
- `/lineage`
- `/note`
- `/history`
- `/help`

Research meaning:

- The command surface covers first generation candidate browsing and explanation.
- It does not yet cover deep analysis, market regime, sector strength, shortlist synthesis, scenario planning, or setup evidence retrieval.

### 7. Assistant architecture

The research assistant is already a structured, policy constrained layer on top of deterministic tools.

Observed assistant components:

- intent classifier
- planner
- executor
- synthesizer
- policy enforcement
- gateway LLM client

Current documented intents:

- `scan_candidates`
- `filter_candidates`
- `compare_symbols`
- `explain_symbol`
- `review_quality`
- `show_lineage`
- `summarize_watchlist`
- `create_research_note`
- `show_history`
- `fetch_data`
- `unsupported_or_unsafe`

Current assistant characteristics:

- Natural language prompts are classified into a bounded intent set.
- Plans are built deterministically and validated against a tool allowlist.
- The LLM has no direct warehouse or filesystem access.
- Synthesized outputs are meant to include basis, risks or caveats, and missing data disclosure.
- Refusal policy already blocks trading execution, unavailable tool requests, safety bypass attempts, and certainty seeking prompts.

Research meaning:

- The assistant foundation is strong for safe, warehouse grounded explanation.
- The current intent set is too small for deeper research intelligence workflows.
- Future intelligence should expand assistant planning, not bypass deterministic tools.

### 8. Local tool registry

The tool registry is already a concrete contract layer between the assistant and the warehouse.

Current allowlisted tool inventory:

- `watchlist.scan`
- `watchlist.filter`
- `candidate.explain`
- `candidate.compare`
- `quality.get_status`
- `quality.get_many_status`
- `lineage.get_symbol_lineage`
- `note.create`
- `history.list_sessions`
- `data.fetch`

Research meaning:

- The tool registry enforces bounded access and gives future research intelligence work a clear extension point.
- There are no current tools for deep symbol analysis, regime context, sector strength, shortlist generation, scenario planning, or setup evidence.

### 9. TUI

The TUI is already a real workspace, not just a thin command wrapper.

Current TUI foundation:

- Textual based application
- Screens: `home`, `watchlist`, `detail`, `command`, `outcomes`, `quality`, `log_viewer`, `assistant`, `rejected`
- Widgets: `composer_input`, `output_stream`, `score_table`, `risk_panel`, `chat_panel`, `command_input`, `command_result`, `status_bar`
- Input and routing helpers: `input_history`, `input_router`, `runtime_status`

Observed behavior:

- Users can navigate screens and ask assistant questions.
- Assistant screen supports free form questions, processing state, answer panel, and plan panel.
- Outcomes screen already renders candidate outcomes, score bucket performance, setup type performance, and risk flag performance.

Research meaning:

- The TUI already has the shell for a richer research workflow.
- It does not yet have dedicated deep analysis panels, shortlist synthesis views, scenario workflow states, or historical evidence drilldowns.

### 10. Observability

Observability is already unusually strong for a research workspace.

Current observability capabilities from code and docs:

- structured JSONL logging through `audit.py` and `logger.py`
- trace events through `trace.py`
- domain events for migration, sync, feature, scoring, watchlist, and outcome workflows
- deploy and repair CLI support
- retention handling
- redaction support
- context and summary capture
- bundle workflows
- error capture
- assistant and tool trace persistence

Research meaning:

- The platform can already support high quality audit trails for future intelligence features.
- Future research workflows need new event families and evaluation artifacts, not a new observability philosophy.

### 11. Outcomes and evaluation substrate

The system already includes an outcome evaluation layer.

Current outcome capabilities:

- outcome evaluator
- metrics
- calibration
- horizons
- aggregations
- repositories
- forward outcome tracking for scored candidates
- TUI outcomes screen for retrospective review

Research meaning:

- There is already a foundation for evidence based refinement.
- The evidence layer is not yet exposed as a first class assistant tool for setup specific historical context.
- Future research intelligence can build on this, but must create specific evidence contracts instead of vague references to outcomes.

### 12. Testing

The current codebase already has broad test coverage.

Current coverage areas, per task context:

- around 70 test files
- CLI
- commands
- assistant
- chat
- TUI
- observability
- scoring
- features
- ingestion
- data availability
- outcomes
- tools

Research meaning:

- The project already values deterministic verification.
- New research intelligence work should extend that pattern with golden sets, groundedness checks, policy checks, and scenario quality checks.

### 13. Data availability and readiness

The project already has automatic data provisioning controls.

Current modules called out in task context:

- `checks.py`
- `ensure.py`
- `lock.py`
- `policy.py`

Research meaning:

- The platform already knows how to verify and provision analysis prerequisites.
- Future deep analysis commands should integrate readiness checks instead of assuming all prerequisite datasets always exist.

### Summary of current capability

Today, `vnalpha` is already a serious end of day research workspace with:

- deterministic ingestion into DuckDB
- canonical OHLCV and feature snapshots
- candidate scoring and watchlist generation
- bounded command tools
- a policy constrained research assistant
- a Textual based research UI
- outcome tracking and observability

The main intelligence gap is not basic infrastructure. The gap is the next layer: deeper structured analysis objects, broader context features, richer assistant intents, stronger synthesis contracts, richer TUI research workflows, and evaluation artifacts tailored to research answers and scenario plans.

## Target capability model

The target capability model defines the minimum outputs that future research intelligence must produce. These are output contracts, not claims of current implementation.

### 1. Deep symbol analysis

Minimum output fields:

- `symbol`
- `as_of_date`
- `data_freshness`
- `lineage`
- `trend_context`
- `momentum_context`
- `relative_strength_context`
- `volume_context`
- `volatility_context`
- `setup_quality`
- `support_resistance_levels`
- `scenario_summary`
- `risks_caveats`
- `missing_data`
- `confidence`

Minimum semantic expectations:

- Trend context should describe current structure across available horizons, not just one moving average comparison.
- Momentum context should separate acceleration, persistence, and extendedness.
- Relative strength context should cover benchmark and sector context when available.
- Volume context should distinguish healthy confirmation from abnormal spikes or weak sponsorship.
- Volatility context should frame tradability and instability, in research language.
- Support and resistance levels should be explicit derived levels, not vague commentary.
- Scenario summary should remain conditional and research only.
- Confidence should reflect data completeness and evidence quality, not certainty about future outcome.

### 2. Market regime

Minimum output fields:

- `market_regime_state`
- `index_trend`
- `index_volatility`
- `breadth_metrics`
- `sector_strength_ranking`
- `symbol_sector_alignment`
- `risk_context`

Minimum semantic expectations:

- Regime state must be derived from persisted market data and feature logic.
- Breadth must include at least a few market wide participation indicators.
- Sector ranking must provide ordered relative context, not a binary good or bad label.
- Symbol sector alignment should say whether the symbol participates in a strong, neutral, or weak group.

### 3. Sector context

Minimum output fields:

- `sector_strength`
- `sector_rotation`
- `relative_performance`

Minimum semantic expectations:

- Sector strength should support both direct command access and inclusion in deep analysis.
- Sector rotation should indicate improving, weakening, or stable leadership state where data supports it.
- Relative performance should support benchmark relative and peer relative framing.

### 4. Watchlist synthesis

Minimum output fields:

- `watchlist_size`
- `class_distribution`
- `setup_distribution`
- `sector_clustering`
- `strongest_names`
- `near_trigger_names`
- `extended_names`
- `risk_flagged`
- `next_session_focus`

Minimum semantic expectations:

- The summary should synthesize the list as a portfolio of research situations, not just reprint ranks.
- Sector clustering should surface concentration risk and leadership pockets.
- Near trigger names should identify names that need confirmation rather than immediate action language.
- Next session focus should be a research agenda, not execution advice.

### 5. Shortlist generation

Minimum output fields:

- `rank`
- `symbol`
- `setup_type`
- `setup_quality`
- `shortlist_score`
- `why_shortlisted`
- `why_not_immediate`
- `data_status`
- `risk_context`
- `confirmation_conditions`
- `invalidation_conditions`

Minimum semantic expectations:

- The shortlist should be more selective than the broad watchlist.
- It should explain both inclusion and restraint.
- Confirmation and invalidation must be framed as research monitoring conditions.

### 6. Conditional research scenario

Minimum output fields:

- `symbol`
- `current_setup`
- `key_levels`
- `confirmation_conditions`
- `invalidation_conditions`
- `scenario_tree`
- `risk_reward_estimate`
- `checklist`
- `confidence`
- `caveats`
- `research_only_language`

Minimum semantic expectations:

- The scenario tree should cover at least a base case, failed confirmation case, and low quality drift case when data supports it.
- Risk or reward estimates must remain rough, level grounded, and caveated.
- The checklist should be evidence based, not a generic script.
- Every output must clearly stay within research only framing.

### 7. Historical evidence

Minimum output fields:

- `setup_type`
- `sample_size`
- `forward_return_distribution`
- `fae_aae_stats`
- `outcome_rate`
- `regime_split`
- `small_sample_caveat`

Minimum semantic expectations:

- Evidence must be tied to defined setup cohorts.
- Forward distributions should avoid overclaiming based on means alone.
- Regime split should show how context changes outcomes.
- Small sample caveats should be explicit and mandatory below a defined threshold.

### 8. Assistant workflow target

The assistant target model requires:

- expanded intent taxonomy for deeper research tasks
- new deterministic tools for each research object
- synthesis templates matched to each intent
- grounded validation before synthesis and before final answer release

### 9. TUI workflow target

The TUI target model requires:

- dedicated deep analysis panels
- shortlist panels
- scenario panels
- evidence panels
- long running status or progress feedback
- efficient keyboard workflows for drilldown, back, compare, save note, and route to assistant

## Formal gap matrix

| Capability | Current State | Target State | Gap | Priority | Future OpenSpec | Acceptance Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Deep symbol analysis | Current `/explain` and `candidate.explain` provide candidate level explanation, lineage, and quality can be queried separately | One consolidated deep analysis object with context blocks, levels, scenario summary, caveats, and confidence | No unified analysis contract, no explicit level map, no structured confidence model | P0 | `deep-symbol-analysis-engine` | Command and tool return complete deep analysis payload for known symbols with grounded missing data disclosure |
| Multi timeframe features | Daily features exist for MA, slopes, RS, ATR, distance, and volatility | Daily plus weekly or multi timeframe trend and momentum context | No weekly or higher timeframe persistence, no cross timeframe synthesis | P1 | `deep-symbol-analysis-engine` | Feature snapshot or derived tables expose multi timeframe fields used in analysis output |
| Support/resistance levels | Risk flags may imply resistance proximity but no first class level record exists | Explicit support and resistance level extraction with provenance | No schema, tool contract, or rendering for levels | P1 | `deep-symbol-analysis-engine` | Analysis output includes persisted levels with derivation metadata |
| Setup quality model | Setup type and candidate score exist | Dedicated setup quality object with evidence dimensions and confidence | Current score is broad ranking, not a decomposed setup quality model | P1 | `deep-symbol-analysis-engine` | Setup quality fields appear in analysis and shortlist outputs with deterministic scoring basis |
| Risk/reward estimate | Risks are present as flags, no explicit scenario estimate | Rough conditional risk or reward estimate linked to key levels | No level aware estimate engine or contract | P1 | `research-scenario-plan-engine` | Scenario output includes caveated estimate and invalidation linked to explicit levels |
| Market regime | Relative strength vs VNINDEX exists and index sync exists | Market regime snapshot with state, trend, volatility, breadth, sector ranking, risk context | No market regime snapshot schema, no breadth features, no command or tool | P0 | `market-regime-and-sector-context` | `/market-regime` and tool payload return persisted regime snapshot with freshness and caveats |
| Sector strength | Symbol metadata can include sector, but no research sector ranking layer exists | Ranked sector strength and rotation context | No sector snapshot table, no sector relative features, no assistant access | P0 | `market-regime-and-sector-context` | `/sector-strength` returns ranked sectors with methodology metadata |
| Watchlist synthesis | `daily_watchlist` persists ranked names, assistant can summarize at a basic level | Structured watchlist synthesis with distributions, clusters, extended names, and next session focus | No rich synthesis contract or deterministic aggregation tool | P0 | `watchlist-synthesis-and-shortlist` | `/watchlist-summary` and tool payload include class, setup, sector, and risk breakdowns |
| Shortlist generation | Watchlist exists, but no narrower shortlist artifact exists | Selective shortlist with reasons, restraints, conditions, and risk context | No shortlist schema, command, or scoring layer | P1 | `watchlist-synthesis-and-shortlist` | `/shortlist` creates ranked shortlist records and returns deterministic evidence blocks |
| Conditional research scenario planning | No dedicated scenario planning record or command exists | Scenario plan with key levels, conditions, scenario tree, checklist, and caveats | No scenario schema, tool, assistant intent, or policy tuned template | P1 | `research-scenario-plan-engine` | `/research-plan SYMBOL` returns conditional plan with research only wording and policy checks |
| Historical evidence | Outcome tracker and aggregates exist, TUI outcomes screen exists | Setup evidence lookup with sample size, distributions, FAE or AAE, regime split, caveats | No setup evidence contract or assistant intent | P1 | `setup-historical-evidence-engine` | `/setup-evidence` returns cohort evidence summary with small sample caveat logic |
| Assistant intents/tools | Assistant supports ten first generation intents and a bounded tool allowlist | Expanded intent taxonomy and tools for analysis, regime, sector, shortlist, scenario, evidence | Current planning surface does not cover richer research tasks | P0 | `assistant-research-intelligence-tools` | Intent classifier, plan builder, and tool allowlist support all new research workflows |
| TUI research workflow | TUI has screens for watchlist, quality, outcomes, assistant, and command results | Dedicated analysis, shortlist, scenario, evidence panels with keyboard drilldowns and progress states | No research focused multi panel workflow | P1 | `tui-research-workflow-polish` | TUI flows allow open analyze, open shortlist, open scenario, open evidence, back, and compare actions |
| Observability | JSONL logging, traces, domain events, retention, redaction, summary, bundle, and error capture already exist | Full event coverage for new research workflows with answer audit and evaluation hooks | Missing event families and audit records for deep research intelligence outputs | P2 | `assistant-research-intelligence-tools` | New event types and audit rows captured for each research workflow |
| Evaluation/golden sets | Tests exist broadly, outcomes exist, no research answer golden set suite called out | Golden sets and groundedness or policy checks for research outputs | Missing dedicated evaluation files and workflow | P2 | `assistant-research-intelligence-tools` | Golden sets run in CI and cover answer quality, policy safety, and scenario groundedness |
| Policy guardrails | Refusal policy already blocks trading execution, certainty, safety bypass, and unavailable tools | Explicit research scenario policy with allowed and disallowed output contracts | Current policy is strong but not yet specific to scenario planning and shortlist nuance | P0 | `assistant-research-intelligence-tools` | Policy tests prove allowed research outputs pass and execution style requests are refused |

## Data/schema gaps

Future research intelligence needs new persisted research objects. The current schema foundation is good, but these records are still missing or incomplete as first class entities.

### 1. Market regime snapshots

Need:

- `market_regime_snapshot` style table keyed by `as_of_date`
- fields for regime state, benchmark trend, benchmark volatility, breadth summary, freshness, lineage, and derivation version

Why it matters:

- Deep analysis and watchlist synthesis should not recompute regime context ad hoc inside every answer.
- Regime context should be auditable and reusable across commands, assistant, and TUI.

### 2. Sector strength snapshots

Need:

- `sector_strength_snapshot` style table keyed by `as_of_date` and sector
- ranking, relative performance windows, rotation state, breadth proxy if available, and methodology version

Why it matters:

- Sector context should be queryable as a persisted research object.
- It is needed for both global sector ranking and symbol sector alignment.

### 3. Symbol level snapshots

Need:

- `symbol_level_snapshot` or equivalent support and resistance table keyed by symbol and date
- derived support levels, resistance levels, source bars, strength score, and derivation metadata

Why it matters:

- Scenario plans and deep analysis need explicit key levels.
- Risk flags alone are not enough for level based research outputs.

### 4. Setup analysis records

Need:

- `setup_analysis` table or equivalent persisted object
- symbol, date, setup type, setup quality dimensions, trend context summary, volatility context summary, confidence, caveats, and lineage

Why it matters:

- Deep analysis needs a durable record that can be rendered, audited, and compared over time.

### 5. Shortlist candidate records

Need:

- `shortlist_candidate` table keyed by shortlist run and rank
- shortlist score, setup quality, reasons included, reasons restrained, risk context, confirmation, invalidation, and lineage

Why it matters:

- A shortlist is distinct from the broad watchlist and should be reproducible.

### 6. Research scenario plan records

Need:

- `research_scenario_plan` table keyed by symbol, date, and scenario plan id
- current setup, key levels, scenario tree, checklist, confidence, caveats, and policy classification fields

Why it matters:

- Scenario outputs should be inspectable and reviewable after generation.
- This is especially important for policy audits.

### 7. Setup historical evidence records

Need:

- `setup_evidence_snapshot` or equivalent cohort evidence table
- setup type, sample definition, horizon, sample size, return distribution stats, FAE or AAE stats, hit rates, regime split, and caveats

Why it matters:

- Evidence should be pre structured and reusable across assistant and TUI instead of embedded in prose.

### 8. Research answer audit records

Need:

- dedicated `research_answer_audit` style record or an extension of existing assistant traces
- requested intent, tools used, dataset freshness, groundedness result, policy result, and answer artifact references

Why it matters:

- Current assistant session and tool trace persistence is useful, but richer answer level audits will make evaluation easier.

## Feature engineering gaps

### 1. Weekly and multi timeframe features

Current state:

- Feature snapshot is daily oriented.

Gap:

- Need weekly and possibly mixed timeframe trend context, weekly moving averages, weekly range compression, and cross timeframe agreement signals.

Why it matters:

- Deep analysis quality is limited when all context comes from one timeframe.

### 2. Momentum window gaps

Current state:

- Current inputs include 20 day and 60 day return or RS windows.

Gap:

- Need multiple lookback periods that support short, medium, and intermediate context, such as 5 day, 10 day, 20 day, 40 day, 60 day, and 120 day style windows if justified.

Why it matters:

- Momentum persistence and acceleration cannot be judged reliably with only a couple of windows.

### 3. Drawdown and extendedness gaps

Current state:

- Distance to MA20 and distance to 52 week high exist.

Gap:

- Need richer extendedness metrics, drawdown from recent swing high, distance from multiple anchors, and normalized extension context.

Why it matters:

- Scenario planning and shortlist restraint require more than one extension proxy.

### 4. Base duration and base quality gaps

Current state:

- `base_range_30d` exists.

Gap:

- Need base duration, contraction progression, shakeout count, pivot density, range tightening progression, and other setup quality cues.

Why it matters:

- Setup classification exists, but setup quality is not deeply measured.

### 5. Support/resistance level gaps

Current state:

- There is no first class support or resistance feature family.

Gap:

- Need derived pivot or level features, breakout reference levels, support clusters, and nearby resistance maps.

Why it matters:

- Deep analysis and scenario plans depend on explicit level structures.

### 6. Breadth feature gaps

Current state:

- No market wide breadth feature family is called out in current capability inventory.

Gap:

- Need breadth measures such as advancing participation proxies, percent above moving averages, or similar market wide internal strength indicators compatible with available data.

Why it matters:

- Market regime quality is weak without participation context.

### 7. Sector relative feature gaps

Current state:

- Relative strength is currently measured against VNINDEX.

Gap:

- Need relative strength versus sector, sector trend rank, and sector rotation features.

Why it matters:

- A symbol can look strong versus the benchmark while lagging peers, or the reverse.

### 8. Setup outcome feature gaps

Current state:

- Outcomes are tracked, but setup scoring does not yet appear to use forward outcome evidence as a calibrated feature family.

Gap:

- Need calibrated historical evidence features or confidence modifiers derived from prior setup outcomes.

Why it matters:

- Shortlist and scenario confidence should eventually reflect empirical setup quality, not only static technical structure.

## Command/API gaps

The next research intelligence layer needs a larger command and tool surface. These are target contracts, not current features.

### 1. `/analyze SYMBOL`

Purpose:

- Return deep symbol analysis for a single symbol and date.

Minimum command output contract:

- symbol
- as of date
- freshness
- lineage
- trend context
- momentum context
- relative strength context
- volume context
- volatility context
- setup quality
- support or resistance levels
- risks and caveats
- missing data
- confidence
- research only scenario summary

Tool contract candidate:

- `analysis.deep_symbol`

### 2. `/market-regime`

Purpose:

- Return current market regime state for the selected date.

Minimum command output contract:

- regime state
- index trend
- index volatility
- breadth metrics
- sector ranking summary
- risk context
- freshness and lineage

Tool contract candidate:

- `context.market_regime`

### 3. `/sector-strength`

Purpose:

- Return ranked sector strength and rotation context.

Minimum command output contract:

- ranked sectors
- relative performance windows
- rotation labels
- strongest and weakest clusters
- methodology summary
- freshness and caveats

Tool contract candidate:

- `context.sector_strength`

### 4. `/watchlist-summary`

Purpose:

- Return deep watchlist synthesis for a date.

Minimum command output contract:

- watchlist size
- class distribution
- setup distribution
- sector clustering
- strongest names
- near trigger names
- extended names
- risk flagged names
- next session focus
- missing data or concentration caveats

Tool contract candidate:

- `watchlist.summarize_deep`

### 5. `/shortlist`

Purpose:

- Produce a narrower, richer shortlist from the broad watchlist.

Minimum command output contract:

- ranked shortlist rows
- setup quality
- shortlist score
- why shortlisted
- why not immediate
- data status
- risk context
- confirmation and invalidation conditions

Tool contract candidate:

- `watchlist.generate_shortlist`

### 6. `/research-plan SYMBOL`

Purpose:

- Produce a conditional research scenario plan for one symbol.

Minimum command output contract:

- current setup
- key levels
- confirmation conditions
- invalidation conditions
- scenario tree
- risk or reward estimate
- checklist
- confidence
- caveats
- research only framing banner

Tool contract candidate:

- `scenario.generate_plan`

### 7. `/setup-evidence`

Purpose:

- Return historical cohort evidence for a setup type or filtered setup family.

Minimum command output contract:

- setup definition
- sample size
- forward return distribution
- FAE or AAE stats
- outcome rate
- regime split
- small sample caveat

Tool contract candidate:

- `evidence.get_setup_history`

### 8. Shared API and tool output principles

All future commands and tools should:

- return structured JSON compatible payloads first
- include `as_of_date`
- include freshness and lineage when data is derived
- include `missing_data`
- include `confidence` only as evidence quality, never predictive certainty
- include `policy_classification` where scenario or shortlist semantics may be sensitive
- keep prose synthesis separate from deterministic payload fields

## Assistant intent/tool gaps

### 1. New required intents

The current intent set should be extended with these research specific intents:

- `deep_analyze_symbol`
- `review_market_regime`
- `review_sector_strength`
- `summarize_watchlist_deep`
- `generate_shortlist`
- `generate_research_scenario`
- `review_setup_evidence`

### 2. Required tools per intent

#### `deep_analyze_symbol`

Needs tools such as:

- `analysis.deep_symbol`
- `lineage.get_symbol_lineage`
- `quality.get_status`
- optionally `context.market_regime`
- optionally `context.sector_strength`

#### `review_market_regime`

Needs tools such as:

- `context.market_regime`
- optionally `context.sector_strength`

#### `review_sector_strength`

Needs tools such as:

- `context.sector_strength`
- optionally symbol metadata or peer linkage tools if the prompt mentions a symbol

#### `summarize_watchlist_deep`

Needs tools such as:

- `watchlist.summarize_deep`
- optionally `context.market_regime`
- optionally `context.sector_strength`

#### `generate_shortlist`

Needs tools such as:

- `watchlist.generate_shortlist`
- optionally `context.market_regime`
- optionally `quality.get_many_status`

#### `generate_research_scenario`

Needs tools such as:

- `scenario.generate_plan`
- `analysis.deep_symbol`
- optionally `evidence.get_setup_history`

#### `review_setup_evidence`

Needs tools such as:

- `evidence.get_setup_history`
- optionally `context.market_regime`

### 3. Synthesis template gaps

Current state:

- The assistant already synthesizes grounded answers, but templates are oriented around first generation watchlist and quality questions.

Gap:

- Each new intent needs a dedicated synthesis template that preserves structure and caveats.

Examples:

- Deep analysis template should always include setup summary, context blocks, levels, risk notes, and missing data.
- Market regime template should lead with state, then internal evidence, then caveats.
- Shortlist template should separate strongest research candidates from restraint reasons.
- Scenario template should visibly present conditional branches and a research only disclaimer.
- Evidence template should show sample quality before any performance summary.

### 4. Groundedness requirements

Future assistant workflows should enforce:

- every material claim maps to deterministic tool output fields
- no inferred support or resistance levels unless those levels exist in the payload
- no sector commentary without sector context data
- no regime commentary without market regime snapshot availability
- missing data must be surfaced explicitly, not silently omitted
- confidence is evidence quality only, never certainty
- answers should refuse or degrade gracefully when prerequisite datasets are missing

## TUI workflow gaps

### 1. Deep analysis rendering

Current state:

- Detail and assistant views exist, but there is no dedicated deep analysis panel contract.

Gap:

- Need multi section rendering for symbol overview, setup quality, trend, RS, volume, volatility, levels, caveats, and data freshness.

### 2. Shortlist rendering

Current state:

- Watchlist table exists, but no richer shortlist flow is called out.

Gap:

- Need shortlist specific panels that show rank, rationale, restraint, risk context, and drilldown into symbol analysis.

### 3. Scenario plan rendering

Current state:

- No dedicated scenario panel is described.

Gap:

- Need a clear scenario view with key levels, conditional branches, checklist, caveats, and policy framing.

### 4. Historical evidence rendering

Current state:

- Outcomes screen exists for retrospective review, but not setup evidence by request.

Gap:

- Need evidence panels showing cohort stats, distributions, regime splits, sample size, and small sample warnings.

### 5. Status and progress for long workflows

Current state:

- Assistant screen shows processing state.

Gap:

- Need richer progress states for multi step workflows such as loading regime context, generating shortlist, computing scenario plan, and retrieving evidence.

### 6. Keyboard workflow gaps

Need:

- fast open analyze on selected symbol
- open shortlist from watchlist screen
- open scenario plan from deep analysis view
- compare selected symbols without leaving context
- jump from assistant answer to structured panel
- save note from deep analysis or scenario panel
- predictable back and escape behavior across panels

## Observability/evaluation gaps

### 1. New event families

Current observability is strong, but future research intelligence needs explicit events for:

- deep analysis request started, completed, failed
- shortlist generation started, completed, failed
- scenario plan generation started, completed, failed
- setup evidence query started, completed, failed
- groundedness check passed or failed
- policy safety check passed or failed

### 2. Golden set files

Future evaluation should include at least these files:

- `research_answer_golden_set.jsonl`
- `shortlist_golden_set.jsonl`
- `scenario_plan_golden_set.jsonl`
- `policy_safety_golden_set.jsonl`

Purpose of each:

- `research_answer_golden_set.jsonl` checks deep analysis and contextual answer grounding.
- `shortlist_golden_set.jsonl` checks shortlist selection and restraint reasoning shape.
- `scenario_plan_golden_set.jsonl` checks conditional planning structure and research language.
- `policy_safety_golden_set.jsonl` checks allowed versus disallowed prompt boundaries.

### 3. Groundedness checks

Need:

- automated checks that answer fields only use deterministic payload evidence
- explicit failure when synthesis invents levels, sector ranking, regime state, or confidence basis not present in tool outputs
- answer annotations or audit summaries that record which evidence blocks were present

### 4. Policy safety checks

Need:

- tests that conditional research scenarios remain allowed
- tests that execution style prompts are refused
- tests that certainty claims are blocked or rewritten into caveated research framing
- tests that account specific or allocation prompts remain disallowed

### 5. Scenario quality checks

Need:

- checks for presence of confirmation and invalidation conditions
- checks for explicit caveats
- checks for research only wording
- checks for missing data disclosure
- checks for confidence semantics that stay within evidence quality framing

## Policy guardrail section

The future research intelligence layer should stay within the project principle that `vnalpha` is a research workspace, not an execution system.

### Allowed outputs

Allowed content, when grounded in persisted data and explicit methodology:

- conditional scenarios
- setup analysis
- key levels
- risk or reward estimates
- research checklists
- caveats
- confidence as evidence quality
- watchlist and shortlist synthesis
- historical setup evidence summaries
- market regime and sector context summaries

Constraints on allowed outputs:

- all statements must be data grounded
- all forward looking language must remain conditional
- all estimates must be caveated and methodology linked where possible
- all outputs must disclose missing data when it affects reliability

### Disallowed outputs

Disallowed content includes:

- account specific advice
- allocation instructions
- external platform actions
- certainty claims
- execution oriented commands

Concrete disallowed examples:

- telling a user how much capital to allocate
- instructing a user to place, modify, or cancel an order
- directing activity on a broker, exchange, or external platform
- claiming a symbol will definitely move in a direction
- converting research output into imperatives such as buy, sell, enter, or exit

### Guardrail design implications

Future assistant and command implementations should:

- separate research conditions from action language
- label scenario plans as research only
- refuse prompts that ask for account specific or execution oriented output
- downgrade certainty seeking prompts into caveated research framing where allowed, or refuse when the request remains unsafe

## Prioritised roadmap

The roadmap below is ordered by dependency and research usefulness.

### Phase 1, foundation for meaningful research intelligence

Priority: P0

Goals:

- define and persist market regime snapshots
- define and persist sector strength snapshots
- define deep symbol analysis output contract
- extend assistant intent taxonomy and tool allowlist
- extend policy rules for research scenario outputs

Dependencies:

- current warehouse and observability foundations
- existing quality and lineage tooling
- existing ingestion and feature pipeline

Reason:

- Without regime, sector, and deep analysis contracts, future research answers remain shallow and fragmented.

### Phase 2, shortlist and scenario planning reliability

Priority: P1

Goals:

- add support or resistance level features and persistence
- add richer setup quality model
- build shortlist generation records and command or tool
- build conditional research scenario plan records and command or tool
- integrate setup evidence lookups into analysis and scenario flows

Dependencies:

- Phase 1 contracts
- level derivation logic
- expanded feature families

Reason:

- Shortlist and scenario planning should not ship on top of vague level logic or undecomposed score outputs.

### Phase 3, evidence and workflow refinement

Priority: P2

Goals:

- expose setup historical evidence as first class command, tool, and TUI panel
- add groundedness audits and golden set evaluation suites
- add research answer audit records
- add richer watchlist synthesis aggregations
- improve TUI progress and panel interoperability

Dependencies:

- Phase 1 and Phase 2 runtime objects
- stable output contracts for evaluation

Reason:

- Once core workflows exist, quality control and evidence consistency become the main differentiator.

### Phase 4, polish and later enhancement

Priority: P3

Goals:

- additional convenience workflows
- richer keyboard navigation and saved workflow states
- expanded comparative analytics
- deeper calibration loops between outcomes and setup confidence

Dependencies:

- stable user facing research workflows

Reason:

- These are valuable, but not prerequisites for meaningful research intelligence.

### Dependency summary

The practical dependency order is:

1. regime and sector context
2. deep symbol analysis contract
3. support or resistance and setup quality model
4. shortlist generation
5. research scenario planning
6. setup evidence exposure
7. evaluation and workflow polish

## Future OpenSpec split

The full intelligence gap should be split into separate, focused OpenSpec changes.

### 1. `deep-symbol-analysis-engine`

Scope:

- deep symbol analysis contract
- support for multi block context assembly
- setup quality decomposition
- support or resistance level integration
- command and tool surface for `/analyze SYMBOL`

Out of scope:

- market regime and sector snapshot generation
- shortlist workflow
- scenario planning persistence

### 2. `market-regime-and-sector-context`

Scope:

- market regime snapshot schema
- sector strength snapshot schema
- breadth features
- sector relative features
- `/market-regime` and `/sector-strength` commands and tools

Out of scope:

- deep symbol analysis rendering details
- shortlist or scenario plan generation

### 3. `watchlist-synthesis-and-shortlist`

Scope:

- deep watchlist aggregation logic
- shortlist generation logic and persistence
- `/watchlist-summary` and `/shortlist` commands and tools
- sector clustering and risk clustering summaries

Out of scope:

- scenario planning
- historical evidence engine internals

### 4. `research-scenario-plan-engine`

Scope:

- scenario plan schema
- scenario generation contract
- key levels, confirmation, invalidation, checklist, and caveat rendering
- `/research-plan SYMBOL` command and tool
- policy constrained research only wording requirements

Out of scope:

- market regime snapshot generation
- broad watchlist aggregation

### 5. `setup-historical-evidence-engine`

Scope:

- setup evidence cohorts
- sample size rules
- return distribution and FAE or AAE summaries
- regime split evidence
- `/setup-evidence` command and tool

Out of scope:

- assistant intent expansion except where needed to expose the tool

### 6. `assistant-research-intelligence-tools`

Scope:

- new assistant intents
- plan builder updates
- tool allowlist updates
- synthesis templates
- grounded validation
- policy safety expansion
- golden set evaluation harness and answer audit integration

Out of scope:

- low level market regime feature computation
- TUI panel implementation details

### 7. `tui-research-workflow-polish`

Scope:

- deep analysis panels
- shortlist panels
- scenario panels
- evidence panels
- progress states
- keyboard workflow improvements

Out of scope:

- core feature engineering and warehouse derivation logic

## Closing synthesis

The codebase already delivers a substantial research workspace foundation. The missing piece is a richer intelligence layer that turns persisted data, features, scores, outcomes, and lineage into durable research objects that can be queried consistently across commands, assistant workflows, and the TUI.

The most important conclusion from this gap map is that future work should not start by asking the assistant to improvise deeper analysis. It should start by creating the missing deterministic substrates:

- persisted regime and sector context
- explicit level and setup quality records
- shortlist and scenario artifacts
- historical evidence contracts
- evaluation and policy checks tied to those artifacts

Once those substrates exist, the assistant and TUI can become deeper without becoming looser. That split keeps `vnalpha` aligned with its core principle: auditable, grounded, research first intelligence, not execution automation or certainty theater.
