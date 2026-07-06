# Tasks: Phase 5 Alpha Discovery TUI MVP

## 0. System baseline

- [x] Confirm `openstock` has `vnstock` and `vnalpha` submodules.
- [x] Confirm `vnstock-service` can start locally.
- [x] Confirm required `vnstock-service` data endpoints exist or are planned.
- [x] Confirm `vnalpha` is not using Streamlit for Phase 5.
- [x] Confirm Phase 5 output is a TUI daily watchlist, not a web dashboard.

## 1. openstock orchestration

- [x] Add or update `openstock/Makefile`.
- [x] Add `make up-vnstock`.
- [x] Add `make sync`.
- [x] Add `make features`.
- [x] Add `make score`.
- [x] Add `make tui`.
- [x] Add or update `openstock/.env.example`.
- [x] Add or update `openstock/docker-compose.yml` for `vnstock-service`.
- [x] Document local startup in `openstock/docs/ROADMAP.md` or dedicated runbook.

## 2. vnstock operational contract

- [x] Confirm `GET /v1/reference/symbols` works.
- [x] Confirm `GET /v1/equity/ohlcv` works.
- [x] Confirm `GET /v1/equity/quote` works or document as deferred.
- [x] Confirm `GET /v1/index/ohlcv` works or document as deferred.
- [x] Confirm `GET /v1/providers/health` works.
- [x] Confirm `GET /v1/providers/capabilities` works.
- [x] Add response examples for OHLCV, symbols, and provider health.
- [x] Add smoke test for FPT OHLCV.
- [x] Add smoke test for VNINDEX OHLCV if endpoint is available.
- [x] Add smoke test for reference symbols.

## 3. vnalpha core skeleton

- [x] Create or update `vnalpha/pyproject.toml`.
- [x] Add `src/vnalpha/cli.py`.
- [x] Add `src/vnalpha/core/config.py`.
- [x] Add `src/vnalpha/core/logging.py`.
- [x] Add `src/vnalpha/core/types.py`.
- [x] Add `configs/services.yaml`.
- [x] Add `configs/universe.yaml`.
- [x] Add `configs/scoring.yaml`.
- [x] Add test bootstrap.
- [x] Add `vnalpha --help` test.

## 4. vnstock client in vnalpha

- [x] Add `src/vnalpha/clients/vnstock/client.py`.
- [x] Add `src/vnalpha/clients/vnstock/schemas.py`.
- [x] Add `src/vnalpha/clients/vnstock/errors.py`.
- [x] Implement `get_symbols()`.
- [x] Implement `get_equity_ohlcv()`.
- [x] Implement `get_equity_quote()` if service endpoint is available.
- [x] Implement `get_index_ohlcv()` if service endpoint is available.
- [x] Implement `get_provider_health()`.
- [x] Implement `get_provider_capabilities()`.
- [x] Preserve provider lineage and quality metadata.
- [x] Add mocked vnstock-service tests.
- [x] Ensure vnalpha contains no provider-specific data access logic.

## 5. DuckDB research warehouse

- [x] Add `src/vnalpha/warehouse/connection.py`.
- [x] Add `src/vnalpha/warehouse/schema.py`.
- [x] Add `src/vnalpha/warehouse/migrations.py`.
- [x] Add `src/vnalpha/warehouse/repositories.py`.
- [x] Create `ingestion_run` table.
- [x] Create `symbol_master` table.
- [x] Create `market_ohlcv_raw` table.
- [x] Create `canonical_ohlcv` table.
- [x] Create `feature_snapshot` table.
- [x] Create `candidate_score` table.
- [x] Create `daily_watchlist` table.
- [x] Create `rejected_symbol` table.
- [x] Add schema creation tests.

## 6. Ingestion jobs

- [x] Add `src/vnalpha/ingestion/sync_symbols.py`.
- [x] Add `src/vnalpha/ingestion/sync_ohlcv.py`.
- [x] Add `src/vnalpha/ingestion/build_canonical.py`.
- [x] Implement `vnalpha sync symbols`.
- [x] Implement `vnalpha sync ohlcv --universe VN30 --start YYYY-MM-DD`.
- [x] Implement `vnalpha build canonical`.
- [x] Store raw OHLCV response lineage.
- [x] Store rejected rows/symbols with reason.
- [x] Add fixture-based tests.

## 7. Feature store v1

- [x] Add `src/vnalpha/features/price.py`.
- [x] Add `src/vnalpha/features/volume.py`.
- [x] Add `src/vnalpha/features/volatility.py`.
- [x] Add `src/vnalpha/features/relative_strength.py`.
- [x] Add `src/vnalpha/features/build_features.py`.
- [x] Compute MA20, MA50, MA100.
- [x] Compute MA20 and MA50 slopes.
- [x] Compute volume MA20 and volume ratio.
- [x] Compute ATR14.
- [x] Compute return_20d and return_60d.
- [x] Compute RS20 and RS60 vs VNINDEX.
- [x] Compute distance_to_ma20.
- [x] Compute distance_to_52w_high.
- [x] Compute base_range_30d.
- [x] Compute close_strength.
- [x] Compute volatility_20d.
- [x] Add synthetic dataset tests.

## 8. Alpha scoring v1

- [x] Add `src/vnalpha/scoring/rules.py`.
- [x] Add `src/vnalpha/scoring/score.py`.
- [x] Add `src/vnalpha/scoring/risk_flags.py`.
- [x] Add `src/vnalpha/scoring/generate_watchlist.py`.
- [x] Implement trend score.
- [x] Implement relative strength score.
- [x] Implement volume score.
- [x] Implement base/compression score.
- [x] Implement breakout proximity score.
- [x] Implement risk/data quality score.
- [x] Implement candidate class mapping.
- [x] Implement setup type detection v1.
- [x] Implement risk flags.
- [x] Persist `candidate_score`.
- [x] Persist `daily_watchlist`.
- [x] Add scoring tests with synthetic features.

## 9. TUI MVP

- [x] Add `src/vnalpha/tui/app.py`.
- [x] Add home screen.
- [x] Add daily watchlist screen.
- [x] Add symbol detail screen.
- [x] Add rejected symbols screen.
- [x] Add provider/data quality screen.
- [x] Add score table widget.
- [x] Add risk panel widget.
- [x] Add optional mini chart widget.
- [x] Implement keyboard navigation.
- [x] Implement refresh action.
- [x] Implement symbol drill-down.
- [x] Add TUI smoke tests.

## 10. Safety and language boundary

- [x] Ensure API/TUI uses research language only.
- [x] Ensure no buy/sell/order/portfolio language appears in user-facing strings.
- [x] Ensure candidate output includes evidence and risk flags.
- [x] Ensure candidate output includes lineage.
- [x] Add tests for forbidden terms in candidate output strings.

## 11. End-to-end validation

- [x] `make up-vnstock` starts data service.
- [x] `vnalpha sync symbols` succeeds for VN30 or configured universe.
- [x] `vnalpha sync ohlcv --universe VN30 --start 2024-01-01` succeeds.
- [x] `vnalpha build canonical` succeeds.
- [x] `vnalpha build features --date today` succeeds.
- [x] `vnalpha score --date today` succeeds.
- [x] `vnalpha watchlist --date today` returns candidates or explicit no-candidate result.
- [x] `vnalpha tui` opens daily watchlist.

## Completion checklist

- [x] Phase 5 daily watchlist is usable in terminal.
- [x] Phase 5 TUI can drill into symbol detail.
- [x] Phase 5 stores lineage and data quality.
- [x] Phase 5 excludes broker/account/order/portfolio functionality.
- [x] Phase 5 is ready for Phase 6 outcome tracking.
