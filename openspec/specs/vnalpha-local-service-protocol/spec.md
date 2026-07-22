## ADDED Requirements

### Requirement: vnalpha SHALL have one shared domain and application layer
Production SHALL preserve one OpenStock repository, one `vnalpha` codebase and
one shared typed domain/application layer across the client and service planes.
The `WorkspaceClient`, protocol adapter, TUI and CLI SHALL delegate to that
layer and SHALL NOT duplicate readiness, capability, remediation, queue
identity, persistence or analysis policy.

#### Scenario: A client requests current-symbol research
- **WHEN** a TUI or interactive CLI submits current-symbol research
- **THEN** its `WorkspaceClient` invokes the shared service application contract
- **AND** no client-specific capability or remediation policy is evaluated.

### Requirement: Production process ownership SHALL be explicit
The TUI and interactive CLI SHALL be client-plane processes. The API/control
service SHALL own public protocol dispatch and application orchestration. One
sequential worker SHALL own normal durable-job execution and DuckDB mutation
through the existing write coordinator. Timers SHALL trigger only bounded
internal maintenance/recovery commands. `vnstock-service` SHALL remain a
service/worker-plane dependency.

#### Scenario: A durable current-symbol command is submitted
- **WHEN** a client submits `ENSURE_CURRENT_SYMBOL`
- **THEN** the control service submits or joins its typed durable goal
- **AND** the worker, not the client or control-service request handler, runs
  normal provider and writable-DuckDB work.

### Requirement: Public client operations SHALL be finite and classified
The v1 public protocol SHALL accept only the following typed operations:

| Classification | Operations |
| --- | --- |
| Synchronous query | `HEALTH_STATUS`, `WATCHLIST_LATEST`, `WATCHLIST_HISTORY`, `JOB_LIST`, `JOB_STATUS`, `MAINTENANCE_RUN_STATUS`, `DIAGNOSTICS_STATUS` |
| Immediate application command | `CURRENT_SYMBOL_RESEARCH`, `JOB_WAIT`, `JOB_CANCEL` |
| Durable job command | `JOB_RETRY`, `ENSURE_CURRENT_SYMBOL`, `MAINTENANCE_RUN_SUBMIT` |

Each operation SHALL have a dedicated typed request and response DTO. The
protocol SHALL reject SQL, shell text, Python callable names, arbitrary URLs,
untyped command strings and payload-directed dispatch before application work.

#### Scenario: A caller sends an unknown operation
- **WHEN** a request contains an operation outside the v1 operation enum
- **THEN** the service returns `MALFORMED_REQUEST` or
  `UNSUPPORTED_OPERATION`
- **AND** it performs no queue, warehouse, provider or shell work.

### Requirement: Protocol envelopes SHALL be versioned and correlated
Every v1 request SHALL contain `protocol_version`, `request_id`, one closed
operation enum and an operation-specific typed payload. It MAY contain a
bounded opaque correlation ID. Every response SHALL echo the request ID,
include the correlation ID, include its response protocol version and contain
exactly one typed result or error envelope.

#### Scenario: A client omits a correlation ID
- **WHEN** a valid v1 request has no correlation ID
- **THEN** the service assigns a bounded correlation ID
- **AND** the response and related safe diagnostics contain that same ID.

### Requirement: Protocol compatibility SHALL fail closed
The service SHALL accept only supported protocol major versions. It SHALL
return `UNSUPPORTED_PROTOCOL_VERSION` and the supported version set for an
otherwise decodable unsupported request. It SHALL NOT silently downgrade, infer
another request schema or reinterpret a field with changed meaning.

#### Scenario: A v2 client contacts a v1-only service
- **WHEN** the service receives a decodable request declaring unsupported major
  protocol version `v2`
- **THEN** it returns a typed unsupported-version error naming `v1`
- **AND** it does not dispatch the request to an application operation.

### Requirement: Client result statuses SHALL be truthful and complete
Every public operation result SHALL use exactly one of `READY`, `DEGRADED`,
`ACCEPTED`, `PENDING`, `BUSY`, `UNAVAILABLE` or `FAILED`. `READY` means the
requested evidence is valid; `DEGRADED` means only a deterministic lower
effective capability is valid; `ACCEPTED` means durable work was accepted or
joined; `PENDING` means an explicit bounded wait expired while work is active;
`BUSY` means a local capacity or contention limit prevented service now;
`UNAVAILABLE` means the required evidence/dependency is non-repairable; and
`FAILED` means the operation reached a terminal failure.

#### Scenario: A bounded job wait expires
- **WHEN** `JOB_WAIT` or current-symbol research reaches its configured bounded
  wait timeout while the durable job remains active
- **THEN** the response result is `PENDING`
- **AND** the response includes the stable job ID and selected wait policy
- **AND** it does not report cancellation or a terminal result.

### Requirement: Public DTOs SHALL preserve research evidence
Where applicable, public result DTOs SHALL preserve requested and effective
date, requested and effective capability, freshness state/basis, typed lineage
references, limitations, job ID, maintenance-run ID, correlation ID, wait
policy and timeout. Lineage SHALL contain only stable artifact, snapshot,
source-policy, contract-version and stage references required to interpret the
result.

#### Scenario: Ranking research is valid only at price capability
- **WHEN** current-symbol research requested `CANDIDATE_RANKING` but the shared
  application selects `PRICE_ANALYSIS`
- **THEN** the public result is `DEGRADED`
- **AND** it preserves both requested/effective capabilities, effective date,
  freshness, limitations, lineage and correlation ID.

### Requirement: Durable job observation SHALL not imply cancellation
Client disconnect, client-side socket timeout and `JOB_WAIT` timeout SHALL end
only that request's observation. They SHALL NOT cancel a submitted or joined
job. `JOB_CANCEL` SHALL be the only public cancellation command, SHALL be
explicit, SHALL warn when a job can be shared and SHALL use the cooperative
cancellation semantics owned by the durable-job service.

#### Scenario: A waiting client disconnects
- **WHEN** a client disconnects after `ENSURE_CURRENT_SYMBOL` returned a stable
  job ID
- **THEN** the job remains observable by `JOB_STATUS` or a later `JOB_WAIT`
- **AND** no cancellation request is issued.

### Requirement: Production transport SHALL be a protected Unix-domain socket
The v1 production transport SHALL use `/run/openstock/vnalpha.sock`. The
`/run/openstock` runtime directory SHALL be owned by the `openstock` service
account and group with mode `0750`; the socket SHALL be owned by that account
and group with mode `0660`. No TCP, HTTP or other public listener SHALL be a
fallback transport.

#### Scenario: A non-member attempts to connect
- **WHEN** a process outside the socket's authorized account/group attempts to
  connect
- **THEN** the client reports `SERVICE_ACCESS_DENIED` with safe group-membership
  remediation
- **AND** it does not relax socket permissions or try a network listener.

### Requirement: Local transport failures SHALL be typed and actionable
The service SHALL map socket absence, connection refusal, safe stale-socket
detection, permission denial, malformed/oversized frames, service contention
and client deadlines to bounded typed errors. Those errors SHALL state the
affected local component and safe remediation, and SHALL state that durable job
state is unchanged when a client deadline/disconnect occurs.

#### Scenario: The service is not running
- **WHEN** `WorkspaceClient` finds no listening socket at the configured path
- **THEN** it returns `SERVICE_UNAVAILABLE` with a start/status remediation
- **AND** it does not create the socket, invoke the queue directly or substitute
  an in-process production adapter.

### Requirement: Safe diagnostics SHALL not expose execution or secret material
Public errors and diagnostics SHALL include stable error code, safe component,
correlation ID and bounded retry/remediation guidance. They SHALL NOT expose
credentials, tokens, authorization headers, raw SQL, arbitrary filesystem
paths, stack traces, provider payloads or internal callable names.

#### Scenario: An unexpected service exception occurs
- **WHEN** an application adapter raises an unexpected exception
- **THEN** the service logs the diagnostic internally with the correlation ID
- **AND** the client receives a bounded `INTERNAL_FAILURE` envelope without the
  exception text or stack trace.

### Requirement: Interactive clients SHALL not access mutable infrastructure directly
Production TUI and interactive CLI processes SHALL access the service plane only
through `WorkspaceClient` over the v1 UDS. They SHALL NOT open writable DuckDB,
access the queue database, invoke worker handlers, call `vnstock-service` or
invoke operator-only commands directly.

#### Scenario: A TUI user requests queue status
- **WHEN** the TUI renders queue status
- **THEN** it obtains the bounded `DIAGNOSTICS_STATUS` or job-query DTO through
  `WorkspaceClient`
- **AND** it does not open the SQLite queue database itself.

### Requirement: Public commands SHALL remain separate from operator commands
The service SHALL keep worker handlers, timer triggers, queue
integrity/prune/checkpoint actions, warehouse recovery and service lifecycle
controls as internal typed operator/service commands. They SHALL NOT appear in
the public v1 operation enum or be reachable through a generic command name.

#### Scenario: A public caller requests an operator action
- **WHEN** a public protocol request names a queue checkpoint or warehouse
  recovery action
- **THEN** the protocol rejects it as an unsupported operation
- **AND** it does not run the operator action.

### Requirement: In-process adapters SHALL be explicit and non-production
The system SHALL permit an in-process adapter only for tests, explicit
development mode or explicit recovery tooling. It SHALL implement the same
typed contract and declare its mode. Production interactive clients SHALL use
the UDS client and SHALL NOT silently fall back to an in-process adapter.

#### Scenario: The production socket is unavailable
- **WHEN** a production interactive client cannot connect to the UDS
- **THEN** it returns the typed local transport failure
- **AND** it does not invoke the shared application layer in-process.

### Requirement: The local protocol SHALL preserve the research-only boundary
The public protocol and all initial DTOs SHALL remain research-only. They SHALL
not add broker login, order placement, account mutation, margin, transfers,
portfolio allocation, autonomous trading execution or generic remote execution.

#### Scenario: A client submits an order-like payload
- **WHEN** a request attempts to name an order, account or trading operation
- **THEN** protocol validation rejects it before dispatch
- **AND** no broker, account or trading surface is contacted.
