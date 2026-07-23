## ADDED Requirements

### Requirement: Verified official corporate-action events SHALL reconcile deterministically
Only official event types already supported by the canonical corporate-action subsystem SHALL be eligible for reconciliation.

#### Scenario: Official and provider evidence agree
- **WHEN** an official event matches an existing provider action on identity, dates and terms
- **THEN** official source authority is linked to the canonical action
- **AND** no duplicate action revision is created.

#### Scenario: Official and provider evidence conflict
- **WHEN** dates, amount or ratio differ materially
- **THEN** the system creates a candidate revision or quarantine record according to the versioned source-authority policy
- **AND** does not silently overwrite provider evidence.

### Requirement: Unsupported or incomplete official events SHALL remain event evidence
Official events lacking deterministic adjustment terms SHALL remain non-mutating event evidence.

#### Scenario: An official event lacks fields required by the factor method
- **WHEN** deterministic adjustment terms cannot be established
- **THEN** the event remains disclosure/event context
- **AND** does not mutate canonical corporate actions or adjustment factors.

### Requirement: Accepted corporate-action revisions SHALL invalidate only the affected range
Accepted corporate-action revisions SHALL invalidate and rebuild only their affected range.

#### Scenario: An accepted official revision changes an existing action
- **WHEN** the revision is persisted
- **THEN** one affected-range signal is emitted
- **AND** adjustment factors and adjusted OHLCV are rebuilt only for the affected interval
- **AND** raw canonical OHLCV remains unchanged.

### Requirement: Downstream adjusted evidence SHALL preserve action lineage
Rebuilt adjusted evidence SHALL retain the accepted action and factor lineage that produced it.

#### Scenario: Adjusted features or outcomes are rebuilt
- **WHEN** an accepted action revision changes the factor chain
- **THEN** rebuilt artifacts reference the new action and factor lineage
- **AND** repeated reconciliation remains idempotent.

### Requirement: Valuation context SHALL use exact point-in-time inputs
Every valuation metric SHALL reference the exact canonical price date and basis, fundamental revision, share-count revision, taxonomy evidence and methodology version used.

#### Scenario: Current-only facts are available for a historical date
- **WHEN** a historical valuation snapshot is requested
- **THEN** current-only fundamentals or share counts are excluded
- **AND** unavailable metrics are reported explicitly.

### Requirement: Valuation metrics SHALL fail closed independently
Each valuation metric SHALL report unavailable when its own inputs are incompatible or absent.

#### Scenario: EPS or equity is missing, zero, negative or incompatible
- **WHEN** a metric denominator does not satisfy its declared rules
- **THEN** only the affected metric is unavailable
- **AND** the system does not guess, coerce or silently substitute another value.

### Requirement: Historical percentile SHALL use comparable persisted snapshots
Historical percentiles SHALL use only persisted snapshots with compatible point-in-time methodology.

#### Scenario: Historical P/E percentile is calculated
- **WHEN** prior comparable valuation snapshots exist
- **THEN** the percentile uses only snapshots with compatible methodology, scope, currency and price basis
- **AND** excludes future revisions.

### Requirement: Sector-relative percentile SHALL use point-in-time peers
Sector-relative percentiles SHALL use only peers supported by point-in-time taxonomy evidence.

#### Scenario: Sector-relative valuation is requested
- **WHEN** effective-dated membership or taxonomy evidence exists for the as-of date
- **THEN** the peer set uses that evidence
- **AND** excludes symbols without comparable metric semantics.

### Requirement: Valuation context SHALL remain optional and research-only
Valuation context SHALL remain optional, research-only evidence and SHALL not change ranking policy.

#### Scenario: Valuation evidence is unavailable
- **WHEN** existing price or ranking analysis is otherwise ready
- **THEN** core readiness remains unchanged
- **AND** valuation is disclosed as unavailable.

#### Scenario: Valuation context is rendered
- **WHEN** metrics are available
- **THEN** CLI, TUI and assistant use the same typed snapshot and caveats
- **AND** no target price, recommendation or automatic scoring-policy change is produced.
