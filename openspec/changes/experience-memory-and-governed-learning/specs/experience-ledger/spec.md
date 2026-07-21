# Experience ledger requirements

## ADDED Requirements

### Requirement: Immutable research episodes

The system SHALL persist an immutable `research_episode` for each eligible completed deterministic research operation. It SHALL identify the normalized request, subjects, requested/effective date, requested/effective capability, enrichments, evidence snapshot, policy references, terminal result, limitations, artifact reference and correlation ID.

#### Scenario: Completed analysis creates one episode

- **GIVEN** a deterministic research operation returns `READY` or `DEGRADED`
- **WHEN** experience retention runs
- **THEN** one episode is persisted with exact evidence and policy references
- **AND** repeating retention for the same result creates no duplicate

#### Scenario: Pending request creates no prediction

- **GIVEN** a request returns `ACCEPTED` or `PENDING`
- **WHEN** the operational episode is retained
- **THEN** the episode records that no analysis was produced
- **AND** no market prediction is created

#### Scenario: Correction preserves history

- **GIVEN** an existing episode
- **WHEN** a later user correction is recorded
- **THEN** the original episode remains unchanged
- **AND** the correction is stored as linked feedback or a later episode

### Requirement: Explicit typed predictions

Predictions SHALL be created only from typed deterministic research artifacts. Initial prediction types SHALL be finite and versioned:

```text
CANDIDATE_SELECTION
BENCHMARK_OUTPERFORMANCE
RISK_WARNING
SETUP_CLASSIFICATION
PORTFOLIO_INCLUSION
```

#### Scenario: Candidate artifact emits a prediction

- **GIVEN** a candidate artifact with exact policy, horizon and evidence lineage
- **WHEN** its deterministic adapter runs
- **THEN** applicable prediction records reference the source episode, artifact and policy versions

#### Scenario: Narrative-only claim creates no prediction

- **GIVEN** an assistant narrative contains a claim absent from typed artifacts
- **WHEN** experience retention runs
- **THEN** no prediction record is created for that claim

### Requirement: Score is not probability

A raw score SHALL NOT be represented as a probability without a named accepted calibration artifact.

#### Scenario: Uncalibrated score remains a score

- **GIVEN** a candidate score of 85 and no accepted calibration
- **WHEN** a prediction is stored
- **THEN** the score may be retained
- **AND** no 85-percent success probability is recorded

### Requirement: User feedback is separate from market truth

The system SHALL store explicit typed feedback separately from outcomes. Initial types SHALL include `WATCH`, `IGNORE`, `SAVE_RESEARCH`, `USER_CORRECTION`, `PAPER_PORTFOLIO_ADD` and `PAPER_PORTFOLIO_REMOVE`.

#### Scenario: Watch action remains preference evidence

- **GIVEN** a user watches a symbol
- **WHEN** feedback is persisted
- **THEN** a `WATCH` event is stored
- **AND** it is not used as proof that a prediction was correct

### Requirement: Retained payloads are bounded

Episode, prediction and feedback payloads SHALL use typed size-bounded fields and SHALL exclude credentials and arbitrary execution instructions.

#### Scenario: Invalid payload is rejected

- **GIVEN** a payload violates the typed or size contract
- **WHEN** persistence is attempted
- **THEN** validation fails before writing
- **AND** the original research result remains unaffected
