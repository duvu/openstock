## Why

OpenStock has individually capable ingestion, warehouse, research-context and
memory subsystems, but operators lack one deterministic daily operation and one
release-candidate acceptance gate proving that they form a coherent core loop.
Issues #238, #239, #243, #244 and #245 establish that operational spine after
the effective-date, diagnostics, data-only and knowledge-memory dependencies.

Current implementation includes the one-shot daily command, systemd packaging
and the canonical #238 documentation pointer. The remaining gap is exact
release-candidate validation, OpenSpec evidence reconciliation and closure on
the final published commit.

Dependencies are #231–#233 and #239–#244 in the order recorded by #238. The
verified existing capability includes canonical ingestion/build services,
market/sector context, structured memory lifecycle and Debian packaging.

## What Changes

- add one deterministic, date-bound `vnalpha maintain daily` operation with
  dry-run, non-session, partial-provider and repeated-run semantics;
- run selective symbol and typed entity-memory projection after validated
  research snapshots, without promoting model prose;
- package an explicit-timezone weekday systemd timer disabled by default, with
  stable writer locking and machine-readable results;
- make #238 the single live roadmap pointer and mark older planning documents
  historical;
- require clean-host acceptance against the exact package and commit before the
  core-loop umbrella can close;
- preserve all existing CLI, TUI, assistant, readiness and package paths.

No broker, order, account, portfolio, allocation, margin, transfer, execution,
unrestricted SQL/shell/filesystem or autonomous assistant `data.fetch` behavior
is introduced.

## Capabilities

### New Capabilities

- `daily-core-maintenance`: Deterministic one-shot daily maintenance, explicit
  scheduling, truthful outcomes, stable locking and release acceptance.

### Modified Capabilities

None. Symbol/entity memory and market/group context requirements remain owned
by their overlapping active changes and are not duplicated here.

## Impact

The change affects `vnalpha` maintenance and CLI services, warehouse build and
memory projection orchestration, Debian/systemd assets, root validation gates,
operator documentation, the OpenSpec registry and GitHub closure evidence.
The database migration is additive and existing symbol APIs remain compatibility
wrappers over typed entity identity.
