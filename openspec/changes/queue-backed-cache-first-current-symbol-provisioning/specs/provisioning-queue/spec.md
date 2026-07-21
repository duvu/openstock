## ADDED Requirements

### Requirement: Queue goals SHALL be finite and versioned
The queue SHALL accept only `ENSURE_CURRENT_SYMBOL`, `SYNC_DATASET_RANGE` and `FINALIZE_MARKET_SESSION` payloads defined by explicit schema versions.

#### Scenario: An unknown goal or enrichment is submitted
- **WHEN** a payload contains an unknown goal, enrichment or schema version
- **THEN** submission fails before persistence
- **AND** no provider or DuckDB work occurs.

### Requirement: Equivalent active goals SHALL join one job
The queue SHALL derive identity from every normalized field that changes desired persisted state.

#### Scenario: An interactive request joins queued maintenance work
- **WHEN** an equivalent active job already exists at lower priority
- **THEN** the request receives the same job ID
- **AND** the queued priority becomes the maximum existing or incoming priority
- **AND** no duplicate job is created.

### Requirement: SQLite operation SHALL be explicit and bounded
The queue SHALL use WAL mode, a bounded busy timeout, foreign keys, documented synchronous behavior, short transactions and size-bounded payloads/results.

#### Scenario: Submit and claim occur concurrently
- **WHEN** one client submits while the worker claims or another client reads status
- **THEN** operations follow the configured busy-timeout policy
- **AND** no external or DuckDB work runs inside the SQLite transaction.

### Requirement: The provisioner SHALL execute one job at a time
The supported runtime SHALL run one sequential worker with an explicit handler registry.

#### Scenario: A goal has no registered handler
- **WHEN** the worker claims a valid goal whose production handler is not registered
- **THEN** the job terminates with `UNSUPPORTED_GOAL_HANDLER`
- **AND** performs no provider or DuckDB work.

### Requirement: Worker delivery SHALL be at-least-once with idempotent effects
A retry after process interruption SHALL re-read persisted evidence and SHALL NOT duplicate persisted artifacts.

#### Scenario: DuckDB work completed before queue completion was recorded
- **WHEN** the worker resumes the job after lease recovery
- **THEN** re-planning detects the persisted effect
- **AND** the job records reuse instead of repeating the effect.

### Requirement: Worker stages SHALL be bounded
Every provider, build or finalization stage SHALL have a configured timeout compatible with the job lease.

#### Scenario: A long bounded stage begins
- **WHEN** the current lease does not cover the allowed stage duration plus safety margin
- **THEN** the worker extends the lease before the stage
- **AND** heartbeats at safe boundaries.

### Requirement: Worker stop behavior SHALL preserve recoverability

#### Scenario: The provisioner receives a stop request
- **WHEN** the worker is running a job
- **THEN** it stops claiming new jobs
- **AND** finishes or rolls back at a safe transaction boundary
- **AND** leaves recoverable lease and job state.

### Requirement: Ready same-date requests SHALL avoid queue work

#### Scenario: Required evidence is already ready
- **WHEN** readiness reports the requested capability ready
- **THEN** the caller creates no job
- **AND** performs no provider or build action.

### Requirement: Provisioning SHALL acquire only bounded missing data

#### Scenario: One new market session is missing
- **WHEN** persisted OHLCV coverage ends at the preceding session
- **THEN** the job requests only the missing session range
- **AND** canonical promotion processes only the affected range.

### Requirement: Action execution SHALL stop dependent work after failure

#### Scenario: A required upstream action fails
- **WHEN** an action fails its execution or postcondition
- **THEN** dependent actions are not invoked
- **AND** they are recorded as `BLOCKED`
- **AND** the original failure remains primary evidence.
