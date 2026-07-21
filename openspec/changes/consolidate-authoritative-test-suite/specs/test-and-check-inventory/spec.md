## ADDED Requirements

### Requirement: Every retained test and validation check SHALL have a decision
The change SHALL classify every existing test and validation check as `KEEP`,
`MERGE`, `REPLACE` or `DELETE`. `MOVE_TO_NIGHTLY` is not a valid disposition
for duplicate or obsolete coverage.

#### Scenario: A retained authoritative contract is checked
- **WHEN** consistency reads the authoritative manifest
- **THEN** every retained entry has one contract identifier and one existing
  test node
- **AND** no two entries own the same contract identifier.

#### Scenario: A redundant checker is discovered
- **WHEN** a checker only repeats a real required gate
- **THEN** its inventory disposition is `MERGE` or `DELETE`
- **AND** it does not run as a separate required validation action.
