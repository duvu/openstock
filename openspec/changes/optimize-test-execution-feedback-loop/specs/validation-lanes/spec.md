## ADDED Requirements

### Requirement: Validation SHALL expose five distinct lanes
The repository SHALL provide consistency/spec, fast smoke, affected-domain, full regression and package/operational acceptance lanes with documented local, pull-request, nightly and release ownership.

#### Scenario: A normal application pull request is evaluated
- **WHEN** routing identifies a `vnalpha` application change
- **THEN** consistency, fast smoke and the owning affected-domain lane run
- **AND** unrelated package acceptance is deliberately skipped.

#### Scenario: A release is evaluated
- **WHEN** the release validation path runs
- **THEN** full regression and package/operational acceptance execute in addition to consistency.

### Requirement: Fast smoke SHALL be bounded and fail closed
The fast-smoke lane SHALL contain canonical H+1 cases for critical fail-closed behavior and one bounded R0 pipeline flow. Its measured local runtime SHALL be at most 60 seconds in the recorded environment or the remaining blocker SHALL stay explicitly incomplete.

#### Scenario: Critical smoke passes within budget
- **WHEN** the canonical local smoke command completes
- **THEN** it exits zero, reports every selected test and records a wall time no greater than 60 seconds.

#### Scenario: A smoke case fails
- **WHEN** any selected critical contract fails
- **THEN** the lane exits non-zero and preserves failure diagnostics.

### Requirement: Aggregate execution SHALL collect each test once
An aggregate lane SHALL resolve its selected manifests to one stable, deduplicated pytest invocation. Standalone R0 and R4 commands SHALL remain available but SHALL NOT run sequentially around a full suite that already includes their files. Each aggregate path SHALL invoke `openstock-verify --ci` at most once.

#### Scenario: Full aggregate validation is planned
- **WHEN** the aggregate execution plan is inspected
- **THEN** no pytest file appears more than once
- **AND** R0 and R4 files are collected through the full suite rather than separate sequential invocations.

#### Scenario: A duplicate path enters the aggregate plan
- **WHEN** the runner resolves overlapping selections
- **THEN** it deduplicates before execution and the consistency checker reports any manifest ownership conflict.

### Requirement: Required merge conclusions SHALL fail closed
The always-evaluated Required merge gate SHALL accept only `success` or a deliberate `skipped` conclusion for each fixed dependency. Failure, cancellation, timeout, action-required, neutral, startup failure, unknown or missing conclusions SHALL fail the gate.

#### Scenario: Docs-only runtime jobs are deliberately skipped
- **WHEN** consistency succeeds and runtime/package jobs conclude `skipped` by routing policy
- **THEN** the Required merge gate succeeds.

#### Scenario: A required job is cancelled
- **WHEN** any dependency concludes `cancelled`
- **THEN** the Required merge gate fails.

### Requirement: Validation evidence SHALL be environment-identical
Before/after collection, runtime, duplicate and migration measurements SHALL identify exact commits and the same OS, CPU, memory, Python, DuckDB, pytest and dependency environment. PR wall-time claims SHALL use equivalent runner evidence.

#### Scenario: A performance comparison is published
- **WHEN** final evidence claims improvement
- **THEN** it includes both exact commits, clean/dirty state, commands, counts, durations and matching environment identity.
