# Example Outputs

This directory contains captured real output from running each provider example script.
Generated on: 2026-07-03

## Status Summary

| Provider | Script | Status | Notes |
|----------|--------|--------|-------|
| KBS | `kbs_example.py` | Working | All endpoints return data |
| VCI | `vci_example.py` | Working | All endpoints return data |
| MSN | `msn_example.py` | Working | Requires resolving `symbol_id` first |
| FMarket | `fmarket_example.py` | Working | Fund symbol must match `Fund.listing()` short names |
| DNSE | `dnse_example.py` | Degraded | `services.entrade.com.vn` returns null arrays for all symbols; may require Vietnamese IP |
| TCBS | `tcbs_example.py` | Unavailable | `apipubaws.tcbs.com.vn` returns 404 for all endpoints; API may have changed or requires auth |
| FMP | `fmp_example.py` | Requires key | Set `FMP_API_KEY` environment variable before running |

## Output Files

- `kbs_output.txt` — KBS (TCBS-compatible via KBS) provider: OHLCV, intraday, price board, listing, company, financials
- `vci_output.txt` — VCI provider: OHLCV, intraday, price board, listing, company, financials
- `msn_output.txt` — MSN provider: symbol search, OHLCV history
- `fmarket_output.txt` — FMarket provider: fund listing, NAV, holdings, sector/asset allocation
- `dnse_output.txt` — DNSE provider: all calls return errors (API unreachable from current environment)
- `tcbs_output.txt` — TCBS provider: all calls return 404 (API endpoints unavailable)

## Regenerating

```bash
python examples/kbs_example.py > examples/output/kbs_output.txt 2>&1
python examples/vci_example.py > examples/output/vci_output.txt 2>&1
python examples/msn_example.py > examples/output/msn_output.txt 2>&1
python examples/fmarket_example.py > examples/output/fmarket_output.txt 2>&1
python examples/dnse_example.py > examples/output/dnse_output.txt 2>&1
python examples/tcbs_example.py > examples/output/tcbs_output.txt 2>&1
FMP_API_KEY=<your_key> python examples/fmp_example.py > examples/output/fmp_output.txt 2>&1
```
