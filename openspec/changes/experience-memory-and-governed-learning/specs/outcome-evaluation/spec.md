# Outcome linkage and evaluation requirements

## ADDED Requirements

### Requirement: Deterministic prediction-to-outcome linkage

The system SHALL link a prediction to a matured outcome only when subject, as-of date, horizon, benchmark, policy and evidence lineage match the prediction contract.

#### Scenario: Exact candidate outcome link

- **GIVEN** a candidate prediction and a matured candidate outcome with matching subject, date, horizon, benchmark and lineage
- **WHEN** the outcome linker runs
- **THEN** one idempotent link is persisted
- **AND** the original prediction and outcome remain immutable

#### Scenario: Ambiguous outcome remains unlinked

- **GIVEN** more than one plausible outcome or incomplete matching fields
- **WHEN** linkage is attempted
- **THEN** no link is selected
- **AND** a stable ambiguity or missing-lineage reason is recorded

#### Scenario: Revised source outcome preserves history

- **GIVEN** a linked outcome is later invalidated or superseded
- **WHEN** linkage is rebuilt
- **THEN** the prior link history is retained
- **AND** a new link revision references the corrected outcome when eligible

### Requirement: Immutable evaluation runs

The system SHALL persist an immutable `evaluation_run` identified by as-of date, policy/version, prediction type, windows, universe hash, evaluation method and cost model.

#### Scenario: Repeated identical evaluation is idempotent

- **GIVEN** unchanged inputs and method versions
- **WHEN** the same evaluation is requested again
- **THEN** the existing equivalent evaluation is reused or deterministically deduplicated

#### Scenario: Method change creates a new run

- **GIVEN** the evaluation method or cost model version changes
- **WHEN** evaluation runs
- **THEN** a new immutable evaluation record is created
- **AND** the prior run remains queryable

### Requirement: Evaluation exposes evidence quality

Every evaluation SHALL expose sample counts, coverage, missing-data caveats and slice eligibility together with performance metrics.

Initial metrics SHALL include:

```text
count and coverage
directional hit rate
mean and median realized return
mean and median excess return
maximum drawdown
maximum favorable excursion
calibration buckets
turnover and cost-adjusted result when applicable
```

#### Scenario: Insufficient sample fails closed

- **GIVEN** a policy/setup/regime slice has fewer observations than the configured minimum
- **WHEN** comparison is requested
- **THEN** the slice is reported as `INSUFFICIENT_SAMPLE`
- **AND** the system does not claim superiority from that slice

### Requirement: Point-in-time evaluation

Historical evaluation SHALL use only evidence, policy versions, universe membership and outcome observations available under the evaluation cutoff.

#### Scenario: Future policy is excluded

- **GIVEN** a later policy version exists after the evaluated period
- **WHEN** a historical evaluation is reconstructed
- **THEN** the later policy version is excluded

#### Scenario: Future outcome is excluded

- **GIVEN** a prediction horizon had not matured by the evaluation cutoff
- **WHEN** the evaluation is built
- **THEN** the prediction remains pending or excluded with reason
- **AND** later realized data does not leak into the earlier evaluation

### Requirement: Regime and drift diagnostics

The system SHALL support bounded evaluation slices by policy, setup, regime, sector, horizon and configured score/confidence buckets. It SHALL compare current evidence with a named prior accepted window to report drift.

#### Scenario: Drift is reported, not automatically acted upon

- **GIVEN** a material decline in calibration or cost-adjusted performance
- **WHEN** drift diagnostics run
- **THEN** the evaluation records the affected metrics and slices
- **AND** no accepted policy is changed automatically
