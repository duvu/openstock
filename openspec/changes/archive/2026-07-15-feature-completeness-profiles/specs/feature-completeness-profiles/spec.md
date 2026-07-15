## ADDED Requirements

### Requirement: Versioned feature completeness evidence

The system SHALL evaluate every newly persisted feature snapshot against the
versioned `MINIMAL_20`, `STANDARD_120`, and `FULL_252` completeness profiles.
The evidence SHALL record the selected profile, required and observed history,
missing benchmark-neutral fields, missing relative-strength fields, neutral and
relative-strength completeness outcomes, and the validation-rule version.

#### Scenario: A 20-bar snapshot is evaluated

- **WHEN** a feature snapshot is built from exactly 20 canonical daily bars
- **THEN** it SHALL satisfy only the profile whose required history and
  benchmark-neutral fields are present
- **AND** it SHALL record why it does not satisfy the higher-history profiles.

#### Scenario: A full-history snapshot is evaluated

- **WHEN** a feature snapshot has 252 valid daily bars and all required fields
- **THEN** it SHALL record `FULL_252` neutral completeness under the current
  validation-rule version.

### Requirement: Benchmark-neutral and relative-strength completeness remain distinct

The system SHALL evaluate benchmark-neutral feature evidence independently from
relative-strength evidence. Missing or incomplete benchmark data SHALL not
invalidate an otherwise complete neutral profile, but SHALL prevent a
relative-strength-requiring consumer from treating the snapshot as complete.

#### Scenario: Benchmark data is unavailable

- **WHEN** a symbol has sufficient exact-date price, volume, and volatility
  data but no usable benchmark-relative-strength values
- **THEN** its neutral completeness SHALL remain truthful
- **AND** its relative-strength completeness SHALL record the typed missing
  requirement.

### Requirement: Profile-enforcing consumers fail closed

Scoring, readiness, market breadth, and sector strength SHALL declare their
required profile and whether relative strength is required. They SHALL use
only exact-date, non-legacy snapshots that satisfy that declared evidence and
SHALL expose typed exclusions rather than inferring readiness from row
existence or warning text.

#### Scenario: Scoring receives an incomplete standard snapshot

- **WHEN** scoring requests a profile that requires MA100 and 60-session
  return evidence from a snapshot that has only 20 bars
- **THEN** scoring SHALL refuse to generate a score from that snapshot
- **AND** the exclusion SHALL identify the missing profile evidence.

#### Scenario: Market breadth receives an exact minimal snapshot

- **WHEN** market breadth requests its benchmark-neutral minimum profile for
  an exact-date snapshot satisfying that profile
- **THEN** it SHALL include the snapshot without requiring relative strength.

#### Scenario: Sector strength receives missing relative strength

- **WHEN** sector strength requests a profile with relative strength and the
  snapshot lacks benchmark-relative-strength evidence
- **THEN** it SHALL exclude the snapshot and retain the typed reason.

### Requirement: Legacy feature snapshots are explicit

The warehouse migration SHALL preserve existing feature snapshots while marking
their completeness as `LEGACY_UNKNOWN`. A legacy snapshot SHALL remain
readable for compatibility but SHALL not satisfy a profile-enforcing consumer
until rebuilt under a known validation-rule version.

#### Scenario: Existing warehouse is migrated

- **WHEN** migrations run against a warehouse containing pre-profile feature
  snapshots
- **THEN** the rows SHALL remain queryable
- **AND** profile-enforcing consumers SHALL reject them until a feature rebuild
  persists explicit completeness evidence.
