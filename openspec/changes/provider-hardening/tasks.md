# Tasks: Provider Hardening

## 1. Provider Models

- [x] Add `vnstock/core/provider/models.py`
- [x] Implement `ProviderCapability`
- [x] Implement `ProviderHealth`
- [x] Implement `ProviderComparisonReport`
- [x] Implement structured provider issue model
- [x] Add unit tests for model serialization

## 2. Capability Registry

- [x] Add `vnstock/core/provider/capabilities.py`
- [x] Register KBS capabilities
- [x] Register VCI capabilities
- [x] Register DNSE capabilities
- [x] Register MSN capabilities where applicable
- [x] Register FMP capabilities where applicable
- [x] Register FMarket capabilities where applicable
- [x] Add helper to query providers by dataset type, asset class, method, and interval
- [x] Add tests for unsupported capability behavior

## 3. Contract Fixture Structure

- [x] Add `tests/fixtures/providers/dnse/`
- [x] Add `tests/fixtures/providers/kbs/`
- [x] Add `tests/fixtures/providers/vci/`
- [x] Add raw sample fixtures for OHLCV daily
- [x] Add raw sample fixtures for price board
- [x] Add raw sample fixtures for intraday trades
- [x] Add normalized expected output fixtures where practical
- [x] Document fixture update process

## 4. Provider Contract Tests

- [x] Add `tests/contracts/providers/test_dnse_contracts.py`
- [x] Add `tests/contracts/providers/test_kbs_contracts.py`
- [x] Add `tests/contracts/providers/test_vci_contracts.py`
- [x] Validate raw fixture parsing
- [x] Validate normalized OHLCV schema
- [x] Validate normalized price board schema
- [x] Validate normalized intraday schema
- [x] Ensure contract tests do not call live endpoints

## 5. Live Smoke Test Infrastructure

- [x] Add `tests/live/providers/`
- [x] Add `VNSTOCK_LIVE_TESTS` gating
- [x] Add `VNSTOCK_LIVE_PROVIDERS` filtering
- [x] Add `VNSTOCK_LIVE_SYMBOLS` filtering
- [x] Add pytest markers: `live`, `provider`, `provider_dnse`, `provider_kbs`, `provider_vci`
- [x] Add skip behavior when live tests are disabled
- [x] Add documentation for safe live test execution

## 6. Live Smoke Tests

- [x] Add DNSE live OHLCV smoke test
- [x] Add DNSE live price board smoke test
- [x] Add DNSE live intraday smoke test where endpoint supports it
- [x] Add KBS live OHLCV smoke test
- [x] Add KBS live price board smoke test
- [x] Add VCI live OHLCV smoke test
- [x] Add VCI live price board smoke test
- [x] Keep all live tests small and rate-limit friendly

## 7. Schema Drift Detection

- [x] Add `vnstock/core/provider/drift.py`
- [x] Implement raw schema drift detector
- [x] Implement normalized schema drift detector
- [x] Classify drift as `none`, `minor`, or `major`
- [x] Detect missing required raw fields
- [x] Detect missing required normalized columns
- [x] Detect dtype category drift
- [x] Add unit tests with drift fixtures

## 8. Cross-Provider Comparison

- [x] Add `vnstock/core/provider/compare.py`
- [x] Implement OHLCV comparison across KBS, VCI, DNSE
- [x] Implement missing-date comparison
- [x] Implement price difference summary
- [x] Implement volume difference summary
- [x] Implement price-scale mismatch detection
- [x] Add configurable tolerances
- [x] Add tests using synthetic provider outputs

## 9. Provider Health Scoring

- [x] Add `vnstock/core/provider/health.py`
- [x] Implement health statuses: `healthy`, `degraded`, `failing`, `unknown`
- [x] Convert contract test results into health signals
- [x] Convert live smoke test results into health signals
- [x] Track latency, error rate, schema status, freshness status, and issues
- [x] Add tests for health state transitions

## 10. Router Integration

- [x] Update `vnstock/core/router.py` to optionally use provider health state
- [x] Prefer healthy providers
- [x] Allow degraded providers only when necessary
- [x] Skip failing providers unless caller forces source
- [x] Add `ignore_provider_health` option
- [x] Add `include_provider_diagnostics` option
- [x] Add router tests for health-aware provider selection

## 11. Provider Capability Matrix

- [x] Add matrix generator utility
- [x] Generate `docs/PROVIDER_MATRIX.md`
- [x] Generate machine-readable provider matrix JSON artifact
- [x] Include provider, dataset type, asset class, method, intervals, auth requirement, contract status, live status, notes
- [x] Add tests for matrix generation

## 12. CI Integration

- [x] Add contract tests to normal CI
- [x] Ensure live tests are skipped in normal CI
- [x] Add optional scheduled/manual live smoke workflow
- [x] Add marker docs to `pytest.ini`
- [x] Fail CI on contract drift
- [x] Do not fail normal CI on unavailable live providers unless explicitly enabled

## 13. Documentation

- [x] Add `docs/PROVIDER_HARDENING.md`
- [x] Document contract tests
- [x] Document live smoke tests
- [x] Document provider health statuses
- [x] Document cross-provider comparison
- [x] Document provider matrix generation
- [x] Document how to add a new provider safely

## 14. Rollout Plan

- [x] Start with DNSE contract fixtures and tests
- [x] Add KBS and VCI fixtures next
- [x] Add OHLCV comparison first
- [x] Add price board comparison second
- [x] Add intraday comparison last
- [x] Integrate provider health with router only after contract tests are stable
