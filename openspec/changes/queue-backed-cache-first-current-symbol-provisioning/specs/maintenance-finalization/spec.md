## ADDED Requirements

### Requirement: A maintenance run SHALL freeze one session scope
A maintenance run SHALL persist one resolved session, validated universe snapshot and hash, exact symbol set, source-policy version, calendar version and expected normalized goal identities.

#### Scenario: Symbol reference data changes during acquisition
- **WHEN** the active symbol snapshot changes after a maintenance run begins
- **THEN** the running maintenance scope remains unchanged
- **AND** the new snapshot applies only to a later run.

### Requirement: Maintenance acquisition SHALL prepare canonical evidence only
The producer SHALL enqueue benchmark dataset-range work and equity `PRICE_ANALYSIS` goals.

#### Scenario: A maintenance run is submitted
- **WHEN** the run has a frozen universe
- **THEN** VNINDEX is represented by `SYNC_DATASET_RANGE(index.ohlcv)`
- **AND** each equity is represented by `ENSURE_CURRENT_SYMBOL(PRICE_ANALYSIS)`
- **AND** acquisition jobs do not build batch features, scores or watchlists.

### Requirement: Maintenance producer updates SHALL be recoverable across SQLite and DuckDB
The producer SHALL persist expected goal identities before queue submission and SHALL idempotently map returned queue job IDs in `maintenance_run_job`.

#### Scenario: Processing stops after some goals are submitted
- **WHEN** the producer resumes the same `ENQUEUING` run
- **THEN** it reuses existing mappings
- **AND** submits only missing expected goals
- **AND** transitions to `ACQUIRING` only when every expected goal is mapped.

### Requirement: Queue job identity SHALL be independent of maintenance-run membership
Queue job identity SHALL represent only normalized desired persisted state, while `maintenance_run_job` records run membership separately.

#### Scenario: Interactive and maintenance callers request equivalent work
- **WHEN** both callers request the same normalized desired state
- **THEN** they may reference the same queue job
- **AND** maintenance-run membership is stored in `maintenance_run_job`
- **AND** the queue job identity does not include one authoritative maintenance-run ID.

### Requirement: Session finalization SHALL be submitted only after acquisition is terminal
`maybe_submit_session_finalization()` SHALL submit or join a finalization job only after every expected acquisition goal is mapped to a terminal job.

#### Scenario: An expected acquisition job remains active
- **WHEN** `maybe_submit_session_finalization()` evaluates the run
- **THEN** no finalization job is submitted
- **AND** the run remains `ACQUIRING`.

#### Scenario: The final expected acquisition job becomes terminal
- **WHEN** every expected goal is mapped to a terminal job
- **THEN** the operation submits or joins one `FINALIZE_MARKET_SESSION` job
- **AND** transitions the run to `FINALIZATION_QUEUED`
- **AND** does not execute finalization inline.

### Requirement: Finalization SHALL use the frozen eligible universe
The finalizer SHALL NOT reacquire data or change the run universe.

#### Scenario: Finalization starts
- **WHEN** the finalization job is claimed
- **THEN** it reloads persisted acquisition evidence for the frozen run scope
- **AND** determines eligible coverage and exclusions from that evidence.

### Requirement: Session-wide derived artifacts SHALL be built once
One finalization attempt for a frozen session SHALL build each session-wide derived artifact at most once before dependent outcome and memory stages.

#### Scenario: Acquisition is complete
- **WHEN** finalization has an eligible universe
- **THEN** it builds features once for that universe
- **AND** builds score/watchlist once
- **AND** then builds market, sector and group context
- **AND** then matures outcomes and projects approved memory.

### Requirement: Final maintenance status SHALL be truthful
The finalizer SHALL persist `SUCCESS`, `PARTIAL` or `FAILED` from required-stage outcomes, coverage and exclusions without representing incomplete work as successful.

#### Scenario: Some symbols are excluded but minimum coverage is met
- **WHEN** required final stages succeed
- **AND** configured minimum coverage remains satisfied
- **THEN** the result is `PARTIAL`
- **AND** successful symbols, exclusions and reasons remain visible.

#### Scenario: Benchmark or minimum coverage is unavailable
- **WHEN** a required benchmark or configured minimum coverage is not satisfied
- **THEN** the result is `FAILED`
- **AND** no success status is recorded.

### Requirement: Finalization SHALL be idempotent and resumable
Finalization SHALL persist stage evidence sufficient to reuse completed deterministic work after interruption without duplicating artifacts.

#### Scenario: Finalization resumes after an interrupted stage
- **WHEN** deterministic stage output already exists for the same run and contract version
- **THEN** the finalizer reuses the existing output
- **AND** does not create duplicate artifacts.
