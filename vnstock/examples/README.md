# vnstock Provider Examples

Runnable Python scripts demonstrating every data provider supported by vnstock.
Each script calls real APIs and prints actual data — no mocking.

## Quick Start

```bash
# Install vnstock
pip install vnstock

# Run any provider example
python examples/kbs_example.py
python examples/vci_example.py
python examples/dnse_example.py
python examples/msn_example.py
python examples/tcbs_example.py
python examples/fmp_example.py   # requires FMP_API_KEY env var
python examples/fmarket_example.py
```

## Provider Reference

| Provider | Script | Credentials | Available Methods |
|---|---|---|---|
| **KBS** (default) | `kbs_example.py` | None | history, intraday, price_board, all_symbols, symbols_by_industries, company overview/shareholders, balance_sheet, income_statement, cash_flow, ratio |
| **VCI** | `vci_example.py` | None | history, intraday, price_board, all_symbols, symbols_by_industries, company overview/shareholders, balance_sheet, income_statement, cash_flow, ratio |
| **DNSE** | `dnse_example.py` | None | history, intraday, price_board |
| **MSN** | `msn_example.py` | None | search_symbol, history (requires symbol_id), listing info |
| **TCBS** | `tcbs_example.py` | None | history (3-endpoint fallback), intraday\*, price_board, all_symbols, symbol_industry, company overview/shareholders/dividends, balance_sheet, income_statement, cash_flow, ratio, screener\* |
| **FMP** | `fmp_example.py` | `FMP_API_KEY` env var | history, intraday, full quote |
| **FMarket** | `fmarket_example.py` | None | fund listing, filter, NAV report, top/industry/asset holdings |

> \* = experimental feature

## Default Symbols Used

Most examples use `FPT`, `VCB`, and `TCB` — liquid large-cap stocks present across all exchanges.

## Notes

- Guest-accessible providers may apply rate limits (~20 req/min)
- TCBS intraday and screener are unofficial public endpoints subject to change
- FMP requires a free API key from [financialmodelingprep.com](https://financialmodelingprep.com/developer/docs/)
- Each script wraps every API call in `try/except` so a single failure does not abort the full demo
