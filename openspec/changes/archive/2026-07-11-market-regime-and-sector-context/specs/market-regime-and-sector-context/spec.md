# Specification: Market Regime and Sector Context

## ADDED Requirements

### Requirement: Market regime snapshot

OpenStock SHALL produce a persisted market regime snapshot for an as-of date.

#### Scenario: User requests market regime

- **WHEN** the user runs `/market-regime`
- **THEN** the system returns regime state, index trend, index volatility, breadth metrics, freshness, lineage, quality status, and caveats

### Requirement: Sector strength ranking

OpenStock SHALL produce ranked sector strength snapshots.

#### Scenario: User requests sector strength

- **WHEN** the user runs `/sector-strength`
- **THEN** the system returns sectors ranked by deterministic strength metrics with methodology metadata

### Requirement: Symbol-sector alignment

OpenStock SHALL explain how a symbol aligns with sector context.

#### Scenario: User asks about FPT sector alignment

- **WHEN** symbol metadata and sector snapshots are available
- **THEN** the system states whether the symbol is aligned with a strong, neutral, weak, improving, or weakening group

### Requirement: Research-only context

Market and sector outputs SHALL remain research context only.

#### Scenario: Regime is risk-on

- **WHEN** the output describes a constructive regime
- **THEN** it does not instruct the user to buy, allocate, rebalance, or place orders

### Requirement: Insufficient data handling

The engine SHALL disclose missing or insufficient data.

#### Scenario: Sector metadata is incomplete

- **WHEN** sector ranking is generated with incomplete sector membership
- **THEN** the output includes a quality warning and caveat
