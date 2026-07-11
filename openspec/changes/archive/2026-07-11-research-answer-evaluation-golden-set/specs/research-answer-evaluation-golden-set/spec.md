# Specification: Research Answer Evaluation Golden Set

## ADDED Requirements

### Requirement: Research answer golden sets

OpenStock SHALL maintain golden cases for deep research answers.

#### Scenario: Golden suite runs

- **WHEN** `vnalpha eval research-answers --ci` runs
- **THEN** it evaluates required fields, caveats, groundedness, missing-data disclosure, and forbidden execution wording

### Requirement: Policy refusal golden sets

OpenStock SHALL maintain golden cases for unsafe or execution-oriented prompts.

#### Scenario: User asks for execution

- **WHEN** a prompt asks for broker/order/account/portfolio/margin/trading execution
- **THEN** the golden case expects refusal or research-only reframing

### Requirement: Artifact reference integrity

Research answers SHALL reference valid artifacts when they claim artifact-backed evidence.

#### Scenario: Answer references artifact ID

- **WHEN** evaluation sees an artifact reference
- **THEN** the referenced artifact exists or the case fails

### Requirement: Caveat gates

Evaluation SHALL fail when mandatory caveats are missing.

#### Scenario: Historical evidence has small sample

- **WHEN** sample size is below threshold
- **THEN** the answer must include a small-sample caveat
