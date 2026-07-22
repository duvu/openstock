## Context

Issue #376 establishes a single-host process split for `vnalpha`. The existing
queue-backed change owns deterministic readiness, typed queue goals, job
identity, wait policy, worker execution and DuckDB write coordination. Its
interactive adapters still run in the same process, so there is no stable
contract for a future thin TUI/CLI client to use without reaching into queue,
warehouse or provider internals.

This change is the prerequisite contract for #378 (`WorkspaceClient`) and #379
(the local API). It preserves one repository, one Python codebase and one
shared typed domain/application layer. It does not move existing policy into a
transport layer or introduce another service boundary for `vnstock`.

## Goals / Non-Goals

**Goals:**

- Define production ownership for the client, control service, worker, timers
  and `vnstock-service`.
- Define a finite, versioned protocol with typed requests, results and errors.
- Classify every initial operation and preserve the evidence required by the
  current-symbol and durable-job contracts.
- Make local transport behavior, compatibility and failures actionable before
  #379 implements the adapter.
- Make direct interactive access to mutable infrastructure impossible in the
  production topology.

**Non-Goals:**

- Implement the `WorkspaceClient`, daemon, UDS server, package units or TUI
  migration.
- Change queue identities, capability/readiness policy, job state machines,
  worker concurrency, DuckDB ownership or maintenance finalization.
- Add a TCP/HTTP/public listener, TLS, multi-user authentication, browser UI,
  a repository/package split, a remote control plane or a database migration.
- Add generic job execution, SQL, shell, callable-name or arbitrary-URL
  endpoints, or any trading/account behavior.

## Decisions

### 1. One codebase and typed application layer span both process planes

The production topology is:

```text
TUI / interactive CLI
  -> WorkspaceClient
  -> vnalpha-local-protocol v1 over UDS
  -> service application adapters
  -> read-only warehouse queries or durable typed queue
  -> one worker / one DuckDB writer
  -> vnstock-service
```

The client renders typed results and submits finite use cases. The control
service invokes the existing application layer and performs only short-lived
read-only warehouse reads. The worker owns normal mutation through the existing
write coordinator. Timers invoke bounded service/operator use cases; they do
not become a second scheduler. `vnstock-service` remains a worker/service-plane
dependency and is never called by a client process.

This is a modular-monolith process boundary, not a microservice decomposition.
Duplicating readiness, capability selection, queue identity or remediation
policy in `WorkspaceClient`, a protocol handler or a TUI is prohibited.

Alternatives rejected:

- Keep direct local calls from the TUI/CLI: cannot enforce the future ownership
  and permission boundary.
- Separate repositories/packages: creates versioning and duplicated-domain
  risk without a multi-host requirement.
- Let the service expose generic function dispatch: creates a remote execution
  boundary rather than a bounded research protocol.

### 2. Protocol v1 is a bounded request/response contract

The initial protocol uses one UTF-8 JSON request and one UTF-8 JSON response per
Unix-domain-socket connection. A frame is length-delimited, bounded before JSON
decoding and contains exactly one typed envelope. The protocol is not HTTP and
does not provide streaming, subscriptions, callbacks or arbitrary routing.

Each request carries:

```text
protocol_version: "v1"
request_id: bounded opaque client request identifier
correlation_id: optional bounded opaque lineage identifier
operation: closed V1 operation enum
payload: operation-specific typed DTO
```

The service assigns a correlation ID when the client omits one and echoes the
request ID. A response carries the negotiated version, request ID, correlation
ID, one client result status, an operation-specific typed result or an error,
and typed evidence metadata. Requests and responses have a configured maximum
size; an oversized or malformed frame is rejected before application dispatch.

`v1` is the major compatibility key. A service accepts exactly its supported
major versions. It may add optional fields only when older clients can ignore
them; it never changes the meaning or required type of an accepted field. A
client sends its exact supported major and receives a typed
`UNSUPPORTED_PROTOCOL_VERSION` response with the supported versions when a
connection can be established. There is no silent downgrade or schema guessing.

### 3. The public operation inventory is closed and classified

The following inventory is the complete initial public operation enum. Payloads
are discriminated typed models, not a free-form command string or dictionary.

| Operation | Classification | Service behavior |
| --- | --- | --- |
| `HEALTH_STATUS` | synchronous query | Return local service, queue, warehouse and dependency readiness summaries. |
| `WATCHLIST_LATEST` | synchronous query | Read the latest immutable published watchlist snapshot. |
| `WATCHLIST_HISTORY` | synchronous query | Read a bounded historical range of immutable published snapshots. |
| `CURRENT_SYMBOL_RESEARCH` | immediate application command | Invoke the owned current-symbol application; it can return a read result or submit/join one existing durable goal under #322/#325. |
| `JOB_LIST` | synchronous query | Return bounded durable-job summaries. |
| `JOB_STATUS` | synchronous query | Return one job's typed state, stage and bounded evidence. |
| `JOB_WAIT` | immediate application command | Observe one job through the existing wait policy without cancelling it. |
| `JOB_CANCEL` | immediate application command | Request explicit cooperative cancellation of an existing job. |
| `JOB_RETRY` | durable job command | Validate a terminal typed job and create or join its retry according to #325. |
| `ENSURE_CURRENT_SYMBOL` | durable job command | Submit or join only the typed current-symbol goal owned by #338. |
| `MAINTENANCE_RUN_SUBMIT` | durable job command | Freeze and submit/join bounded maintenance work owned by #326. |
| `MAINTENANCE_RUN_STATUS` | synchronous query | Return one maintenance run's frozen scope and truthful state. |
| `DIAGNOSTICS_STATUS` | synchronous query | Return bounded queue and warehouse diagnostic summaries without mutation or secret-bearing detail. |

Immediate application commands return after their finite application operation
has completed. Durable job commands return stable job/run identity and do not
claim durable work has completed. Existing queue goals, readiness capabilities,
job lifecycle and maintenance states remain defined by #317, #322, #325, #326,
#337, #339, #343 and #344; this protocol only serializes their public typed
results.

### 4. Shared result semantics remain truthful across every client

Every successful protocol response has exactly one result status:

| Status | Meaning |
| --- | --- |
| `READY` | Requested read/application evidence is available and valid. |
| `DEGRADED` | A deterministic lower effective capability is valid; limitations name the unavailable scope. |
| `ACCEPTED` | A durable command was accepted or joined and continues asynchronously. |
| `PENDING` | A bounded wait elapsed while durable work remains active. |
| `BUSY` | A bounded local resource/contention limit prevented this operation from being served now; no completion is implied and retry guidance is present. |
| `UNAVAILABLE` | Required evidence or dependency is known unavailable/non-repairable for the request. |
| `FAILED` | The typed operation reached a terminal failure. |

`READY` and `DEGRADED` are the only current-symbol results that may include
analysis. `ACCEPTED` and `PENDING` include the stable job ID when applicable
and never imply cancellation. `BUSY` is distinct from `PENDING`: it does not
claim that the request has a durable job unless the typed result includes one.

### 5. Metadata is typed evidence, not opaque service output

Where applicable, a result contains requested and effective date/capability,
freshness state and basis, typed lineage references, limitations, durable job
or maintenance-run ID, correlation ID, selected wait policy and timeout.
Lineage is restricted to stable artifact/source-policy/version/snapshot and
stage references. Diagnostics include stable error code, retry/remediation
action and safe component name; they exclude credentials, authorization
headers, raw SQL, arbitrary paths, stack traces and provider payloads.

The protocol adapter maps known application failures to typed errors without
rewriting their evidence. Unknown failures are logged service-side with the
correlation ID and returned as a bounded `INTERNAL_FAILURE` diagnostic.

### 6. Unix-domain socket is the first and only production transport

The v1 socket path is `/run/openstock/vnalpha.sock`. The service creates it in
`/run/openstock`, owned by the `openstock` service account and `openstock`
group. The runtime directory is mode `0750`; the socket is mode `0660`; only
the service account and members of the `openstock` group can connect. Packaging
#381 is responsible for provisioning that account, group and runtime directory
without weakening these modes.

The client maps local failures as follows:

| Condition | Typed error/result |
| --- | --- |
| Socket absent, stale or connection refused | `SERVICE_UNAVAILABLE` with start/status remediation. |
| Socket or runtime directory permission denied | `SERVICE_ACCESS_DENIED` with group-membership remediation. |
| Protocol major unsupported | `UNSUPPORTED_PROTOCOL_VERSION` with supported versions. |
| Frame malformed or too large | `MALFORMED_REQUEST` without application dispatch. |
| Service capacity or bounded warehouse/queue contention | `BUSY` with retry guidance. |
| Client read/write deadline expires | `SERVICE_TIMEOUT` with a statement that any durable job is unchanged. |

The implementation removes a stale socket only after proving it is a socket at
the configured path and that no supported service owns it. It never follows a
symlink or binds a TCP port as fallback.

### 7. Client disconnect never changes durable work

The API/control service treats request connection lifetime as observation
lifetime, not job ownership. A disconnect, local client timeout or a
`JOB_WAIT` deadline closes only that request. It never cancels a submitted or
joined job. Cancellation is the explicit `JOB_CANCEL` operation, warns when
the job is shared and remains cooperative under #324/#325. A later client can
query or wait on the same stable ID.

### 8. Public, operator and development paths are deliberately separate

Public protocol operations are exactly the inventory above. Worker handlers,
timer recovery/maintenance triggers, queue prune/checkpoint/integrity actions,
warehouse recovery and service lifecycle administration are internal operator
or service commands with separate typed entrypoints. They are not exported as
public operation names and cannot be requested through an arbitrary string.

An in-process adapter is allowed only for unit/integration tests, explicit
development mode and explicit recovery tooling. It must implement the same
typed interface and must declare its mode. Production TUI and interactive CLI
always use `WorkspaceClient` over the UDS; no development fallback activates
implicitly in production.

## Risks / Trade-offs

- [A local socket is unavailable during restart] → clients return a typed
  unavailable/timeout result with remediation; durable state remains in the
  queue and warehouse for the next connection.
- [A v1 DTO later needs a breaking shape] → introduce a new major protocol and
  run compatible versions only through an explicit migration window.
- [Long waits consume control-service capacity] → preserve #325 bounded wait
  policies and return `PENDING`; v1 adds no subscriber registry or streaming.
- [Socket-group membership is misconfigured] → fail closed with
  `SERVICE_ACCESS_DENIED`; never relax the socket mode or use TCP fallback.
- [Adapter code reimplements policy] → code review and contract tests compare
  `WorkspaceClient` results with the shared application results in #378/#379.

## Migration Plan

1. #378 implements protocol DTOs and `WorkspaceClient` against this v1
   contract, including in-process adapters only in the permitted modes.
2. #379 hosts the typed application adapters over the configured UDS and
   verifies the error/compatibility matrix.
3. #380 moves the TUI and interactive CLI to `WorkspaceClient`, removing their
   direct queue, writable-DuckDB and `vnstock-service` paths.
4. #381 packages the control service, socket ownership and service lifecycle.
5. #382/#383 and the retained queue issues use only the finite protocol or
   documented internal operator seams.

Rollback consists of stopping the new control service and restoring the
previous installed client only before #380 removes direct paths. No protocol
rollback mutates queue or warehouse state. After the thin-client migration,
production rollback keeps the last compatible service version running until a
compatible client is installed; it never enables an in-process production
fallback.

## Open Questions

None. The v1 frame limit and service timeouts are configuration values to be
selected by #379/#381 within this contract's bounded, fail-closed behavior.
