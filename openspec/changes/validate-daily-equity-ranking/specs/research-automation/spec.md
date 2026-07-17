## ADDED Requirements

### Requirement: Research feature eligibility shall use production statuses

Research consumers SHALL parse the same versioned feature-data statuses emitted by
the production builder. Only exact-date rows SHALL be eligible; stale,
missing-benchmark, null, and unknown legacy statuses SHALL fail closed with typed
exclusion reasons.

#### Scenario: Production exact-date snapshot enters a study

- **WHEN** the production builder persists an `EXACT_DATE` feature snapshot
- **THEN** research eligibility SHALL accept the row under the shared contract
- **AND** lineage SHALL record the contract version.

#### Scenario: Unknown legacy status is encountered

- **WHEN** a persisted feature status is null or outside the production enum
- **THEN** the row SHALL remain queryable
- **AND** research consumers SHALL exclude it as `UNKNOWN_FEATURE_STATUS`.

### Requirement: Hypotheses shall measure later observations

A hypothesis SHALL treat event-time feature columns only as inputs and SHALL measure
the requested horizon from a separate complete later-observation record joined by
symbol and event date.

#### Scenario: Trailing feature differs from later outcome

- **WHEN** a selected feature row has a trailing return that differs from its
  complete candidate outcome
- **THEN** the hypothesis metric SHALL use the candidate outcome
- **AND** lineage SHALL identify the measurement source, status, horizon, join keys,
  and measurement contract version.

#### Scenario: Later observation is missing

- **WHEN** an otherwise eligible event has no complete later observation
- **THEN** it SHALL not enter the measured sample
- **AND** the missing observation SHALL remain explicit in metrics and caveats.

### Requirement: Ranking evaluation shall be point-in-time and reproducible

Every evaluation SHALL bind one universe snapshot, data snapshot, price basis,
feature version, scoring-policy hash, assumptions hash, observation contract, and
run manifest. Earlier evaluation SHALL not read later information.

#### Scenario: Held-out policy evaluation runs

- **WHEN** an operator evaluates a frozen scoring policy on held-out periods
- **THEN** the system SHALL use next-session observation semantics
- **AND** SHALL compare simple baselines under identical observations and exclusions.

### Requirement: Daily ranking evidence shall be immutable

The system SHALL keep finalized daily ranking batches, members, policies,
assumptions, reports, dataset experiments, and policy decisions immutable. Later
observations SHALL be separate append-only records.

#### Scenario: A finalized ranking matures

- **WHEN** a later 5, 10, 20, or 60-session observation becomes available
- **THEN** the system SHALL append or idempotently confirm the observation
- **AND** SHALL NOT rewrite the original ranking state.

### Requirement: Policy lifecycle decisions shall be reviewed

Scoring policies SHALL have an explicit `EXPERIMENTAL`, `ACCEPTED`, `REJECTED`, or
`RETIRED` decision backed by immutable evidence and a named reviewer. Policy
selection SHALL remain operator-controlled.

#### Scenario: A policy is accepted

- **WHEN** a reviewer accepts a policy with required reports and available later
  observations
- **THEN** the active pointer SHALL reference that immutable policy
- **AND** historical scores and rankings SHALL retain their original policy hashes.

### Requirement: The ranking vertical shall remain research-only

The system SHALL keep full-universe discovery, evaluation, reporting, dataset
experiments, and policy review free of broker, account, order, portfolio,
allocation, margin, transfer, or execution behavior.

#### Scenario: Ranking evidence is rendered

- **WHEN** CLI, TUI, artifact, or assistant output presents a shortlist or report
- **THEN** it SHALL present reproducible research evidence and caveats
- **AND** SHALL NOT claim guaranteed outcomes or autonomous trading action.
