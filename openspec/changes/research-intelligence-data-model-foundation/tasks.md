# Tasks: Research Intelligence Data Model Foundation

## 0. Governance

- [ ] 0.1 Keep all data models inside the research-only/no-trading-execution boundary.
- [ ] 0.2 Do not add broker/order/account/portfolio/margin/transfer/allocation/trading execution fields.
- [ ] 0.3 Preserve redaction-by-default logging and artifact references.
- [ ] 0.4 Do not mark runtime capability complete from schema alone.

## 1. Models

- [ ] 1.1 Define `MarketRegimeSnapshot`.
- [ ] 1.2 Define `SectorStrengthSnapshot`.
- [ ] 1.3 Define `SymbolLevelSnapshot`.
- [ ] 1.4 Define `SetupAnalysis`.
- [ ] 1.5 Define `ShortlistCandidate`.
- [ ] 1.6 Define `ResearchScenarioPlan`.
- [ ] 1.7 Define `SetupEvidenceSnapshot`.
- [ ] 1.8 Define `ResearchAnswerAudit`.
- [ ] 1.9 Define shared lineage, freshness, quality, caveat, and correlation fields.

## 2. Warehouse migrations

- [ ] 2.1 Add additive DuckDB migrations for the new research intelligence tables.
- [ ] 2.2 Ensure migrations are idempotent.
- [ ] 2.3 Preserve existing command and assistant behavior.
- [ ] 2.4 Add migration tests.

## 3. Repositories

- [ ] 3.1 Add create/read/list APIs for market regime snapshots.
- [ ] 3.2 Add create/read/list APIs for sector strength snapshots.
- [ ] 3.3 Add create/read/list APIs for symbol level snapshots.
- [ ] 3.4 Add create/read/list APIs for setup analysis records.
- [ ] 3.5 Add create/read/list APIs for shortlist candidates.
- [ ] 3.6 Add create/read/list APIs for scenario plans.
- [ ] 3.7 Add create/read/list APIs for setup evidence snapshots.
- [ ] 3.8 Add create/read/list APIs for research answer audits.

## 4. Validators

- [ ] 4.1 Validate required IDs and dates.
- [ ] 4.2 Validate lineage is present.
- [ ] 4.3 Validate quality status is present where required.
- [ ] 4.4 Validate caveats are present for scenario and evidence objects.
- [ ] 4.5 Validate research-only policy metadata.
- [ ] 4.6 Validate no execution-oriented fields appear.

## 5. Documentation

- [ ] 5.1 Document all object contracts.
- [ ] 5.2 Document repository APIs.
- [ ] 5.3 Document migration strategy.
- [ ] 5.4 Document which future engines depend on each object.

## 6. Validation

- [ ] 6.1 Run `make test-vnalpha`.
- [ ] 6.2 Run `make lint-vnalpha`.
- [ ] 6.3 Run `make verify-r4`.
- [ ] 6.4 Run `openstock-verify --ci`.
- [ ] 6.5 Attach validation evidence to implementation PR.
