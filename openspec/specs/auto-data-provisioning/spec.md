# Specification: Auto data provisioning for symbol analysis

## ADDED Requirements

### Requirement: System shall ensure data readiness before one-symbol analysis

OpenStock SHALL automatically check and provision required data artifacts before analysing a requested symbol.

#### Scenario: Candidate score exists and is fresh

- **GIVEN** `candidate_score(symbol, target_date)` exists
- **AND** supporting data freshness is sufficient
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL use the existing score without running sync/build/score actions
- **AND** SHALL return an ensure-data result with status `READY` and a cache-hit action.

#### Scenario: Candidate score is missing but features exist

- **GIVEN** `feature_snapshot(symbol, target_date)` exists
- **AND** `candidate_score(symbol, target_date)` is missing
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL generate a candidate score for that symbol/date
- **AND** then run the existing explain flow.

#### Scenario: Feature snapshot is missing but canonical data is sufficient

- **GIVEN** canonical OHLCV exists with sufficient history for the symbol
- **AND** `feature_snapshot(symbol, target_date)` is missing
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL build features for the symbol
- **AND** generate a candidate score
- **AND** then run the existing explain flow.

#### Scenario: Canonical data is missing

- **GIVEN** canonical OHLCV is missing or insufficient for the symbol
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL fetch symbol OHLCV from vnstock-service
- **AND** build canonical OHLCV for the symbol
- **AND** build features
- **AND** generate a candidate score
- **AND** then run the existing explain flow.

#### Scenario: Benchmark data is missing

- **GIVEN** the requested symbol has data
- **BUT** benchmark OHLCV is missing or insufficient
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL fetch benchmark OHLCV
- **AND** build benchmark canonical OHLCV
- **AND** build symbol features using the benchmark where available
- **AND** report benchmark freshness in the result.

---

### Requirement: Ensure-data result shall be explicit and user-visible

The system SHALL return an explicit data readiness result from provisioning.

#### Scenario: Ready result contains actions and freshness

- **GIVEN** ensure-data completes successfully
- **WHEN** the result is rendered
- **THEN** it SHALL include status, actions taken, cache hits, warnings, freshness, and lineage.

#### Scenario: Partial result is clear

- **GIVEN** some artifacts exist but analysis cannot be fully completed
- **WHEN** ensure-data returns `PARTIAL`
- **THEN** the user-facing result SHALL explain which artifact is missing or stale.

#### Scenario: Failed result is actionable

- **GIVEN** provisioning fails
- **WHEN** ensure-data returns `FAILED`
- **THEN** the user-facing result SHALL include the failure reason and suggested manual diagnostic command.

---

### Requirement: Auto provisioning shall be minimal by default

One-symbol analysis SHALL provision only the requested symbol and required benchmark by default.

#### Scenario: Explain one symbol does not refresh full universe

- **GIVEN** the user requests `/explain FPT`
- **WHEN** data is missing
- **THEN** the system SHALL NOT sync all active symbols by default
- **AND** SHALL fetch only FPT and required benchmark data.

#### Scenario: Existing fresh data is reused

- **GIVEN** required artifacts already exist and are fresh enough
- **WHEN** the user requests analysis
- **THEN** the system SHALL reuse existing artifacts.

---

### Requirement: Freshness policy shall be deterministic

Data readiness SHALL use a deterministic freshness and lookback policy.

#### Scenario: Target date is not a trading day

- **GIVEN** the target date has no trading bar
- **WHEN** canonical data has a bar before the target date
- **THEN** the system SHALL use the latest bar on or before the target date
- **AND** SHALL expose `as_of_bar_date`.

#### Scenario: Insufficient history remains after sync

- **GIVEN** symbol OHLCV is fetched
- **BUT** the row count remains below the minimum required bars
- **WHEN** ensure-data completes
- **THEN** the result SHALL be `PARTIAL` or `FAILED`
- **AND** SHALL include an insufficient-history warning.

---

### Requirement: `/explain` shall integrate ensure-data

The `/explain` command SHALL call ensure-data before reading candidate score artifacts.

#### Scenario: Missing data is provisioned for explain

- **GIVEN** no candidate score exists for `FPT` on the target date
- **WHEN** the user runs `/explain FPT`
- **THEN** the command SHALL run ensure-data
- **AND** produce the missing artifacts when vnstock-service supplies data
- **AND** return the normal explain result.

#### Scenario: Explain result includes data readiness panel

- **GIVEN** `/explain FPT` completes
- **WHEN** the result is rendered
- **THEN** it SHALL include a `Data Readiness` panel.

#### Scenario: Explain fails gracefully when provisioning fails

- **GIVEN** vnstock-service is unavailable
- **WHEN** `/explain FPT` runs and data is missing
- **THEN** the command SHALL return a clear failed result
- **AND** SHALL NOT crash.

---

### Requirement: `/compare` shall integrate ensure-data for all symbols

The `/compare` command SHALL ensure data for each requested symbol before comparison.

#### Scenario: Compare two symbols provisions both

- **GIVEN** the user runs `/compare FPT MWG`
- **WHEN** one or both candidate scores are missing
- **THEN** the system SHALL run ensure-data for each requested symbol
- **AND** then compare available candidate scores.

#### Scenario: Compare handles partial symbol failures

- **GIVEN** one symbol can be provisioned and another cannot
- **WHEN** comparison runs
- **THEN** the result SHALL include the ready symbol data and warning for the failed symbol
- **OR** SHALL fail if no symbols are ready.

---

### Requirement: Assistant path shall invoke deterministic ensure-data preconditions

Natural-language assistant flows SHALL ensure data before executing analysis read tools.

#### Scenario: Natural-language explain provisions data

- **GIVEN** the user asks to evaluate a symbol in natural language
- **WHEN** the intent is `explain_symbol`
- **THEN** the assistant execution path SHALL ensure data for that symbol before calling `candidate.explain`.

#### Scenario: Natural-language compare provisions data

- **GIVEN** the user asks to compare multiple symbols
- **WHEN** the intent is `compare_symbols`
- **THEN** the assistant execution path SHALL ensure data for all requested symbols before calling `candidate.compare`.

#### Scenario: LLM does not control provisioning decision

- **GIVEN** the assistant builds a plan
- **WHEN** data is missing
- **THEN** deterministic execution code SHALL decide whether to provision data
- **AND** the LLM SHALL NOT be responsible for selecting sync/build steps.

---

### Requirement: Ensure-data shall emit structured observability events

Every provisioning decision and action SHALL be observable through file-based logs.

#### Scenario: Ensure-data starts

- **GIVEN** ensure-data begins
- **WHEN** the workflow starts
- **THEN** a `DATA_ENSURE_STARTED` event SHALL be written.

#### Scenario: Cache hit is logged

- **GIVEN** all required data is available
- **WHEN** ensure-data skips provisioning
- **THEN** a `DATA_ENSURE_CACHE_HIT` event SHALL be written.

#### Scenario: Provisioning action succeeds

- **GIVEN** a sync/build/score action runs successfully
- **WHEN** it completes
- **THEN** a corresponding succeeded event SHALL be written.

#### Scenario: Provisioning action fails

- **GIVEN** a sync/build/score action fails
- **WHEN** the failure is caught
- **THEN** a corresponding failed event SHALL be written with error details.

#### Scenario: Final status is logged

- **GIVEN** ensure-data completes
- **WHEN** final status is known
- **THEN** one of `DATA_ENSURE_READY`, `DATA_ENSURE_PARTIAL`, or `DATA_ENSURE_FAILED` SHALL be written.

---

### Requirement: Ensure-data shall be idempotent and concurrency-safe

Provisioning SHALL avoid duplicate work when multiple requests target the same symbol/date.

#### Scenario: Duplicate request sees active lock

- **GIVEN** an ensure-data lock exists for the same symbol/date
- **WHEN** a second request starts
- **THEN** it SHALL wait briefly, reuse completed artifacts, or return a clear retry/partial message.

#### Scenario: Stale lock is handled

- **GIVEN** an ensure-data lock is stale
- **WHEN** a new request starts
- **THEN** the system SHALL replace the stale lock and continue.

#### Scenario: Lock is released

- **GIVEN** ensure-data exits by success or failure
- **WHEN** cleanup runs
- **THEN** the lock SHALL be released.

---

### Requirement: Auto provisioning shall be configurable

Operators SHALL be able to disable or tune auto provisioning.

#### Scenario: Auto sync disabled

- **GIVEN** auto sync is disabled by config or policy
- **WHEN** data is missing
- **THEN** ensure-data SHALL not fetch remote data
- **AND** SHALL return a clear result describing the missing artifact.

#### Scenario: Source override is supplied

- **GIVEN** a source/provider override is configured
- **WHEN** sync runs
- **THEN** the override SHALL be passed to vnstock-service client calls.

---

### Requirement: Documentation and validation shall be provided

The implementation SHALL include documentation and validation evidence.

#### Scenario: Documentation exists

- **GIVEN** the change is implemented
- **WHEN** docs are inspected
- **THEN** `vnalpha/docs/auto-data-provisioning.md` SHALL explain behavior, policy, failures, and manual fallback commands.

#### Scenario: Validation evidence exists

- **GIVEN** the implementation is complete
- **WHEN** the OpenSpec tasks are reviewed
- **THEN** validation evidence SHALL show tests, lint, and mocked end-to-end `/explain` auto provisioning.

---

### Requirement: OHLCV ingestion shall preserve truthful symbol and batch outcomes

OHLCV provisioning SHALL preserve typed `SUCCESS`, `EMPTY`, `FAILED`, `INVALID`, and `SKIPPED` outcomes for each requested symbol and SHALL derive the terminal batch status from those outcomes rather than row counts or warning text. A provider response whose quality status is `skipped` SHALL produce `SKIPPED`.

#### Scenario: Mixed symbol outcomes are partial

- **GIVEN** at least one required symbol succeeds
- **AND** another required symbol is empty, failed, or invalid
- **WHEN** the ingestion run finishes
- **THEN** the batch and persisted `ingestion_run.status` SHALL be `PARTIAL`
- **AND** the affected symbols and bounded remediation steps SHALL be user-visible.

#### Scenario: No required symbol completes

- **GIVEN** no required symbol succeeds or is explicitly already current
- **WHEN** the ingestion run finishes
- **THEN** the batch and persisted `ingestion_run.status` SHALL be `FAILED`
- **AND** valid empty responses SHALL remain distinguishable from provider failures and invalid data.

#### Scenario: Provider evidence is retained

- **GIVEN** vnstock-service supplies a quality report or diagnostics
- **WHEN** raw OHLCV rows and the ingestion terminal result are persisted
- **THEN** `quality_report_json` and `diagnostics_json` SHALL retain that sanitized evidence
- **AND** the run SHALL retain one correlation ID, exact terminal reason, counts, and per-symbol results.
