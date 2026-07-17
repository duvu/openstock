## Why

The accepted engineering vertical can build current-symbol features and scores,
but its full-universe ranking value is not yet reproducible or falsifiable. The
current research automation path also accepts legacy quality words that the
production feature builder never emits and measures hypotheses from a trailing
feature rather than a later observation.

## What Changes

- Align feature eligibility and later-outcome semantics first under issue #197.
- Add explicit price-basis and corporate-action lineage under #198.
- Freeze scoring behavior as immutable operator-selected policies under #199.
- Add point-in-time held-out evaluation and versioned assumptions under #200-#201.
- Deliver full-universe shortlist, reports, immutable snapshots, and bounded
  provider dataset experiments under #202-#205.
- Add reviewed policy decisions and an exact-SHA release gate under #206.

## Capabilities

### Modified Capabilities

- `research-automation`: production-aligned eligibility, later-observation
  measurement, point-in-time evaluation, reproducible reports, and policy review.

## Impact

The change primarily affects `vnalpha` feature, scoring, outcome, research
automation, CLI, TUI, artifact, warehouse, and validation paths. `vnstock` remains
data-focused. The system remains read-only and gains no broker, account, order,
portfolio, margin, transfer, or execution capability.
