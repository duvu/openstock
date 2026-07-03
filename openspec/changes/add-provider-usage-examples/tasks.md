## 1. Directory & Index Setup

- [x] 1.1 Create `examples/` directory at repo root
- [x] 1.2 Create `examples/README.md` with provider table (name, script, credentials, methods)

## 2. KBS Provider Example

- [x] 2.1 Create `examples/kbs_example.py` with `main()` and `if __name__ == "__main__"` block
- [x] 2.2 Add KBS Quote.history() demo (symbol=FPT, daily interval)
- [x] 2.3 Add KBS Quote.intraday() demo
- [x] 2.4 Add KBS Trading.price_board() demo (symbols=[FPT, VCB, TCB])
- [x] 2.5 Add KBS Listing.all_symbols() demo
- [x] 2.6 Add KBS Listing.symbols_by_industries() demo
- [x] 2.7 Add KBS Company.overview() demo
- [x] 2.8 Add KBS Company.shareholders() demo
- [x] 2.9 Add KBS Finance.balance_sheet(), income_statement(), cash_flow(), ratio() demos
- [x] 2.10 Wrap each call in try/except; print section headers before each call

## 3. VCI Provider Example

- [x] 3.1 Create `examples/vci_example.py` with `main()` structure
- [x] 3.2 Add VCI Quote.history() and Quote.intraday() demos
- [x] 3.3 Add VCI Trading.price_board() demo
- [x] 3.4 Add VCI Listing.all_symbols() and Listing.symbols_by_industries() demos
- [x] 3.5 Add VCI Company.overview() and Company.shareholders() demos
- [x] 3.6 Add VCI Finance.balance_sheet(), income_statement(), cash_flow(), ratio() demos

## 4. DNSE Provider Example

- [x] 4.1 Create `examples/dnse_example.py` with `main()` structure
- [x] 4.2 Add DNSE Quote.history() demo
- [x] 4.3 Add DNSE Quote.intraday() demo
- [x] 4.4 Add DNSE Trading.price_board() demo

## 5. MSN Provider Example

- [x] 5.1 Create `examples/msn_example.py` with `main()` structure
- [x] 5.2 Add MSN Listing.search_symbol() demo to resolve symbol_id
- [x] 5.3 Add MSN Quote.history() demo using resolved symbol_id
- [x] 5.4 Add MSN Listing.info() demo

## 6. TCBS Provider Example

- [x] 6.1 Create `examples/tcbs_example.py` with `main()` structure
- [x] 6.2 Add TCBS Quote.history() demo (note which fallback endpoint responds)
- [x] 6.3 Add TCBS Quote.intraday() demo (labeled EXPERIMENTAL in comment)
- [x] 6.4 Add TCBS Trading.price_board() demo
- [x] 6.5 Add TCBS Listing.all_symbols() and Listing.symbol_industry() demos
- [x] 6.6 Add TCBS Company.overview(), shareholders(), dividends() demos
- [x] 6.7 Add TCBS Finance.balance_sheet(), income_statement(), cash_flow(), ratio() demos
- [x] 6.8 Add TCBS Screener.scan() demo (labeled EXPERIMENTAL in comment)

## 7. FMP Provider Example

- [x] 7.1 Create `examples/fmp_example.py` with `main()` structure
- [x] 7.2 Add env var check for `FMP_API_KEY`; print setup message and exit if missing
- [x] 7.3 Add FMP Quote.history() demo
- [x] 7.4 Add FMP Quote.intraday() demo
- [x] 7.5 Add FMP Quote.full() demo

## 8. FMarket Provider Example

- [x] 8.1 Create `examples/fmarket_example.py` with `main()` structure
- [x] 8.2 Add Fund.listing() demo
- [x] 8.3 Add Fund.filter() demo
- [x] 8.4 Add Fund.nav_report() demo (symbol=SSIAM-VNX50)
- [x] 8.5 Add Fund.top_holding(), Fund.industry_holding(), Fund.asset_holding() demos

## 9. README Integration

- [x] 9.1 Add "Examples" section to `README.md` linking to `examples/README.md`
