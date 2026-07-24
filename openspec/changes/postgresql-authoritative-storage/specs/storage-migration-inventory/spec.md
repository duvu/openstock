## ADDED Requirements

### Requirement: Storage coupling SHALL be inventoried from the exact checkout
The repository SHALL provide a deterministic scanner that finds DuckDB/SQLite driver use, direct SQL, DDL, database paths, file locks, temporary database tests, packaging, backup and documentation assumptions.

#### Scenario: The inventory is generated
- **WHEN** `python scripts/postgresql_storage_inventory.py --json` runs at a repository SHA
- **THEN** it emits a versioned deterministic JSON report
- **AND** every finding includes path, line, coupling kind, classification, domain, owner issue and bounded evidence.

### Requirement: Every finding SHALL have a migration classification and owner
Each finding SHALL be classified as `portable SQL`, `adapter-only change`, `query rewrite`, `schema redesign` or `behavior/invariant redesign`, and SHALL be assigned to one owner issue in #391–#400.

#### Scenario: New DuckDB or SQLite coupling appears
- **WHEN** the scanner finds a matching source line in a previously unseen path
- **THEN** the path is still assigned through the explicit path/domain policy or validation fails
- **AND** the new coupling cannot remain silently absent from the migration inventory.

### Requirement: Inventory policy and exclusions SHALL be explicit
The report SHALL disclose scanned-file limits, skipped directories/prefixes and pattern descriptions. Generated/build/vendor state, archived OpenSpec changes and the inventory implementation itself MAY be excluded.

#### Scenario: A binary or generated artifact is encountered
- **WHEN** a file is non-UTF-8, exceeds the bounded text size or is under an excluded generated directory
- **THEN** the scanner skips it according to the disclosed policy
- **AND** does not attempt unbounded or binary parsing.

### Requirement: Repository verification SHALL check inventory integrity
`make verify-postgresql-storage-inventory` SHALL fail when the report schema is invalid, required transitional coupling families are absent unexpectedly, a classification is invalid, an owner is outside #391–#400, a path is unsafe or evidence exceeds the bound.

#### Scenario: A finding loses its migration owner
- **WHEN** inventory validation encounters an absent or invalid owner issue
- **THEN** verification exits non-zero
- **AND** repository consistency cannot pass.

### Requirement: The inventory SHALL evolve at cutover
The #391 scanner SHALL inventory the transitional file-database surface. #400 SHALL replace required transitional-family assertions with checks that prohibit authoritative DuckDB/SQLite use and allow only explicitly isolated optional read-only DuckDB tooling.

#### Scenario: PostgreSQL cutover is complete
- **WHEN** production no longer uses DuckDB or SQLite authority
- **THEN** the inventory policy no longer requires current file-database findings
- **AND** instead fails on any non-allowlisted authoritative file-database coupling.
