# Tasks: Market Regime and Sector Context

## 0. Governance

- [x] 0.1 Keep outputs research-only.
- [x] 0.2 Do not generate allocation, portfolio, order, broker, margin, or trading execution instructions.
- [x] 0.3 Include caveats for insufficient breadth/sector data.

## 1. Data and repositories

- [x] 1.1 Add or reuse `MarketRegimeSnapshot` persistence.
- [x] 1.2 Add or reuse `SectorStrengthSnapshot` persistence.
- [x] 1.3 Add repository APIs for latest/as-of-date regime.
- [x] 1.4 Add repository APIs for ranked sector strength.
- [x] 1.5 Add repository APIs for symbol-sector alignment.

## 2. Regime builder

- [x] 2.1 Compute index trend context.
- [x] 2.2 Compute index volatility context.
- [x] 2.3 Compute breadth metrics from available symbols.
- [x] 2.4 Assign coarse market regime state.
- [x] 2.5 Persist lineage and methodology version.
- [x] 2.6 Emit quality warnings for incomplete data.

## 3. Sector builder

- [x] 3.1 Group symbols by sector metadata.
- [x] 3.2 Compute sector return and relative strength windows.
- [x] 3.3 Compute sector breadth proxies.
- [x] 3.4 Rank sectors deterministically.
- [x] 3.5 Assign rotation state.
- [x] 3.6 Persist sector snapshots.

## 4. Commands

- [x] 4.1 Add `/market-regime`.
- [x] 4.2 Add `/sector-strength`.
- [x] 4.3 Add `/sector-strength SYMBOL` for symbol-sector alignment.
- [x] 4.4 Add help text and examples.
- [x] 4.5 Render tables and caveats in OutputStream.

## 5. Assistant tools

- [x] 5.1 Add `market.get_regime` tool.
- [x] 5.2 Add `sector.get_strength` tool.
- [x] 5.3 Add `sector.get_symbol_alignment` tool.
- [x] 5.4 Add assistant intents for market and sector context.
- [x] 5.5 Add synthesis templates.

## 6. Observability and evaluation

- [x] 6.1 Emit `MARKET_REGIME_BUILT`.
- [x] 6.2 Emit `SECTOR_STRENGTH_BUILT`.
- [x] 6.3 Link events to correlation ID.
- [x] 6.4 Add golden examples for regime and sector answers.

## 7. Validation

- [x] 7.1 Test regime snapshot creation.
- [x] 7.2 Test sector ranking creation.
- [x] 7.3 Test insufficient data caveats.
- [x] 7.4 Test no trading/execution language.
- [x] 7.5 Run `make test-vnalpha`, `make lint-vnalpha`, `make verify-r4`, and `openstock-verify --ci`.
