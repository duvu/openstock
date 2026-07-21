## ADDED Requirements

### Requirement: One application SHALL own current-symbol orchestration
CLI, TUI, slash commands and assistant SHALL delegate to one `CurrentSymbolResearchApplication` that owns readiness, queue submit/join, wait behavior, capability selection and deterministic analysis.

#### Scenario: Deep analysis is planned
- **WHEN** the assistant classifies a current-symbol deep-analysis request
- **THEN** the plan contains one current-symbol application operation
- **AND** does not contain unconditional provisioning followed by analysis steps.

### Requirement: Queue waiting SHALL NOT hold a DuckDB connection

#### Scenario: A job remains active
- **WHEN** the application submits or joins a job and begins waiting
- **THEN** no DuckDB connection remains open during queue polling
- **AND** the application reopens the warehouse read-only only when needed.

### Requirement: Wait policies SHALL be explicit and shared
The system SHALL support `WAIT_UNTIL_TERMINAL`, `WAIT_UP_TO` and `DETACH` through one configuration and application service.

#### Scenario: Default interactive request
- **WHEN** CLI, TUI or chat submits a request without an explicit wait option
- **THEN** each surface uses the same configured bounded-wait default.

#### Scenario: Bounded wait expires
- **WHEN** `WAIT_UP_TO` reaches its timeout while the job remains active
- **THEN** the application returns `PENDING` with the job ID
- **AND** does not cancel the job
- **AND** does not execute deterministic analysis.

### Requirement: Protocol results SHALL be truthful
The application SHALL return exactly one of `READY`, `DEGRADED`, `ACCEPTED`, `PENDING`, `UNAVAILABLE` or `FAILED`.

#### Scenario: Minimum capability is not ready and detach is selected
- **WHEN** `PRICE_ANALYSIS` is not ready
- **AND** the request selects `DETACH`
- **THEN** the application returns `ACCEPTED` with the job ID
- **AND** returns no unsupported analysis.

#### Scenario: Terminal provisioning cannot produce valid price evidence
- **WHEN** the terminal job leaves `PRICE_ANALYSIS` unavailable
- **THEN** the application returns `UNAVAILABLE`
- **AND** includes exact missing, invalid or non-repairable evidence.

### Requirement: Capability fallback SHALL be deterministic
The LLM SHALL NOT choose the fallback capability.

#### Scenario: Ranking is unavailable but price analysis is ready
- **WHEN** the requested capability is `CANDIDATE_RANKING`
- **AND** valid price evidence is ready
- **THEN** the application returns `DEGRADED`
- **AND** sets the effective capability to `PRICE_ANALYSIS`.

### Requirement: Price-only output SHALL contain only supported claims

#### Scenario: Effective capability is price analysis
- **WHEN** a degraded price-only result is rendered
- **THEN** it may include price trend, return, volatility, drawdown, volume/liquidity, coverage, quality, gaps and lineage
- **AND** omits score, rank and unavailable benchmark-derived claims.

### Requirement: Shared jobs SHALL use administrative cancellation

#### Scenario: A user requests job cancellation
- **WHEN** `jobs cancel JOB_ID` targets an active shared job
- **THEN** the surface warns that cancellation can affect other callers
- **AND** the action is explicit rather than caused by timeout or disconnect.

### Requirement: Current-symbol results SHALL be consistent across surfaces

#### Scenario: Equivalent requests use CLI, TUI and chat
- **WHEN** the same inputs and persisted evidence are used
- **THEN** every surface returns the same protocol status, requested/effective capability, dates, job identity and limitations.
