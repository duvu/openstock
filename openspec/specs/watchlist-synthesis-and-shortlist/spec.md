# watchlist-synthesis-and-shortlist Specification

## Purpose
TBD - created by archiving change watchlist-synthesis-and-shortlist. Update Purpose after archive.
## Requirements
### Requirement: Watchlist synthesis

OpenStock SHALL provide a structured synthesis of the daily watchlist.

#### Scenario: User requests watchlist summary

- **WHEN** the user runs `/watchlist-summary`
- **THEN** the system returns size, class distribution, setup distribution, sector clustering, strongest names, near-confirmation names, extended names, risk-flagged names, and next-session research focus

### Requirement: Shortlist generation

OpenStock SHALL generate a narrower shortlist artifact distinct from the broad watchlist.

#### Scenario: User requests shortlist

- **WHEN** the user runs `/shortlist --limit 10`
- **THEN** the system returns ranked candidates with reasons, restraints, conditions, data status, and risk context

### Requirement: Explainable shortlist score

Shortlist ranking SHALL be deterministic and explainable.

#### Scenario: Candidate appears in shortlist

- **WHEN** a symbol is shortlisted
- **THEN** output includes why it was shortlisted and why immediate execution is not implied

### Requirement: Research-only wording

Shortlist output SHALL not be framed as trading instructions.

#### Scenario: Strong candidate appears

- **WHEN** a symbol is ranked highly
- **THEN** the output uses research monitoring language, not buy/sell/order language

