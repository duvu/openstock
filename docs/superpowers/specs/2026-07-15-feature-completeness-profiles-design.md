# Feature Completeness Profiles Design

## Goal

Make feature-snapshot usability explicit, versioned, and capability-specific so
research consumers cannot mistake a persisted 20-bar row for complete evidence.

## Architecture

One deterministic profile evaluator owns `MINIMAL_20`, `STANDARD_120`, and
`FULL_252` policy.  Feature construction writes its neutral and
relative-strength outcomes to additive `feature_snapshot` columns.  Scoring,
readiness, breadth, and sector strength then require the profile evidence they
consume, in addition to the existing exact-date freshness predicate.

The evaluator keeps price/volume/volatility evidence separate from
benchmark-relative strength.  This lets benchmark-neutral research remain
truthful when a benchmark is unavailable while preventing relative-strength
consumers from using an incomplete row.  Existing rows migrate to
`LEGACY_UNKNOWN` and remain readable but never satisfy an explicit profile.

## Boundaries

This change does not add indicators, providers, data fetching, market/sector
methodology thresholds, or any trading behavior.  Canonical OHLCV and
benchmark selection remain authoritative inputs established by #80 and #82.
