# Spec: Alpha Discovery TUI MVP

## Purpose

Define the deterministic local alpha-discovery workflow and its research-only TUI.

## Requirements

### Requirement: openstock orchestrates the local research system

`openstock` SHALL provide a local workflow for running `vnstock-service`, executing `vnalpha` jobs, and opening the TUI.

#### Scenario: start vnstock service

Given a developer is in the `openstock` repository  
When they run `make up-vnstock`  
Then `vnstock-service` SHALL start locally.

#### Scenario: run daily pipeline commands

Given `vnstock-service` is available  
When the developer runs sync, feature, score, and TUI commands  
Then the system SHALL produce or display a daily watchlist.

---

### Requirement: vnalpha consumes vnstock-service only through HTTP

`vnalpha` SHALL consume market data through the `vnstock-service` HTTP contract and SHALL NOT embed provider-specific data access logic.

#### Scenario: fetch symbols

Given `vnstock-service` is configured  
When `vnalpha sync symbols` is executed  
Then `vnalpha` SHALL call the reference symbols endpoint and persist symbol metadata.

#### Scenario: fetch OHLCV

Given a configured universe  
When `vnalpha sync ohlcv` is executed  
Then `vnalpha` SHALL call the equity OHLCV endpoint for each symbol and preserve provider lineage.

#### Scenario: provider internals are not used

Given `vnalpha` needs market data  
When data is fetched  
Then `vnalpha` SHALL NOT import or instantiate provider-specific `vnstock` provider classes.

---

### Requirement: local research warehouse exists

`vnalpha` SHALL create and use a DuckDB-based research warehouse for Phase 5.

#### Scenario: initialize warehouse

Given a new local environment  
When `vnalpha init` is executed  
Then DuckDB tables SHALL be created for ingestion runs, symbols, raw OHLCV, canonical OHLCV, features, candidate scores, daily watchlists, and rejected symbols.

#### Scenario: raw lineage is preserved

Given an OHLCV response is received from `vnstock-service`  
When it is stored  
Then provider, quality status, diagnostics, fetched timestamp, and ingestion run ID SHALL be preserved.

#### Scenario: canonical OHLCV is reproducible

Given raw OHLCV exists  
When canonical build is executed for a date or range  
Then canonical OHLCV SHALL be reproducible and rejected rows SHALL include rejection reasons.

---

### Requirement: deterministic feature store v1

`vnalpha` SHALL compute deterministic features from canonical OHLCV only.

#### Scenario: compute price trend features

Given canonical OHLCV exists  
When feature build is executed  
Then MA20, MA50, MA100, and moving-average slopes SHALL be computed where enough history exists.

#### Scenario: compute volume and volatility features

Given canonical OHLCV exists  
When feature build is executed  
Then volume ratio, ATR14, and volatility features SHALL be computed where enough history exists.

#### Scenario: compute relative strength features

Given symbol OHLCV and benchmark OHLCV exist  
When feature build is executed  
Then relative strength features versus the configured benchmark SHALL be computed.

---

### Requirement: alpha scoring v1 produces research candidates

`vnalpha` SHALL score symbols deterministically and produce research candidate records.

#### Scenario: score candidate

Given feature snapshots exist  
When scoring is executed  
Then trend, relative strength, volume, base/compression, breakout proximity, and risk/data quality scores SHALL be computed.

#### Scenario: classify candidate

Given a score is computed  
When candidate class is assigned  
Then the class SHALL be one of STRONG_CANDIDATE, WATCH_CANDIDATE, WEAK_CANDIDATE, or IGNORE.

#### Scenario: evidence and risk flags are included

Given a candidate is generated  
When it is persisted  
Then evidence, risk flags, setup type, and lineage SHALL be stored with the score.

---

### Requirement: daily watchlist is generated

`vnalpha` SHALL generate a daily watchlist from candidate scores.

#### Scenario: generate watchlist

Given candidate scores exist for a date  
When `vnalpha watchlist --date <date>` is executed  
Then the system SHALL rank candidates and persist the daily watchlist.

#### Scenario: no candidate result is explicit

Given no symbol meets candidate criteria  
When a watchlist is generated  
Then the system SHALL return an explicit no-candidate result rather than failing silently.

---

### Requirement: TUI is the Phase 5 user interface

`vnalpha` SHALL provide a terminal user interface for the daily research workflow.

#### Scenario: open TUI

Given a local warehouse exists  
When `vnalpha tui` is executed  
Then a TUI SHALL open and show the daily watchlist or an explicit empty-state message.

#### Scenario: inspect candidate

Given a candidate is selected in the watchlist  
When the user presses Enter  
Then the TUI SHALL show symbol detail including score breakdown, evidence, risk flags, and lineage.

#### Scenario: inspect rejected symbols

Given symbols were rejected during filtering or scoring  
When the user opens the rejected-symbols screen  
Then the TUI SHALL show symbols and rejection reasons.

#### Scenario: inspect provider health

Given provider health data is available  
When the user opens the provider-health screen  
Then the TUI SHALL show provider and data-quality status.

---

### Requirement: research language boundary is enforced

The Phase 5 system SHALL use research/watchlist language only and SHALL NOT present outputs as trading instructions.

#### Scenario: candidate language is used

Given a watchlist item is displayed  
When the user reads the item  
Then the item SHALL use terms such as candidate, watchlist, monitor, setup, evidence, risk flag, and lineage.

#### Scenario: trading instruction language is forbidden

Given API, CLI, or TUI output is generated  
When user-facing text is checked  
Then it SHALL NOT include buy/sell/order/portfolio execution language.

---

### Requirement: Phase 5 prepares Phase 6 outcome tracking

Phase 5 SHALL persist enough identifiers and timestamps to support future outcome tracking.

#### Scenario: candidate has stable identity

Given a candidate is generated  
When it is persisted  
Then it SHALL have date, symbol, setup type, score, evidence, and lineage sufficient for later forward-return measurement.

#### Scenario: watchlist has stable ranking

Given a watchlist is generated  
When it is persisted  
Then rank, score, candidate class, and generated timestamp SHALL be stored.

---

**Clarified requirements (gap closure)**

### Requirement: date handling is deterministic

`vnalpha` CLI and TUI commands SHALL resolve dates via a shared `core.dates.resolve_date()` function.

#### Scenario: today keyword accepted

Given `--date today` is passed to any CLI command  
When the command executes  
Then `today` SHALL resolve to the current ISO date (YYYY-MM-DD).

This generic Phase 5 rule does not override the current-symbol research policy
in the natural-language research assistant specification. Deep assistant and
slash research surfaces SHALL resolve `today` to the latest configured Vietnam
market session so readiness can provision one consistent effective date.

#### Scenario: invalid date rejected

Given an invalid date string is passed to `--date`  
When the command executes  
Then a `ValueError` SHALL be raised with a clear message.

---

### Requirement: candidate_score is the authoritative score record

`candidate_score` SHALL be the single source of truth for scored research candidates.
`daily_watchlist` SHALL be derived from `candidate_score` and SHALL NOT recompute scores.

#### Scenario: daily_watchlist derives from candidate_score

Given `vnalpha score --date <date>` has been run  
When `vnalpha watchlist --date <date>` is executed  
Then the watchlist SHALL read from persisted `candidate_score` rows with no recomputation.

#### Scenario: IGNORE class excluded from watchlist

Given a symbol is scored as IGNORE  
When the daily watchlist is generated  
Then that symbol SHALL NOT appear in `daily_watchlist`.

---

### Requirement: TUI detail reads persisted candidate record

The TUI DetailScreen SHALL read the authoritative `candidate_score` record for (symbol, date).
It SHALL NOT recompute scores from `feature_snapshot`.

#### Scenario: persisted detail displayed

Given a candidate_score row exists for (symbol, date)  
When the user selects the symbol in the TUI  
Then the detail view SHALL display the persisted score, evidence, risk flags, and lineage.

#### Scenario: no persisted score shown as empty state

Given no candidate_score row exists for (symbol, date)  
When the user selects the symbol  
Then the detail view SHALL show an explicit "no persisted score" message with instructions.

---

### Requirement: scoring lineage includes audit metadata

Each `candidate_score` row SHALL include a `lineage_json` field with scoring version and generated timestamp.

#### Scenario: lineage fields are present

Given a score is persisted  
When `lineage_json` is read  
Then it SHALL contain `scoring_version` (e.g., `v1.0`) and `generated_at` (ISO timestamp).

---

**Modified requirements (Phase 5 hardening)**

### Requirement: Phase 5 pipeline shall be executable through documented commands

The system SHALL provide a consistent command contract across Makefile, CLI, roadmap, and runbook.

#### Scenario: User runs Makefile Phase 5 pipeline

Given `vnalpha` is installed
And the local warehouse is configured
When the user runs:

```bash
make sync
make features
make score
```

Then the commands SHALL call supported `vnalpha` CLI options
And the pipeline SHALL create or update `canonical_ohlcv`, `feature_snapshot`, `candidate_score`, and `daily_watchlist`.

#### Scenario: User syncs OHLCV by named universe

Given the user wants to sync VN30 OHLCV
When the user runs:

```bash
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
```

Then the CLI SHALL accept `--universe`
And the system SHALL resolve `VN30` to a concrete list of symbols
And the system SHALL sync OHLCV for those symbols.

#### Scenario: User syncs OHLCV by explicit symbols

Given the user wants to sync a custom list of symbols
When the user runs:

```bash
vnalpha sync ohlcv --symbols FPT,CMG,CTR --start 2024-01-01
```

Then the CLI SHALL use exactly the explicit symbol list
And explicit symbols SHALL take precedence over named universe resolution.

---

### Requirement: Phase 5 shall handle benchmark data explicitly

The system SHALL support benchmark OHLCV ingestion so relative strength features are not silently degraded.

#### Scenario: User syncs VNINDEX benchmark

Given a running `vnstock-service`
When the user runs a documented benchmark sync command such as:

```bash
vnalpha sync index --symbol VNINDEX --start 2024-01-01
```

Then the system SHALL call the index OHLCV data source
And SHALL persist benchmark rows into `market_ohlcv_raw`
And `vnalpha build canonical` SHALL promote benchmark rows into `canonical_ohlcv`.

#### Scenario: Feature builder has benchmark data

Given `canonical_ohlcv` contains symbol OHLCV rows
And `canonical_ohlcv` contains benchmark `VNINDEX` rows
When the user runs:

```bash
vnalpha build features --date 2024-06-30 --benchmark VNINDEX
```

Then the system SHALL compute relative strength fields
And `rs_20d_vs_vnindex` and `rs_60d_vs_vnindex` SHALL be non-null where sufficient history exists.

#### Scenario: Feature builder lacks benchmark data

Given symbol OHLCV rows exist
And benchmark OHLCV rows are missing
When the user runs `vnalpha build features`
Then the system SHALL warn or flag that benchmark data is missing
And the system SHALL NOT silently present relative strength as if it were computed.

---

### Requirement: Phase 5 watchlist review shall expose complete candidate evidence

The system SHALL expose all review-critical information for each watchlist candidate.

#### Scenario: User views watchlist from CLI

Given `daily_watchlist` rows exist for a date
When the user runs:

```bash
vnalpha watchlist --date 2024-06-30
```

Then the command SHALL render a research-oriented table
And the table or referenced detail command SHALL expose:

- rank
- symbol
- score
- candidate_class
- setup_type
- evidence
- risk flags
- provider/scoring lineage
- data quality status

#### Scenario: User opens symbol detail in TUI

Given a symbol is present in the daily watchlist
When the user opens the symbol detail screen
Then the screen SHALL show:

- score breakdown
- evidence summary
- risk flags
- lineage
- data quality status

And the detail screen SHALL read from persisted warehouse records, not recompute in-memory scores.

---

### Requirement: Phase 5 shall enforce canonical candidate ontology

The system SHALL persist only canonical Phase 5 values for candidate classes and setup types.

#### Scenario: Candidate score is persisted

Given the scoring engine has produced a score result
When the system persists a `candidate_score` row
Then `candidate_class` SHALL be one of:

- `STRONG_CANDIDATE`
- `WATCH_CANDIDATE`
- `WEAK_CANDIDATE`
- `IGNORE`

And `setup_type` SHALL be one of:

- `ACCUMULATION_BASE`
- `BREAKOUT_ATTEMPT`
- `MOMENTUM_CONTINUATION`
- `PULLBACK_TO_TREND`
- `MEAN_REVERSION`
- `UNCLASSIFIED`

#### Scenario: Legacy ontology value is produced

Given a legacy value such as `STAGE1`, `STAGE2`, `BREAKOUT`, `MOMENTUM`, `MEAN_REVERT`, `TREND_CONTINUATION`, `BASE_BREAKOUT_ATTEMPT`, `PULLBACK_TO_MA20`, or `RELATIVE_STRENGTH_LEADER`
When the system attempts to persist Phase 5 candidate output
Then the system SHALL reject it or map it to a canonical value before persistence.

---

### Requirement: Phase 5 TUI navigation shall support all required screens

The TUI SHALL provide working navigation for the minimum Phase 5 screens.

#### Scenario: User launches TUI

Given `vnalpha` is installed
When the user runs:

```bash
vnalpha tui --date 2024-06-30
```

Then the TUI SHALL launch successfully
And the initial screen SHALL display the daily watchlist or an explicit empty state.

#### Scenario: User opens required screens

Given the TUI is running
When the user invokes the home, watchlist, rejected-symbols, and data-quality actions
Then each action SHALL open a valid screen
And no action SHALL push an unregistered screen name.

#### Scenario: User drills into symbol detail

Given the watchlist screen contains at least one row
When the user selects a symbol
Then the TUI SHALL open the detail screen for that symbol and date.

---

### Requirement: Phase 5 shall have fixture-backed end-to-end tests

The project SHALL validate the Phase 5 pipeline without requiring external provider connectivity.

#### Scenario: CI runs fixture-backed Phase 5 pipeline

Given a temporary or in-memory DuckDB connection
And deterministic fixture OHLCV data for `VNINDEX`, a strong candidate, a weak candidate, and a poor-quality candidate
When the E2E test runs migrations, canonical build, feature build, scoring, and watchlist generation
Then the test SHALL assert:

- `canonical_ohlcv` contains rows
- `feature_snapshot` contains rows
- `candidate_score` contains rows
- `daily_watchlist` contains rows
- at least one candidate is not `IGNORE`
- poor-quality data is flagged or rejected
- benchmark-relative-strength fields are computed when benchmark data exists

---

### Requirement: Phase 5 shall remain research-only

The system SHALL expose research/watchlist/candidate language and SHALL NOT expose trading execution behavior.

#### Scenario: User inspects CLI and TUI public surfaces

Given the user views CLI help, TUI labels, watchlist output, or Phase 5 docs
Then the text SHALL frame outputs as research candidates or watchlist entries
And the text SHALL NOT instruct the user to buy, sell, place orders, or execute a portfolio.

#### Scenario: User searches available Phase 5 commands

Given Phase 5 is installed
When the user lists available commands
Then no command SHALL place orders
And no command SHALL manage brokerage accounts or portfolios.

### Requirement: Phase 5 dynamic terminal output shall remain inert

CLI and TUI renderers SHALL sanitize dynamic command, result, error, answer,
plan, and trace text before constructing final Rich or Textual renderables.

#### Scenario: Dynamic terminal text contains hostile controls

Given a dynamic value contains Rich markup, a credential, or an OSC sequence
When a current or legacy CLI/TUI surface renders the value
Then the credential and terminal controls SHALL be absent
And the remaining text SHALL NOT create an active style or hyperlink

---

**Added requirements (Phase 5 hardening)**

### Requirement: Phase 5 shall expose a rich watchlist query object

The system SHALL provide a repository-level query that returns complete watchlist review records.

#### Scenario: Application queries rich watchlist view

Given `daily_watchlist` and `candidate_score` rows exist for a date
When the application calls the rich watchlist query
Then each returned record SHALL include:

- rank
- symbol
- score
- candidate_class
- setup_type
- evidence_json
- risk_flags_json
- lineage_json
- data_quality_status

And CLI/TUI SHALL use this query or an equivalent service rather than duplicating SQL.

---

### Requirement: Phase 5 shall define universe resolution behavior

The system SHALL define how named universes are resolved.

#### Scenario: User requests VN30 universe

Given `VN30` is the minimum Phase 5 universe
When the user passes `--universe VN30`
Then the system SHALL resolve it deterministically
And the result SHALL be testable without external network access.

#### Scenario: User requests unsupported universe

Given a universe is not implemented
When the user passes that universe name
Then the system SHALL fail with a clear error message listing supported universes.
