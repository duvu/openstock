# Tasks: Market Regime and Sector Context

## 0. Governance

- [ ] 0.1 Keep outputs research-only.
- [ ] 0.2 Do not generate allocation, portfolio, order, broker, margin, or trading execution instructions.
- [ ] 0.3 Include caveats for insufficient breadth/sector data.

## 1. Data and repositories

- [ ] 1.1 Add or reuse `MarketRegimeSnapshot` persistence.
- [ ] 1.2 Add or reuse `SectorStrengthSnapshot` persistence.
- [ ] 1.3 Add repository APIs for latest/as-of-date regime.
- [ ] 1.4 Add repository APIs for ranked sector strength.
- [ ] 1.5 Add repository APIs for symbol-sector alignment.

## 2. Regime builder

- [ ] 2.1 Compute index trend context.
- [ ] 2.2 Compute index volatility context.
- [ ] 2.3 Compute breadth metrics from available symbols.
- [ ] 2.4 Assign coarse market regime state.
- [ ] 2.5 Persist lineage and methodology version.
- [ ] 2.6 Emit quality warnings for incomplete data.

## 3. Sector builder

- [ ] 3.1 Group symbols by sector metadata.
- [ ] 3.2 Compute sector return and relative strength windows.
- [ ] 3.3 Compute sector breadth proxies.
- [ ] 3.4 Rank sectors deterministically.
- [ ] 3.5 Assign rotation state.
- [ ] 3.6 Persist sector snapshots.

## 4. Commands

- [ ] 4.1 Add `/market-regime`.
- [ ] 4.2 Add `/sector-strength`.
- [ ] 4.3 Add `/sector-strength SYMBOL` for symbol-sector alignment.
- [ ] 4.4 Add help text and examples.
- [ ] 4.5 Render tables and caveats in OutputStream.

## 5. Assistant tools

- [ ] 5.1 Add `market.get_regime` tool.
- [ ] 5.2 Add `sector.get_strength` tool.
- [ ] 5.3 Add `sector.get_symbol_alignment` tool.
- [ ] 5.4 Add assistant intents for market and sector context.
- [ ] 5.5 Add synthesis templates.

## 6. Observability and evaluation

- [ ] 6.1 Emit `MARKET_REGIME_BUILT`.
- [ ] 6.2 Emit `SECTOR_STRENGTH_BUILT`.
- [ ] 6.3 Link events to correlation ID.
- [ ] 6.4 Add golden examples for regime and sector answers.

## 7. Validation

- [ ] 7.1 Test regime snapshot creation.
- [ ] 7.2 Test sector ranking creation.
- [ ] 7.3 Test insufficient data caveats.
- [ ] 7.4 Test no trading/execution language.
- [ ] 7.5 Run `make test-vnalpha`, `make lint-vnalpha`, `make verify-r4`, and `openstock-verify --ci`.
