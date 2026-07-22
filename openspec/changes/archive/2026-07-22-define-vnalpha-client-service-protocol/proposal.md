## Why

The queue-backed research runtime now has a typed application and durable-job
foundation, but its terminal clients still share the same process as warehouse,
queue and provider-facing operations. Before a network adapter is introduced,
OpenStock needs one normative boundary that keeps the repository and typed
domain/application layer shared while making production ownership explicit.

## What Changes

- Define a versioned, host-local client/service protocol for `vnalpha`.
- Assign production ownership to the TUI/interactive CLI client, API/control
  service, sequential worker, system timers and `vnstock-service`.
- Classify the initial bounded operations as synchronous queries, immediate
  application commands or durable job commands, with closed typed payloads.
- Define the common request, response, error, correlation, lineage and
  capability/freshness metadata contracts, including the existing client result
  states.
- Specify Unix domain socket transport, socket ownership and permissions,
  connection-failure behavior, protocol-version compatibility and safe
  diagnostics.
- Separate public client commands from internal worker, timer and operator
  commands; confine in-process adapters to tests, development and explicit
  recovery tooling.
- Explicitly reject public listeners, generic remote execution, direct client
  access to the queue/writable warehouse/`vnstock-service`, and duplicated
  domain policy.

## Capabilities

### New Capabilities

- `vnalpha-local-service-protocol`: The process ownership, finite operations,
  versioned envelopes and Unix-domain-socket transport contract between the
  vnalpha client and service planes.

### Modified Capabilities

- None.

## Impact

This is a specification-only prerequisite for #378 through #383. It introduces
no listener, package split, public API, TLS, browser UI, multi-user
authentication, database migration, broker integration or trading capability.
Future `WorkspaceClient`, API, TUI and packaging work must implement this
contract while reusing the typed queue and current-symbol contracts owned by
#317, #322, #325, #326, #337, #339, #343 and #344.
