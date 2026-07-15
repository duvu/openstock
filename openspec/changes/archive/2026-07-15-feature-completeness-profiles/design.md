## Context

`feature_snapshot` currently records freshness, source counts, benchmark counts,
and a broad feature-data status. It does not encode whether a row has enough
history or populated fields for a particular research capability. As a result,
the builder can persist a 20-bar row while scoring or context builders consume
fields that need substantially more history.

Issue #80 established canonical-data quality and issue #82 established
benchmark-specific relative-strength artifacts. This change consumes those
contracts; it does not alter provider, canonical OHLCV, or benchmark selection
behavior.

## Goals / Non-Goals

**Goals:**

- Define deterministic, versioned profile policy and typed evaluation outcomes.
- Persist enough evidence to explain a snapshot's eligibility without parsing
  warning text or re-deriving the policy in every consumer.
- Enforce the same profile evidence at scoring, readiness, market-breadth, and
  sector-strength boundaries while retaining an explicit legacy state.
- Keep benchmark-neutral data usable for benchmark-neutral capabilities when
  relative strength is absent.

**Non-Goals:**

- Add indicators, change benchmark-selection policy, or fetch additional data.
- Rebuild historical snapshots automatically during migration.
- Change market-regime or sector methodology thresholds planned for #84.
- Add broker, account, portfolio, allocation, or execution behavior.

## Decisions

### One pure profile evaluator owns completeness policy

`vnalpha.features.completeness` will expose frozen request/result models and a
small explicit profile registry. The evaluator receives observed history,
feature values, freshness, and benchmark-relative-strength evidence and returns
typed missing neutral and relative-strength requirements. Feature construction
uses it before persistence; consumers use its persisted projection rather than
repeating null predicates.

Duplicating SQL predicates in each consumer would be a smaller first diff but
would recreate the drift that this issue fixes. A separate evidence table
would normalize evaluations but would add joins and an invalidation lifecycle
without a second evaluator or retained history requirement.

### Persist one evaluation plus separable neutral and RS outcomes

`feature_snapshot` gains additive columns for profile, neutral completeness,
relative-strength completeness, required and observed history, missing neutral
fields, missing relative-strength fields, and validation-rule version. The
builder persists the strongest supported neutral profile and records RS
completeness independently for that profile. Consumers select a profile and
declare whether relative strength is required.

This avoids treating missing benchmark data as a reason to discard valid
price/volume/volatility data. It also permits market breadth to use its
benchmark-neutral minimum while sector strength and scoring require the
explicit RS evidence they actually consume.

### Exact-date freshness remains a separate mandatory predicate

Completeness does not replace `as_of_bar_date` or `feature_data_status`.
Every consumer continues to require an exact-date, non-legacy snapshot and
adds the profile evidence predicate. The query/persistence adapter maps typed
profile and issue codes to stored values; user-facing renderers only receive
allowlisted missing-field labels.

### Migration is additive and fail-closed

New columns use `ADD COLUMN IF NOT EXISTS`. Existing rows are backfilled as
`LEGACY_UNKNOWN` with no asserted profile so they remain readable but cannot
satisfy a profile-enforcing consumer. Rebuilding features produces the new
evidence. Removing the new consumer predicates restores legacy read behavior,
so rollback does not require schema reversal.

## Risks / Trade-offs

- [Existing fixtures omit new evidence] → migration defaults are explicit and
  focused fixtures exercise legacy rejection before consumers are updated.
- [Profile definitions become policy sprawl] → keep the registry small,
  immutable, versioned, and limited to the three issue-defined profiles.
- [A consumer accidentally ignores RS requirements] → expose one typed
  repository predicate and cover scoring, breadth, sector, and readiness
  integration tests.
- [In-progress data is mistaken for complete] → require exact-date freshness,
  non-legacy evidence, and typed missing-field status at every selection
  boundary.

## Migration Plan

1. Add the profile/evidence columns and idempotent migration defaults.
2. Write profile-evaluator and persistence tests before implementation.
3. Write new feature rows with the evaluated evidence.
4. Update consumers to require the profiles they actually use.
5. Validate legacy rows are excluded until rebuilt and that a rebuilt fixture
   flows through the CLI-driven feature-to-score path.

## Open Questions

None. The issue defines the three profile names and the existing field set
defines their initial requirements.
