## MODIFIED Requirements

### Requirement: Market regime snapshot

OpenStock SHALL produce a persisted, versioned market-regime snapshot for an
as-of date and SHALL NOT classify a production regime from inputs below the
active policy thresholds.

#### Scenario: Five technically valid rows are available

- **WHEN** production methodology receives only five eligible feature rows
- **THEN** it persists `INSUFFICIENT_DATA` with explicit coverage and policy lineage
- **AND** deep-analysis readiness rejects the snapshot

#### Scenario: Production market evidence is complete

- **WHEN** the exact-date common-equity universe satisfies the minimum eligible, breadth, exchange, liquidity and completeness requirements
- **THEN** the system deterministically classifies the regime
- **AND** persists methodology version, thresholds, exclusions, coverage, breadth metrics and caveats

### Requirement: Sector strength ranking

OpenStock SHALL rank only sectors that satisfy the active versioned membership,
eligibility, metadata, taxonomy and liquidity policy.

#### Scenario: Sector is sparse or illiquid

- **WHEN** a sector has fewer than the required active or eligible members or falls below coverage
- **THEN** it is excluded from ranking or explicitly degraded
- **AND** the result caveats identify the rejected sector and reason

#### Scenario: Sector contains an extreme outlier

- **WHEN** one eligible member has an extreme return or relative-strength value
- **THEN** production aggregation applies deterministic policy-bounded winsorization
- **AND** records the adjustment count and concentration evidence in lineage

### Requirement: Methodology compatibility and readiness

OpenStock SHALL keep historical `v1` methodology callable for compatibility,
while production readiness SHALL require accepted `v2` methodology evidence.

#### Scenario: Legacy snapshot is loaded for deep analysis

- **WHEN** a persisted market or sector snapshot uses a legacy methodology version
- **THEN** readiness fails closed with a typed quality or coverage issue
- **AND** the user is directed to rebuild production context

### Requirement: Research-only context

Market and sector outputs SHALL remain deterministic research context only.

#### Scenario: Production regime is constructive

- **WHEN** the output describes a risk-on or leading-sector state
- **THEN** it does not instruct the user to buy, allocate, rebalance or place orders
