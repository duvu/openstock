# Tasks: Phase 5 Alpha Discovery TUI MVP

## 0. System baseline

- [ ] Confirm `openstock` has `vnstock` and `vnalpha` submodules.
- [ ] Confirm `vnstock-service` can start locally.
- [ ] Confirm required `vnstock-service` data endpoints exist or are planned.
- [ ] Confirm `vnalpha` is not using Streamlit for Phase 5.
- [ ] Confirm Phase 5 output is a TUI daily watchlist, not a web dashboard.

## 1. openstock orchestration

- [ ] Add or update `openstock/Makefile`.
- [ ] Add `make up-vnstock`.
- [ ] Add `make sync`.
- [ ] Add `make features`.
- [ ] Add `make score`.
- [ ] Add `make tui`.
- [ ] Add or update `openstock/.env.example`.
- [ ] Add or update `openstock/docker-compose.yml` for `vnstock-service`.
- [ ] Document local startup in `openstock/docs/ROADMAP.md` or dedicated runbook.

## 2. vnstock operational contract

- [ ] Confirm `GET /v1/reference/symbols` works.
- [ ] Confirm `GET /v1/equity/ohlcv` works.
- [ ] Confirm `GET /v1/equity/quote` works or document as deferred.
- [ ] Confirm `GET /v1/index/ohlcv` works or document as deferred.
- [ ] Confirm `GET /v1/providers/health` works.
- [ ] Confirm `GET /v1/providers/capabilities` works.
- [ ] Add response examples for OHLCV, symbols, and provider health.
- [ ] Add smoke test for FPT OHLCV.
- [ ] Add smoke test for VNINDEX OHLCV if endpoint is available.
- [ ] Add smoke test for reference symbols.

## 3. vnalpha core skeleton

- [ ] Create or update `vnalpha/pyproject.toml`.
- [ ] Add `src/vnalpha/cli.py`.
- [ ] Add `src/vnalpha/core/config.py`.
- [ ] Add `src/vnalpha/core/logging.py`.
- [ ] Add `src/vnalpha/core/types.py`.
- [ ] Add `configs/services.yaml`.
- [ ] Add `configs/universe.yaml`.
- [ ] Add `configs/scoring.yaml`.
- [ ] Add test bootstrap.
- [ ] Add `vnalpha --help` test.

## 4. vnstock client in vnalpha

- [ ] Add `src/vnalpha/clients/vnstock/client.py`.
- [ ] Add `src/vnalpha/clients/vnstock/schemas.py`.
- [ ] Add `src/vnalpha/clients/vnstock/errors.py`.
- [ ] Implement `get_symbols()`.
- [ ] Implement `get_equity_ohlcv()`.
- [ ] Implement `get_equity_quote()` if service endpoint is available.
- [ ] Implement `get_index_ohlcv()` if service endpoint is available.
- [ ] Implement `get_provider_health()`.
- [ ] Implement `get_provider_capabilities()`.
- [ ] Preserve provider lineage and quality metadata.
- [ ] Add mocked vnstock-service tests.
- [ ] Ensure vnalpha contains no provider-specific data access logic.

## 5. DuckDB research warehouse

- [ ] Add `src/vnalpha/warehouse/connection.py`.
- [ ] Add `src/vnalpha/warehouse/schema.py`.
- [ ] Add `src/vnalpha/warehouse/migrations.py`.
- [ ] Add `src/vnalpha/warehouse/repositories.py`.
- [ ] Create `ingestion_run` table.
- [ ] Create `symbol_master` table.
- [ ] Create `market_ohlcv_raw` table.
- [ ] Create `canonical_ohlcv` table.
- [ ] Create `feature_snapshot` table.
- [ ] Create `candidate_score` table.
- [ ] Create `daily_watchlist` table.
- [ ] Create `rejected_symbol` table.
- [ ] Add schema creation tests.

## 6. Ingestion jobs

- [ ] Add `src/vnalpha/ingestion/sync_symbols.py`.
- [ ] Add `src/vnalpha/ingestion/sync_ohlcv.py`.
- [ ] Add `src/vnalpha/ingestion/build_canonical.py`.
- [ ] Implement `vnalpha sync symbols`.
- [ ] Implement `vnalpha sync ohlcv --universe VN30 --start YYYY-MM-DD`.
- [ ] Implement `vnalpha build canonical`.
- [ ] Store raw OHLCV response lineage.
- [ ] Store rejected rows/symbols with reason.
- [ ] Add fixture-based tests.

## 7. Feature store v1

- [ ] Add `src/vnalpha/features/price.py`.
- [ ] Add `src/vnalpha/features/volume.py`.
- [ ] Add `src/vnalpha/features/volatility.py`.
- [ ] Add `src/vnalpha/features/relative_strength.py`.
- [ ] Add `src/vnalpha/features/build_features.py`.
- [ ] Compute MA20, MA50, MA100.
- [ ] Compute MA20 and MA50 slopes.
- [ ] Compute volume MA20 and volume ratio.
- [ ] Compute ATR14.
- [ ] Compute return_20d and return_60d.
- [ ] Compute RS20 and RS60 vs VNINDEX.
- [ ] Compute distance_to_ma20.
- [ ] Compute distance_to_52w_high.
- [ ] Compute base_range_30d.
- [ ] Compute close_strength.
- [ ] Compute volatility_20d.
- [ ] Add synthetic dataset tests.

## 8. Alpha scoring v1

- [ ] Add `src/vnalpha/scoring/rules.py`.
- [ ] Add `src/vnalpha/scoring/score.py`.
- [ ] Add `src/vnalpha/scoring/risk_flags.py`.
- [ ] Add `src/vnalpha/scoring/generate_watchlist.py`.
- [ ] Implement trend score.
- [ ] Implement relative strength score.
- [ ] Implement volume score.
- [ ] Implement base/compression score.
- [ ] Implement breakout proximity score.
- [ ] Implement risk/data quality score.
- [ ] Implement candidate class mapping.
- [ ] Implement setup type detection v1.
- [ ] Implement risk flags.
- [ ] Persist `candidate_score`.
- [ ] Persist `daily_watchlist`.
- [ ] Add scoring tests with synthetic features.

## 9. TUI MVP

- [ ] Add `src/vnalpha/tui/app.py`.
- [ ] Add home screen.
- [ ] Add daily watchlist screen.
- [ ] Add symbol detail screen.
- [ ] Add rejected symbols screen.
- [ ] Add provider/data quality screen.
- [ ] Add score table widget.
- [ ] Add risk panel widget.
- [ ] Add optional mini chart widget.
- [ ] Implement keyboard navigation.
- [ ] Implement refresh action.
- [ ] Implement symbol drill-down.
- [ ] Add TUI smoke tests.

## 10. Safety and language boundary

- [ ] Ensure API/TUI uses research language only.
- [ ] Ensure no buy/sell/order/portfolio language appears in user-facing strings.
- [ ] Ensure candidate output includes evidence and risk flags.
- [ ] Ensure candidate output includes lineage.
- [ ] Add tests for forbidden terms in candidate output strings.

## 11. End-to-end validation

- [ ] `make up-vnstock` starts data service.
- [ ] `vnalpha sync symbols` succeeds for VN30 or configured universe.
- [ ] `vnalpha sync ohlcv --universe VN30 --start 2024-01-01` succeeds.
- [ ] `vnalpha build canonical` succeeds.
- [ ] `vnalpha build features --date today` succeeds.
- [ ] `vnalpha score --date today` succeeds.
- [ ] `vnalpha watchlist --date today` returns candidates or explicit no-candidate result.
- [ ] `vnalpha tui` opens daily watchlist.

## Completion checklist

- [ ] Phase 5 daily watchlist is usable in terminal.
- [ ] Phase 5 TUI can drill into symbol detail.
- [ ] Phase 5 stores lineage and data quality.
- [ ] Phase 5 excludes broker/account/order/portfolio functionality.
- [ ] Phase 5 is ready for Phase 6 outcome tracking.
