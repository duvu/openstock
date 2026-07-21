# User and portfolio memory requirements

## ADDED Requirements

### Requirement: Explicit user preferences are separate from market evidence

The system SHALL store only explicit user preferences as preference records with source, effective date and update history. Preference data SHALL NOT be stored as market evidence, prediction truth or policy-performance labels.

#### Scenario: Explicit horizon preference is stored

- **GIVEN** a user explicitly states a preferred 10-to-20-session research horizon
- **WHEN** the preference is saved
- **THEN** it is recorded with source `EXPLICIT_USER`
- **AND** it may influence request defaults only within the configured product boundary

#### Scenario: Click behavior does not change risk tolerance

- **GIVEN** a user repeatedly watches volatile symbols
- **WHEN** preference processing runs
- **THEN** the system does not infer or increase risk tolerance
- **AND** any risk-profile change requires explicit confirmation

#### Scenario: Preference deletion preserves no hidden active copy

- **GIVEN** a deletable user preference
- **WHEN** the user removes it
- **THEN** it is no longer used for current request defaults
- **AND** retention follows the declared audit/privacy policy

### Requirement: User feedback is not outcome truth

User acceptance, rejection, watchlist actions and saved research SHALL remain distinct from realized market outcomes and model correctness.

#### Scenario: Accepted suggestion later underperforms

- **GIVEN** a user accepted or saved a suggestion
- **WHEN** the linked market outcome matures negatively
- **THEN** evaluation uses the realized outcome
- **AND** the prior acceptance is retained only as user feedback

### Requirement: Portfolio research artifacts are typed by provenance

The system SHALL distinguish at least:

```text
MODEL_TARGET
PAPER_PORTFOLIO
USER_SUPPLIED_SNAPSHOT
```

No portfolio research artifact SHALL imply broker execution or confirmed holdings without an explicit compatible source.

#### Scenario: Optimizer target remains a research scenario

- **GIVEN** an optimizer produces target weights
- **WHEN** the portfolio run is retained
- **THEN** it is labeled `MODEL_TARGET`
- **AND** the system does not represent the target as executed holdings

#### Scenario: Paper portfolio outcome is linked

- **GIVEN** a paper portfolio snapshot and later market data
- **WHEN** the evaluation horizon matures
- **THEN** a portfolio outcome may be linked with exact policy, weights, rebalance date and price basis
- **AND** it remains distinct from user-supplied or executed holdings

### Requirement: Portfolio evaluation supports attribution

When supported by available artifacts, portfolio evaluation SHALL separate attributable effects rather than reporting only total return.

Initial attribution categories MAY include:

```text
selection
weighting
sector exposure
risk control
turnover and estimated cost
```

#### Scenario: Missing attribution inputs remain explicit

- **GIVEN** a portfolio outcome lacks sufficient data for one attribution category
- **WHEN** evaluation is produced
- **THEN** the unavailable category is marked with a caveat
- **AND** the system does not allocate the unexplained result arbitrarily

### Requirement: Preference and portfolio data remain research-only

Preference and portfolio-memory surfaces SHALL NOT expose order placement, account mutation or autonomous rebalance execution.

#### Scenario: Rebalance request returns a scenario only

- **GIVEN** a user asks how a portfolio could be rebalanced
- **WHEN** the research application responds
- **THEN** it may return a typed research scenario with assumptions and costs
- **AND** it performs no broker or account action
