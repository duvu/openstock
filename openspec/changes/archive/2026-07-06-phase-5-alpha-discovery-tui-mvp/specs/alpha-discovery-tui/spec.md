# Spec: Alpha Discovery TUI MVP

## ADDED Requirements

### Requirement: openstock orchestrates the local research system

`openstock` SHALL provide a local workflow for running `vnstock-service`, executing `vnalpha` jobs, and opening the TUI.

#### Scenario: start vnstock service

Given a developer is in the `openstock` repository  
When they run `make up-vnstock`  
Then `vnstock-service` SHALL start locally.

#### Scenario: run daily pipeline commands

Given `vnstock-service` is available  
When the developer runs sync, feature, score, and TUI commands  
Then the system SHALL produce or display a daily watchlist.

---

### Requirement: vnalpha consumes vnstock-service only through HTTP

`vnalpha` SHALL consume market data through the `vnstock-service` HTTP contract and SHALL NOT embed provider-specific data access logic.

#### Scenario: fetch symbols

Given `vnstock-service` is configured  
When `vnalpha sync symbols` is executed  
Then `vnalpha` SHALL call the reference symbols endpoint and persist symbol metadata.

#### Scenario: fetch OHLCV

Given a configured universe  
When `vnalpha sync ohlcv` is executed  
Then `vnalpha` SHALL call the equity OHLCV endpoint for each symbol and preserve provider lineage.

#### Scenario: provider internals are not used

Given `vnalpha` needs market data  
When data is fetched  
Then `vnalpha` SHALL NOT import or instantiate provider-specific `vnstock` provider classes.

---

### Requirement: local research warehouse exists

`vnalpha` SHALL create and use a DuckDB-based research warehouse for Phase 5.

#### Scenario: initialize warehouse

Given a new local environment  
When `vnalpha init` is executed  
Then DuckDB tables SHALL be created for ingestion runs, symbols, raw OHLCV, canonical OHLCV, features, candidate scores, daily watchlists, and rejected symbols.

#### Scenario: raw lineage is preserved

Given an OHLCV response is received from `vnstock-service`  
When it is stored  
Then provider, quality status, diagnostics, fetched timestamp, and ingestion run ID SHALL be preserved.

#### Scenario: canonical OHLCV is reproducible

Given raw OHLCV exists  
When canonical build is executed for a date or range  
Then canonical OHLCV SHALL be reproducible and rejected rows SHALL include rejection reasons.

---

### Requirement: deterministic feature store v1

`vnalpha` SHALL compute deterministic features from canonical OHLCV only.

#### Scenario: compute price trend features

Given canonical OHLCV exists  
When feature build is executed  
Then MA20, MA50, MA100, and moving-average slopes SHALL be computed where enough history exists.

#### Scenario: compute volume and volatility features

Given canonical OHLCV exists  
When feature build is executed  
Then volume ratio, ATR14, and volatility features SHALL be computed where enough history exists.

#### Scenario: compute relative strength features

Given symbol OHLCV and benchmark OHLCV exist  
When feature build is executed  
Then relative strength features versus the configured benchmark SHALL be computed.

---

### Requirement: alpha scoring v1 produces research candidates

`vnalpha` SHALL score symbols deterministically and produce research candidate records.

#### Scenario: score candidate

Given feature snapshots exist  
When scoring is executed  
Then trend, relative strength, volume, base/compression, breakout proximity, and risk/data quality scores SHALL be computed.

#### Scenario: classify candidate

Given a score is computed  
When candidate class is assigned  
Then the class SHALL be one of STRONG_CANDIDATE, WATCH_CANDIDATE, WEAK_CANDIDATE, or IGNORE.

#### Scenario: evidence and risk flags are included

Given a candidate is generated  
When it is persisted  
Then evidence, risk flags, setup type, and lineage SHALL be stored with the score.

---

### Requirement: daily watchlist is generated

`vnalpha` SHALL generate a daily watchlist from candidate scores.

#### Scenario: generate watchlist

Given candidate scores exist for a date  
When `vnalpha watchlist --date <date>` is executed  
Then the system SHALL rank candidates and persist the daily watchlist.

#### Scenario: no candidate result is explicit

Given no symbol meets candidate criteria  
When a watchlist is generated  
Then the system SHALL return an explicit no-candidate result rather than failing silently.

---

### Requirement: TUI is the Phase 5 user interface

`vnalpha` SHALL provide a terminal user interface for the daily research workflow.

#### Scenario: open TUI

Given a local warehouse exists  
When `vnalpha tui` is executed  
Then a TUI SHALL open and show the daily watchlist or an explicit empty-state message.

#### Scenario: inspect candidate

Given a candidate is selected in the watchlist  
When the user presses Enter  
Then the TUI SHALL show symbol detail including score breakdown, evidence, risk flags, and lineage.

#### Scenario: inspect rejected symbols

Given symbols were rejected during filtering or scoring  
When the user opens the rejected-symbols screen  
Then the TUI SHALL show symbols and rejection reasons.

#### Scenario: inspect provider health

Given provider health data is available  
When the user opens the provider-health screen  
Then the TUI SHALL show provider and data-quality status.

---

### Requirement: research language boundary is enforced

The Phase 5 system SHALL use research/watchlist language only and SHALL NOT present outputs as trading instructions.

#### Scenario: candidate language is used

Given a watchlist item is displayed  
When the user reads the item  
Then the item SHALL use terms such as candidate, watchlist, monitor, setup, evidence, risk flag, and lineage.

#### Scenario: trading instruction language is forbidden

Given API, CLI, or TUI output is generated  
When user-facing text is checked  
Then it SHALL NOT include buy/sell/order/portfolio execution language.

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
