# Spec: Alpha Discovery TUI

## MODIFIED Requirements

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

## ADDED Requirements

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
