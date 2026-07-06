# Spec: Alpha Discovery TUI

## MODIFIED Requirements

### Requirement: Phase 5 shall provide an executable end-to-end deterministic alpha discovery workflow

The system SHALL provide a local-first workflow that starts from market data synchronization and ends with a daily watchlist visible in CLI and TUI.

#### Scenario: User runs the full local Phase 5 pipeline

Given a configured local DuckDB warehouse
And either a running local `vnstock-service` or a fixture data source
When the user runs:

```bash
vnalpha init
vnalpha sync symbols --universe VN30
vnalpha sync ohlcv --universe VN30
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
```

Then the system SHALL create or update these tables:

- `symbol_master`
- `market_ohlcv_raw`
- `canonical_ohlcv`
- `feature_snapshot`
- `candidate_score`
- `daily_watchlist`

And `vnalpha watchlist` SHALL render a non-error output from `daily_watchlist`.

#### Scenario: Pipeline handles empty or missing data explicitly

Given the warehouse has no usable OHLCV data
When the user runs `vnalpha build features` or `vnalpha score`
Then the command SHALL exit cleanly with an explicit message explaining that no usable source data exists
And the command SHALL NOT silently report success while producing no output.

### Requirement: CLI commands shall not be stubs

All Phase 5 CLI commands SHALL call real implementation modules or return an explicit unsupported-state error.

#### Scenario: Feature command executes real feature builder

Given canonical OHLCV rows exist
When the user runs `vnalpha build features`
Then the command SHALL calculate feature rows
And the command SHALL write rows into `feature_snapshot`
And the command output SHALL include the number of symbols processed.

#### Scenario: Score command executes real scoring pipeline

Given feature snapshot rows exist
When the user runs `vnalpha score`
Then the command SHALL calculate component scores and composite scores
And the command SHALL write rows into `candidate_score`
And the command SHALL write ranked rows into `daily_watchlist`.

#### Scenario: Watchlist command queries persisted watchlist

Given `daily_watchlist` rows exist
When the user runs `vnalpha watchlist`
Then the command SHALL query DuckDB
And the command SHALL render a Rich table containing symbol, score, candidate class, setup type, risk flags, and data quality status.

#### Scenario: TUI command launches the Textual app

Given `vnalpha` is installed
When the user runs `vnalpha tui`
Then the command SHALL launch `VnAlphaApp().run()`
And the app SHALL provide a watchlist screen backed by DuckDB queries.

### Requirement: Candidate classification shall use a stable ontology

The system SHALL distinguish final candidate priority from observed setup type.

#### Scenario: Candidate class uses canonical final priority labels

Given a symbol has a computed composite score
When the scoring pipeline maps the score to a final class
Then `candidate_class` SHALL be one of:

- `STRONG_CANDIDATE`
- `WATCH_CANDIDATE`
- `WEAK_CANDIDATE`
- `IGNORE`

And `candidate_class` SHALL NOT use setup labels such as `STAGE1`, `STAGE2`, `BREAKOUT`, `MOMENTUM`, or `MEAN_REVERT`.

#### Scenario: Setup type uses canonical setup labels

Given a symbol has computed feature values
When the scoring pipeline maps features to a setup label
Then `setup_type` SHALL be one of:

- `ACCUMULATION_BASE`
- `BREAKOUT_ATTEMPT`
- `MOMENTUM_CONTINUATION`
- `PULLBACK_TO_TREND`
- `MEAN_REVERSION`
- `UNCLASSIFIED`

### Requirement: Watchlist candidates shall include transparent evidence

Each generated watchlist candidate SHALL expose enough context for user review without implying an execution instruction.

#### Scenario: Watchlist row contains review evidence

Given a symbol is included in `daily_watchlist`
When the user views it in CLI or TUI
Then the row SHALL include:

- `symbol`
- `score`
- `candidate_class`
- `setup_type`
- evidence summary
- risk flags
- provider lineage
- data quality status

And the detail view SHALL include score breakdown.

#### Scenario: Candidate with poor data quality is flagged or rejected

Given a symbol has missing, duplicate, stale, or invalid data
When the scoring pipeline runs
Then the system SHALL either attach a risk flag to the symbol
Or place the symbol in `rejected_symbol`
And the reason SHALL be queryable in CLI or TUI.

### Requirement: Phase 5 shall remain research-only and non-execution-oriented

The system SHALL avoid capabilities that imply trading instruction, order placement, account access, or portfolio execution.

#### Scenario: Public surfaces avoid execution language

Given a user opens CLI help, TUI screens, docs, or generated watchlist output
Then public-facing text SHALL use research/watchlist/candidate language
And SHALL NOT instruct the user to place orders, manage brokerage accounts, or execute a portfolio.

#### Scenario: No brokerage execution path exists

Given Phase 5 is installed
When a user searches available commands or tools
Then no command SHALL place orders
And no command SHALL access brokerage account execution functions.

### Requirement: Phase 5 closure shall be test-backed

Phase 5 SHALL NOT be marked complete unless executable tests or validation commands prove the end-to-end workflow.

#### Scenario: Fixture-based end-to-end test passes

Given an isolated temporary DuckDB database
And fixture symbol and OHLCV data
When the test suite runs the Phase 5 pipeline
Then it SHALL create canonical data, feature snapshots, candidate scores, and daily watchlist rows
And it SHALL assert at least one non-`IGNORE` candidate exists
And it SHALL assert data-quality issues are flagged or rejected.

#### Scenario: OpenSpec tasks reflect verified state

Given a task is checked in `tasks.md`
When a reviewer inspects the repository
Then the task SHALL be backed by executable code, tests, or documented validation output
And unchecked or unverified implementation work SHALL remain unchecked.

## ADDED Requirements

### Requirement: Repository boundary shall be explicit before closure

The project SHALL define where `vnalpha` implementation code lives before Phase 5 is closed.

#### Scenario: `vnalpha` is a separate implementation repository

Given the intended boundary is:

```text
openstock = orchestration/source-of-truth roadmap/specs
vnstock   = data platform service
vnalpha   = research engine + TUI workspace
```

When Phase 5 implementation code is finalized
Then the implementation SHALL be committed to `duvu/vnalpha`
And `openstock` SHALL reference it through orchestration, docs, or submodule configuration.

#### Scenario: `vnalpha` is vendored under `openstock`

Given the project intentionally vendors `vnalpha` under `openstock/vnalpha`
When Phase 5 is closed
Then the roadmap SHALL explicitly document this boundary decision
And Makefile/test paths SHALL consistently use the vendored location.

### Requirement: MCP and LLM Gateway work shall be deferred from Phase 5 closure

Phase 5 closure SHALL NOT require MCP or LLM Gateway integration.

#### Scenario: User asks for natural-language research assistant capability

Given Phase 5 closure is focused on deterministic watchlist generation
When MCP or LLM Gateway capability is requested
Then the work SHALL be captured in a later change such as Phase 5.8 or Phase 5.9
And Phase 5 deterministic scoring SHALL remain independent of LLM-generated signals.
