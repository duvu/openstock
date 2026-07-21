## ADDED Requirements

### Requirement: Production SHALL use one authoritative warehouse
The system SHALL open only the configured production DuckDB warehouse and SHALL return a typed error when it cannot be opened.

#### Scenario: Production warehouse cannot be opened
- **WHEN** a production read or write connection cannot open the configured warehouse
- **THEN** the system reports a typed busy, unavailable, permission or schema error
- **AND** it does not copy, substitute or create another warehouse.

### Requirement: Read and write connection lifecycles SHALL be separated
Readiness and analysis SHALL use short-lived read-only connections. DuckDB writes SHALL use one global write coordinator.

#### Scenario: A request waits for queued provisioning
- **WHEN** readiness determines that queued work is required
- **THEN** the read-only warehouse connection is closed before submission or polling
- **AND** a new read-only connection is opened only after terminal work when analysis is permitted.

#### Scenario: A DuckDB mutation runs
- **WHEN** any subsystem must mutate DuckDB
- **THEN** it acquires the global writer lock before opening a writable connection
- **AND** closes the connection before releasing the lock.

### Requirement: All DuckDB writers SHALL use the same coordinator
Provisioning, migrations, finalization, outcomes, context, memory and metadata writes SHALL NOT bypass the write coordinator.

#### Scenario: Chat trace persistence overlaps provisioning
- **WHEN** a chat trace write is requested while the provisioner owns the writer lock
- **THEN** the trace write waits or returns the configured typed contention result
- **AND** it does not open a competing writable connection.

### Requirement: Artifact readiness SHALL be capability-scoped
The system SHALL classify artifacts as `READY`, `STALE`, `MISSING` or `INVALID` and SHALL distinguish required from optional evidence.

#### Scenario: Canonical price evidence exists without ranking evidence
- **WHEN** valid canonical OHLCV satisfies price-analysis history, date, quality and gap rules
- **AND** benchmark, feature or score evidence is missing
- **THEN** `PRICE_ANALYSIS` is ready
- **AND** `CANDIDATE_RANKING` is not ready.

### Requirement: Repairability SHALL be source-aware
The readiness report SHALL combine warehouse state with source policy, provider capability, authentication readiness, persistence permission and bounded remediation availability.

| Warehouse evidence | Source and persistence status | Proposed action | Repairable |
| --- | --- | --- | --- |
| Raw OHLCV is absent or stale | An eligible, persistence-approved provider is available | Bounded target or benchmark sync | Yes |
| Raw OHLCV exactly covers the missing trading sessions | N/A | Bounded canonical promotion only | Yes |
| Canonical OHLCV is valid but ranking derivatives are absent | Required upstream canonical evidence is ready or repairable | Build features or score symbol | Yes |
| Provider is unavailable, unapproved, or FiinQuantX lacks explicit readiness | N/A | None | No |
| Historical request, invalid persisted evidence, optional artifact, or checks-only policy | N/A | None | No |

#### Scenario: A required artifact has no eligible source
- **WHEN** a required artifact is missing
- **AND** no approved source or local deterministic build can produce it
- **THEN** the report marks it non-repairable
- **AND** `should_enqueue` is false.

#### Scenario: Raw evidence is ready but canonical evidence is stale
- **WHEN** raw OHLCV reaches the effective session
- **AND** canonical OHLCV does not
- **THEN** the report proposes canonical promotion only
- **AND** proposes no provider action.

### Requirement: Readiness inspection SHALL be read-only
The readiness operation SHALL perform no provider call, write, migration or writer-lock acquisition.

#### Scenario: CLI, TUI and assistant inspect the same request
- **WHEN** equivalent request inputs are inspected through each surface
- **THEN** every surface receives the same readiness report
- **AND** warehouse row counts remain unchanged.

### Requirement: Historical workflows SHALL NOT propose current acquisition
Historical replay and backtest readiness SHALL report missing persisted evidence without proposing or submitting current-data acquisition.

#### Scenario: Replay requests missing evidence
- **WHEN** a replay or backtest request encounters missing persisted evidence
- **THEN** readiness returns the missing/non-repairable result
- **AND** does not propose or submit a current-data job.
