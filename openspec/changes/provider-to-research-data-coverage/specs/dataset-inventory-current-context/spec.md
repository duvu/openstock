## ADDED Requirements

### Requirement: Dataset support SHALL be represented truthfully
The repository SHALL maintain one machine-readable inventory that distinguishes contract, route, provider, quality, client, persistence, consumer, point-in-time, license and queue status.

#### Scenario: A contract exists without runtime delivery
- **WHEN** a dataset contract is registered but no verified provider and service route can deliver it
- **THEN** the inventory reports the contract separately from runtime availability
- **AND** documentation does not present the dataset as production-available.

### Requirement: Route, contract and provider declarations SHALL remain consistent
Canonical routes and provider capability declarations SHALL resolve only to a registered inventory dataset.

#### Scenario: A service route references an unsupported dataset
- **WHEN** a route has no registered contract or actual provider handler
- **THEN** repository consistency validation fails.

#### Scenario: Unsupported fund holdings route is evaluated
- **WHEN** no approved fund-research consumer and provider contract exist
- **THEN** the unsupported route is removed
- **AND** no placeholder fund warehouse is created.

### Requirement: Queue mappings SHALL use finite approved goals
Dataset queue mappings SHALL name only the approved goal and enrichment vocabulary.

#### Scenario: A dataset declares queued acquisition
- **WHEN** the inventory contains a queue mapping
- **THEN** it references a goal or enrichment defined by the queue-runtime specification
- **AND** no dataset defines a private job payload.

### Requirement: Company context SHALL remain current-state evidence
Company-context observations without verified temporal evidence SHALL be treated as current snapshots.

#### Scenario: Company information is persisted
- **WHEN** a provider returns canonical company information
- **THEN** `vnalpha` stores provider, observed time and content hash in an idempotent snapshot revision
- **AND** labels fields without verified effective dates as current-only.

#### Scenario: Historical research requests company context
- **WHEN** only a current company snapshot exists
- **THEN** historical consumers do not treat current shares or industry fields as historical facts.

### Requirement: Company context SHALL be optional
Unavailable company context SHALL not alter existing price or ranking readiness.

#### Scenario: Company information is unavailable
- **WHEN** price or ranking analysis has valid required evidence
- **AND** company information is empty, unsupported or unavailable
- **THEN** the existing analysis remains ready
- **AND** the optional limitation is disclosed.

### Requirement: Quote and intraday data SHALL produce a bounded session summary
Current-session observations SHALL be reduced to one bounded, versioned per-symbol summary.

#### Scenario: Quote and trade observations are available
- **WHEN** current-session data is requested
- **THEN** the consumer may calculate last/close, observed time, volume, high/low, trade count, matched volume and simple VWAP
- **AND** persists only a bounded versioned session summary.

### Requirement: The system SHALL NOT create an unbounded tick warehouse
Repeated intraday observations SHALL not create an unbounded raw-trade warehouse.

#### Scenario: Repeated intraday observations are ingested
- **WHEN** provider content changes during a session
- **THEN** the system stores bounded summary revisions
- **AND** does not persist every trade indefinitely in the research warehouse.

### Requirement: Current-session outcomes SHALL remain typed
Valid empty, stale, unsupported and failed current-session observations SHALL remain distinguishable states.

#### Scenario: The market is closed and provider response is valid empty
- **WHEN** no current trades are expected
- **THEN** the result is distinct from stale data, unsupported provider and provider failure.

### Requirement: Foreign-flow support SHALL be end-to-end or explicitly unavailable
Foreign-flow support SHALL be advertised only after its verified provider, route and consumer chain exists.

#### Scenario: Foreign flow remains contract-only
- **WHEN** no verified provider, route and consumer have been delivered
- **THEN** the inventory marks the dataset deferred
- **AND** no production-available claim is made.

#### Scenario: Daily foreign flow is implemented
- **WHEN** a verified provider returns buy and sell volume/value observations
- **THEN** quality checks validate dates, duplicates, non-negative components and net arithmetic
- **AND** `vnalpha` persists daily rows idempotently with source lineage.

### Requirement: Foreign-flow context SHALL be bounded and optional
Foreign-flow context SHALL be bounded and SHALL not block existing core readiness.

#### Scenario: Flow context is requested
- **WHEN** persisted observations are available
- **THEN** the consumer may expose latest, 5-session and 20-session net flow
- **AND** relative-to-trading metrics only when a canonical denominator exists
- **AND** missing flow never blocks price or ranking analysis.
