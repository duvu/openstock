# Tasks — Add TCBS Data Provider

## 0. Scope and Safety Gate

- [x] Confirm TCBS provider is data-only.
- [x] Confirm no broker login, account, portfolio, margin, order, transfer, or iCopy action endpoint is implemented.
- [x] Add code comments/docs that TCBS endpoints are unofficial public endpoints and may drift.
- [x] Add provider-level disclaimer for vendor-derived TCBS fields such as rating, recommendation, valuation, and buy/sell signals.

## 1. Provider Package Skeleton

- [x] Create `vnstock/explorer/tcbs/__init__.py`.
- [x] Create `vnstock/explorer/tcbs/const.py`.
- [x] Create `vnstock/explorer/tcbs/quote.py`.
- [x] Create `vnstock/explorer/tcbs/trading.py`.
- [x] Create `vnstock/explorer/tcbs/company.py`.
- [x] Create `vnstock/explorer/tcbs/fundamental.py`.
- [x] Create `vnstock/explorer/tcbs/screener.py`.
- [x] Register TCBS adapters with `ProviderRegistry` where required.

## 2. Endpoint Constants and Field Maps

- [x] Add base URL: `https://apipubaws.tcbs.com.vn`.
- [x] Add OHLCV endpoint variants:
  - [x] `/stock/v2/stock/bars-long-term`
  - [x] `/stock-insight/v2/stock/bars-long-term`
  - [x] `/stock-insight/v1/stock/bars-long-term`
- [x] Add intraday endpoint candidate: `/stock/v1/intraday/{symbol}/his/paging`.
- [x] Add price board endpoint: `/stock/v1/stock/second-tc-price`.
- [x] Add company/reference endpoints.
- [x] Add financial endpoints.
- [x] Add screener endpoint: `/ligo/v1/watchlist/preview`.
- [x] Add interval map: `1m`, `5m`, `15m`, `30m`, `1H`, `1D`, `1W`, `1M`.
- [x] Add OHLCV raw-to-normalized map.
- [x] Add price board raw-to-normalized map.
- [x] Add screener raw-to-normalized map.

## 3. Quote Adapter

- [x] Implement `Quote.history()` for TCBS OHLCV.
- [x] Support `symbol`, `start`, `end`, `interval`, `count_back`, `length`, `to_df`, `get_all` where compatible.
- [x] Implement endpoint fallback order.
- [x] Record successful endpoint variant in `df.attrs["endpoint_variant"]`.
- [x] Normalize OHLCV columns to `time/open/high/low/close/volume`.
- [x] Normalize timestamp to timezone-naive Vietnam local time where needed.
- [x] Attach metadata attrs: source, symbol, interval, start, end, fetched_at.
- [x] Add input validation for symbol, date range, interval, and asset type.
- [x] Add structured errors for missing data, malformed response, unsupported interval, and endpoint fallback exhaustion.
- [x] Implement `Quote.intraday()` only if public live smoke verifies endpoint reliability.
- [x] If intraday remains uncertain, declare it experimental or unavailable.

## 4. Trading / Price Board Adapter

- [x] Implement `Trading.price_board(symbols_list, show_log=False, get_all=False)`.
- [x] Validate non-empty `symbols_list`.
- [x] Call `second-tc-price` with comma-separated tickers.
- [x] Normalize minimum required fields: symbol, close_price, volume_accumulated where present.
- [x] Normalize extended fields for technical, valuation, relative-strength, foreign, and market-score data.
- [x] Prefix or document vendor-derived columns clearly.
- [x] Attach metadata attrs: source, symbols, get_all, fetched_at.
- [x] Support `validate=True` and `quality_mode` integration through the UI dispatch path.

## 5. Company Adapter

- [x] Implement `Company.info()` or equivalent overview method using `/tcanalysis/v1/ticker/{symbol}/overview`.
- [x] Implement `Company.profile()` using `/tcanalysis/v1/company/{symbol}/overview` if response is distinct and useful.
- [x] Implement `Company.shareholders()` using large-shareholders endpoint.
- [x] Implement `Company.insider_trading()` using insider-dealing endpoint.
- [x] Implement `Company.subsidiaries()`.
- [x] Implement `Company.officers()`.
- [x] Implement `Company.events()`.
- [x] Implement `Company.news()`.
- [x] Implement `Company.dividends()`.
- [x] Normalize pagination metadata.
- [x] Preserve raw fields when `get_all=True`.

## 6. Symbol Industry Adapter

- [x] Implement symbol industry extraction from TCBS company overview.
- [x] Normalize as classification system `TCBS_INTERNAL`.
- [x] Output columns:
  - [x] symbol
  - [x] provider
  - [x] classification_system
  - [x] industry_code
  - [x] industry_name
  - [x] fetched_at
- [x] Do not map TCBS_INTERNAL to ICB unless a verified mapping exists.
- [x] Add support through `Reference.equity.list_by_industry(source="TCBS")` if compatible.

## 7. Fundamental Adapter

- [x] Implement balance sheet endpoint.
- [x] Implement income statement endpoint.
- [x] Implement cash flow endpoint.
- [x] Implement financial ratios endpoint.
- [x] Support `period="year"` and `period="quarter"`.
- [x] Map period to TCBS query parameters `yearly=true|false`.
- [x] Preserve raw TCBS line items initially.
- [x] Normalize common metadata: symbol, year, quarter, period_type, report_type, provider, fetched_at.
- [x] Add structured errors for unsupported period and malformed responses.

## 8. Screener Adapter

- [x] Implement `Screener.stock(params, limit=50, id=None, lang="vi", get_all=False)`.
- [x] Build `filters` payload from params.
- [x] Parse `searchData.pageContent`.
- [x] Normalize stable screener fields.
- [x] Extract multilingual values for known fields when `lang` is provided.
- [x] Preserve raw fields when `get_all=True`.
- [x] Mark screener API as experimental in docs and provider capabilities.
- [x] Do not expose screener output as investment advice.

## 9. Provider Capability Registry

- [x] Add TCBS OHLCV equity capability.
- [x] Add TCBS price board equity capability.
- [x] Add TCBS company profile capability.
- [x] Add TCBS symbol industry capability with `classification_system=TCBS_INTERNAL` in notes.
- [x] Add TCBS financial statement and ratio capabilities.
- [x] Add TCBS vendor screener capability marked experimental.
- [x] Add intraday capability only after live smoke confirms public availability.

## 10. Unified UI / API Integration

- [x] Add TCBS support to API adapter source validation where applicable.
- [x] Add `source="TCBS"` for `Market.equity.ohlcv`.
- [x] Add `source="TCBS"` for `Market.equity.quote`.
- [x] Add `source="TCBS"` for `Reference.company.info` where compatible.
- [x] Add `source="TCBS"` for `Reference.equity.list_by_industry` where compatible.
- [x] Add `source="TCBS"` for fundamental statement methods where compatible.
- [x] Do not make TCBS the default provider in this change.

## 11. Fixtures and Contract Tests

- [x] Add raw fixture: `tests/fixtures/providers/tcbs/ohlcv_daily_raw.json`.
- [x] Add normalized fixture or expected schema for OHLCV.
- [x] Add raw fixture for price board.
- [x] Add raw fixture for company overview.
- [x] Add raw fixture for financial ratios.
- [x] Add raw fixture for screener.
- [x] Add `tests/contracts/providers/test_tcbs_contracts.py`.
- [x] Test OHLCV parser against fixture.
- [x] Test price board parser against fixture.
- [x] Test company overview parser against fixture.
- [x] Test symbol industry normalization.
- [x] Test financial ratio parser.
- [x] Test screener parser.
- [x] Test malformed response handling.
- [x] Confirm contract tests do not call network.

## 12. Live Smoke Tests

- [x] Add `tests/live/providers/test_tcbs_live.py`.
- [x] Mark tests with `live`, `provider`, and `provider_tcbs`.
- [x] Ensure live tests skip unless `VNSTOCK_LIVE_TESTS=true`.
- [x] Support `VNSTOCK_LIVE_PROVIDERS=TCBS`.
- [x] Test OHLCV daily for one symbol and short range.
- [x] Test price board for one to three symbols.
- [x] Test company overview for one symbol.
- [x] Test financial ratios for one symbol.
- [x] Test screener minimal payload.
- [x] Test intraday only if stable and public.
- [x] Keep live smoke request count small.

## 13. Data Quality Integration

- [x] Ensure TCBS OHLCV output can pass existing OHLCV quality validator.
- [x] Ensure TCBS price board output can pass existing price board quality validator or document missing optional fields.
- [x] Attach `df.attrs["quality"]` when validation is enabled.
- [x] Add quality regression tests for TCBS normalized samples.

## 14. Provider Hardening Integration

- [x] Add TCBS drift baselines for raw and normalized schemas.
- [x] Add TCBS to provider matrix generation.
- [x] Add TCBS health scoring test cases.
- [x] Add TCBS to cross-provider OHLCV comparison if schema is compatible.
- [x] Keep TCBS health `unknown` or `degraded` until live smoke passes.

## 15. Documentation

- [x] Update `README.md` provider table.
- [x] Update `docs/PROVIDER_HARDENING.md`.
- [x] Update `docs/DATA_QUALITY.md` if TCBS-specific caveats are needed.
- [x] Update `roadmap.md` to move TCBS from discovery candidate to implementation candidate.
- [x] Document unofficial public endpoint risk.
- [x] Document vendor-derived screener/rating fields.

## 16. Validation Commands

Run before implementation PR is ready:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core/quality tests/unit/core/provider tests/contracts/providers -q
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
```

Optional live smoke:

```bash
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=TCBS VNSTOCK_LIVE_SYMBOLS=FPT pytest tests/live/providers/test_tcbs_live.py -m live -v
```

## 17. Exit Criteria

- [x] TCBS adapters implement only data-only endpoints.
- [x] OHLCV, price board, company overview, symbol industry, financial ratios, and screener have fixtures.
- [x] Contract tests pass offline.
- [x] Live smoke tests are opt-in and documented.
- [x] Provider capabilities are declared.
- [x] Quality validation works for TCBS OHLCV and price board.
- [x] TCBS is not the default provider.
- [x] Screener remains experimental until field stability is proven.
