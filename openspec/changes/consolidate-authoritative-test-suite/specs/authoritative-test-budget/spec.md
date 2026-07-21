## ADDED Requirements

### Requirement: The authoritative inventory SHALL be budgeted
The repository SHALL keep approximately 180–220 authoritative tests and SHALL
fail consistency when the declared authoritative count exceeds 250.

#### Scenario: The inventory is within the hard cap
- **WHEN** repository consistency reads the authoritative manifest
- **THEN** every declared test exists
- **AND** the declared count is at most 250.

#### Scenario: The inventory exceeds the hard cap
- **WHEN** the manifest has more than 250 authoritative tests
- **THEN** consistency fails with the count and budget remediation.

### Requirement: Existing contracts SHALL not grow test count by default
Adding coverage for an existing contract SHALL reuse, replace, merge or
parameterize its owner. A new test is allowed only for a distinct public or
approved risk contract and must keep the net repository count at or below the
baseline decision recorded for the change.

#### Scenario: Existing coverage needs another literal case
- **WHEN** an additional literal exercises the same public result class
- **THEN** its owner is parameterized or replaced
- **AND** the inventory count does not grow.
