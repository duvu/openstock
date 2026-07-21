# Governed learning requirements

## ADDED Requirements

### Requirement: Immutable learning candidates

The system SHALL persist each proposed improvement as an immutable `learning_candidate` linked to an exact parent policy/version, experiment specification, changed parameters and evaluation references.

Initial candidate types SHALL be finite:

```text
THRESHOLD_CHANGE
WEIGHT_CHANGE
CONSTRAINT_CHANGE
REGIME_RULE_CHANGE
```

#### Scenario: Explainable candidate is created

- **GIVEN** an evaluation identifies a bounded threshold or weight hypothesis
- **WHEN** a candidate is created
- **THEN** it records the exact parent version, proposed configuration delta, evidence references and rationale
- **AND** it does not mutate the parent policy

#### Scenario: Unsupported opaque candidate is rejected

- **GIVEN** a proposal lacks an explicit parent, parameter delta or reproducible experiment specification
- **WHEN** persistence is attempted
- **THEN** the candidate is rejected before entering the review lifecycle

### Requirement: Versioned policy lifecycle

The system SHALL maintain immutable policy versions with the following states:

```text
DRAFT
EXPERIMENTAL
ACCEPTED
RETIRED
REJECTED
```

Allowed transitions SHALL be explicit and validated.

#### Scenario: Draft becomes experimental

- **GIVEN** a valid draft policy version and bounded experiment specification
- **WHEN** an authorized review starts a challenger evaluation
- **THEN** the version may transition to `EXPERIMENTAL`
- **AND** the current accepted policy remains unchanged

#### Scenario: Invalid transition fails closed

- **GIVEN** a rejected or retired version
- **WHEN** a direct transition to `ACCEPTED` is attempted without a valid path
- **THEN** the transition fails
- **AND** no policy state changes

### Requirement: Promotion requires reproducible evidence and approval

A policy SHALL NOT become `ACCEPTED` without:

- exact replay/walk-forward or equivalent bounded validation references;
- champion–challenger comparison against the active accepted version;
- sample-size and cost caveats;
- explicit approval reference.

#### Scenario: Evidence-complete promotion

- **GIVEN** an experimental challenger has reproducible validation and explicit approval
- **WHEN** promotion is executed
- **THEN** a new immutable accepted version becomes active at its effective date
- **AND** the prior accepted version is retained and retired or bounded by effective dates

#### Scenario: Missing approval blocks promotion

- **GIVEN** a challenger has favorable evaluation but no approval reference
- **WHEN** promotion is attempted
- **THEN** promotion fails
- **AND** the existing accepted policy remains active

#### Scenario: Insufficient sample blocks superiority claim

- **GIVEN** challenger metrics are based on insufficient evidence
- **WHEN** comparison is generated
- **THEN** the report marks the evidence insufficient
- **AND** it cannot satisfy the promotion gate

### Requirement: No autonomous policy mutation

Evaluation services, LLM components and maintenance jobs SHALL NOT directly change accepted policy parameters or promote policy versions.

#### Scenario: LLM hypothesis remains non-authoritative

- **GIVEN** an LLM proposes a parameter adjustment
- **WHEN** the proposal is retained
- **THEN** it may create only a draft learning candidate with explicit experiment requirements
- **AND** no accepted runtime policy changes

### Requirement: Rollback preserves lineage

Rollback SHALL restore a prior approved configuration through an explicit governed transition/reference while preserving all intervening versions, evaluations and reasons.

#### Scenario: Accepted version is rolled back

- **GIVEN** a newly accepted version shows a material operational or evaluation problem
- **WHEN** an authorized rollback is executed
- **THEN** the selected prior approved configuration becomes effective through a recorded transition
- **AND** the problematic version, its evidence and rollback reason remain queryable

### Requirement: Adverse evidence is retained

The learning subsystem SHALL preserve failed experiments, adverse slices and rejection reasons. It SHALL NOT compact them out of governance history merely because a later policy performs better.

#### Scenario: Rejected challenger remains auditable

- **GIVEN** a challenger is rejected after poor cost-adjusted or regime-specific performance
- **WHEN** later evaluations are run
- **THEN** the rejected candidate and its evaluation remain available for audit and duplicate-hypothesis detection
