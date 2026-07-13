# Tasks: Research Intelligence Data Model Foundation

## 0. Governance

- [x] 0.1 Keep all data models inside the research-only/no-trading-execution boundary.
- [x] 0.2 Do not add broker/order/account/portfolio/margin/transfer/allocation/trading execution fields.
- [x] 0.3 Preserve redaction-by-default logging and artifact references.
- [x] 0.4 Do not mark runtime capability complete from schema alone.

## 1. Models

- [x] 1.1 Define `MarketRegimeSnapshot`.
- [x] 1.2 Define `SectorStrengthSnapshot`.
- [x] 1.3 Define `SymbolLevelSnapshot`.
- [x] 1.4 Define `SetupAnalysis`.
- [x] 1.5 Define `ShortlistCandidate`.
- [x] 1.6 Define `ResearchScenarioPlan`.
- [x] 1.7 Define `SetupEvidenceSnapshot`.
- [x] 1.8 Define `ResearchAnswerAudit`.
- [x] 1.9 Define shared lineage, freshness, quality, caveat, and correlation fields.

## 2. Warehouse migrations

- [x] 2.1 Add additive DuckDB migrations for the new research intelligence tables.
- [x] 2.2 Ensure migrations are idempotent.
- [x] 2.3 Preserve existing command and assistant behavior.
- [x] 2.4 Add migration tests.

## 3. Repositories

- [x] 3.1 Add create/read/list APIs for market regime snapshots.
- [x] 3.2 Add create/read/list APIs for sector strength snapshots.
- [x] 3.3 Add create/read/list APIs for symbol level snapshots.
- [x] 3.4 Add create/read/list APIs for setup analysis records.
- [x] 3.5 Add create/read/list APIs for shortlist candidates.
- [x] 3.6 Add create/read/list APIs for scenario plans.
- [x] 3.7 Add create/read/list APIs for setup evidence snapshots.
- [x] 3.8 Add create/read/list APIs for research answer audits.

## 4. Validators

- [x] 4.1 Validate required IDs and dates.
- [x] 4.2 Validate lineage is present.
- [x] 4.3 Validate quality status is present where required.
- [x] 4.4 Validate caveats are present for scenario and evidence objects.
- [x] 4.5 Validate research-only policy metadata.
- [x] 4.6 Validate no execution-oriented fields appear.

## 5. Documentation

- [x] 5.1 Document all object contracts.
- [x] 5.2 Document repository APIs.
- [x] 5.3 Document migration strategy.
- [x] 5.4 Document which future engines depend on each object.

## 6. Validation

- [x] 6.1 Run `make test-vnalpha`.
- [x] 6.2 Run `make lint-vnalpha`.
- [x] 6.3 Run `make verify-r4`.
- [x] 6.4 Run `openstock-verify --ci`.
- [ ] 6.5 Attach validation evidence to implementation PR.
