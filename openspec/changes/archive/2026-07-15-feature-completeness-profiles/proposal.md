## Why

Issue #83 is the next unblocked core roadmap item. Feature snapshots can be
persisted after only 20 bars even when downstream work requires MA100,
60-session returns, or 52-week context. Existing freshness and
benchmark-status metadata is valuable but does not say which capabilities a
snapshot can truthfully support.

## What Changes

- Add a typed, versioned feature-completeness contract with `MINIMAL_20`,
  `STANDARD_120`, and `FULL_252` profiles.
- Persist the profile evaluation, required and observed history, missing fields,
  benchmark-relative-strength status, and rule version with each feature
  snapshot.
- Keep benchmark-neutral completeness independent from relative-strength
  completeness so an unavailable benchmark does not invalidate unrelated
  price, volume, or volatility evidence.
- Make scoring, readiness, market breadth, and sector strength request an
  explicit profile and reject snapshots that cannot satisfy it on the requested
  exact date.
- Mark pre-existing snapshots as legacy/unknown rather than treating them as
  complete.

## Capabilities

### New Capabilities

- `feature-completeness-profiles`: Versioned, capability-specific feature
  completeness evidence and profile enforcement for research consumers.

### Modified Capabilities

- None.

## Impact

- Affects the `feature_snapshot` warehouse schema and its migration path.
- Affects feature construction, feature persistence, readiness, scoring,
  market breadth, and sector-strength selection in `vnalpha`.
- Depends on completed canonical-data and benchmark-registry work (#80 and
  #82); it does not add indicators, provider access, trading behavior, or any
  mutation outside the local research warehouse.
- Existing rows remain readable but are explicitly `LEGACY_UNKNOWN` until
  rebuilt under a completeness rule version.
