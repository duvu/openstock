# Spec Delta: Alpha Discovery TUI MVP Gap Closure

## MODIFIED Requirements

### Requirement: openstock orchestrates the local research system

`openstock` SHALL provide a local workflow for running `vnstock-service`, executing real `vnalpha` jobs, and opening the TUI.

#### Scenario: run daily pipeline commands

Given `vnstock-service` is available  
When the developer runs sync, feature, score, watchlist, and TUI commands  
Then the system SHALL produce or display a daily watchlist using persisted research records.

#### Scenario: no placeholder command output

Given Phase 5 commands are invoked  
When `make features`, `make score`, or `make tui` runs  
Then no command SHALL return a placeholder implementation message.

---

### Requirement: alpha scoring v1 produces research candidates

`vnalpha` SHALL score symbols deterministically and persist candidate records as the authoritative scoring output.

#### Scenario: score candidate

Given feature snapshots exist  
When scoring is executed  
Then trend, relative strength, volume, base/compression, breakout proximity, and risk/data quality scores SHALL be computed.

#### Scenario: persist candidate score

Given a candidate score is computed  
When scoring persistence is executed  
Then `candidate_score` SHALL store symbol, date, score, candidate class, setup type, score breakdown, evidence, risk flags, and lineage.

#### Scenario: classify candidate with canonical taxonomy

Given a score is computed  
When candidate class is assigned  
Then the class SHALL be one of the Phase 5 canonical candidate classes documented for scoring engine v1.

#### Scenario: evidence and risk flags are included

Given a candidate is generated  
When it is persisted  
Then evidence, risk flags, setup type, and lineage SHALL be stored with the score and be readable by the TUI.

---

### Requirement: daily watchlist is generated

`vnalpha` SHALL generate a daily watchlist from persisted candidate scores.

#### Scenario: generate watchlist from candidate scores

Given candidate scores exist for a date  
When `vnalpha watchlist --date <date>` is executed  
Then the system SHALL rank persisted candidates and persist the daily watchlist.

#### Scenario: no candidate result is explicit

Given no symbol meets candidate criteria  
When a watchlist is generated  
Then the system SHALL return an explicit no-candidate result rather than failing silently.

---

### Requirement: TUI is the Phase 5 user interface

`vnalpha` SHALL provide a terminal user interface for the daily research workflow using persisted warehouse records.

#### Scenario: open TUI

Given a local warehouse exists  
When `vnalpha tui --date <date>` is executed  
Then a TUI SHALL open and show the daily watchlist or an explicit empty-state message for that date.

#### Scenario: inspect candidate

Given a candidate is selected in the watchlist  
When the user presses Enter  
Then the TUI SHALL show persisted symbol detail including score breakdown, evidence, risk flags, and lineage.

#### Scenario: inspect candidate without recomputation mismatch

Given a persisted candidate score exists  
When the TUI shows symbol detail  
Then the score shown SHALL match the persisted `candidate_score` record.

---

### Requirement: Phase 5 prepares Phase 6 outcome tracking

Phase 5 SHALL persist enough identifiers and timestamps to support future outcome tracking.

#### Scenario: candidate has stable identity

Given a candidate is generated  
When it is persisted  
Then it SHALL have date, symbol, setup type, score, evidence, and lineage sufficient for later forward-return measurement.

#### Scenario: watchlist has stable ranking

Given a watchlist is generated  
When it is persisted  
Then rank, score, candidate class, and generated timestamp SHALL be stored.

---

## ADDED Requirements

### Requirement: Phase 5 commands share deterministic date resolution

`vnalpha` SHALL resolve date arguments consistently across CLI, scoring, watchlist, and TUI.

#### Scenario: resolve today

Given the user passes `today`  
When a Phase 5 command resolves the date  
Then the same canonical date string SHALL be used through the command execution.

#### Scenario: resolve explicit date

Given the user passes an ISO date string  
When a Phase 5 command resolves the date  
Then the same explicit date SHALL be used through the command execution.

#### Scenario: reject invalid date

Given the user passes an invalid date value  
When a Phase 5 command resolves the date  
Then the command SHALL fail clearly before writing warehouse records.

---

### Requirement: Phase 5 closure is validated end to end

Phase 5 SHALL include tests proving the daily local research workflow works through CLI and persisted warehouse records.

#### Scenario: CLI workflow succeeds on fixture warehouse

Given a test warehouse with enough canonical OHLCV data  
When feature build, scoring, and watchlist CLI commands are executed  
Then feature snapshots, candidate scores, and daily watchlist rows SHALL be persisted.

#### Scenario: TUI can read persisted research records

Given daily watchlist and candidate score rows exist  
When TUI data-loading paths are exercised  
Then watchlist and candidate detail data SHALL be readable without recomputing a different score.

#### Scenario: research language boundary is covered

Given user-facing Phase 5 CLI and TUI strings exist  
When boundary tests scan those strings  
Then outputs SHALL use research/watchlist language and avoid execution-style instructions.
