## MODIFIED Requirements

### Requirement: System shall ensure data readiness before one-symbol analysis

OpenStock SHALL automatically check and provision all persisted artifacts required
by the requested one-symbol analysis before executing its read tool.

#### Scenario: Candidate score exists and is fresh

- **GIVEN** `candidate_score(symbol, target_date)` exists
- **AND** supporting data freshness is sufficient
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL use the existing score without running sync/build/score actions
- **AND** SHALL return an ensure-data result with status `READY` and a cache-hit action.

#### Scenario: Candidate score is missing but features exist

- **GIVEN** `feature_snapshot(symbol, target_date)` exists
- **AND** `candidate_score(symbol, target_date)` is missing
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL generate a candidate score for that symbol/date
- **AND** then run the existing explain flow.

#### Scenario: Feature snapshot is missing but canonical data is sufficient

- **GIVEN** canonical OHLCV exists with sufficient history for the symbol
- **AND** `feature_snapshot(symbol, target_date)` is missing
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL build features for the symbol
- **AND** generate a candidate score
- **AND** then run the existing explain flow.

#### Scenario: Canonical data is missing

- **GIVEN** canonical OHLCV is missing or insufficient for the symbol
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL fetch symbol OHLCV from vnstock-service
- **AND** build canonical OHLCV for the symbol
- **AND** build features
- **AND** generate a candidate score
- **AND** then run the existing explain flow.

#### Scenario: Benchmark data is missing

- **GIVEN** the requested symbol has data
- **BUT** benchmark OHLCV is missing or insufficient
- **WHEN** the user requests `/explain SYMBOL`
- **THEN** the system SHALL fetch benchmark OHLCV
- **AND** build benchmark canonical OHLCV
- **AND** build symbol features using the benchmark where available
- **AND** report benchmark freshness in the result.

#### Scenario: Deep analysis requires market and sector snapshots

- **GIVEN** a requested deep analysis includes market-regime or sector-strength context
- **AND** the corresponding snapshot is missing or stale for the effective as-of bar date
- **WHEN** the user requests `/analyze SYMBOL` with that context or the assistant executes `analysis.deep_symbol`
- **THEN** deterministic application code SHALL provision the required snapshot before the read tool executes
- **AND** SHALL return a typed per-artifact readiness result
- **AND** the assistant model SHALL NOT select or invoke any data-fetch action.

#### Scenario: A required deep artifact cannot be made ready

- **GIVEN** a required deep-analysis artifact remains unavailable after provisioning
- **WHEN** readiness completes
- **THEN** the system SHALL not invoke the deep read tool with that incomplete required input set
- **AND** SHALL return the failed artifact, reason, and explicit manual command.
