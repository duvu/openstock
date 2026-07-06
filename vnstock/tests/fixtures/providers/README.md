# Provider Fixtures

This directory contains raw golden fixtures for provider contract tests.

## Structure

```
tests/fixtures/providers/
├── dnse/
│   ├── ohlcv_daily_raw.json       # Raw DNSE OHLCV response (array-of-arrays format)
│   ├── price_board_raw.json       # Raw DNSE price board response
│   └── intraday_raw.json          # Raw DNSE intraday response
├── kbs/
│   ├── ohlcv_daily_raw.json       # Raw KBS OHLCV response (data_day key, prices in millis)
│   ├── price_board_raw.json       # Raw KBS price board response (ISS endpoint, KBS field codes)
│   └── intraday_raw.json          # Raw KBS intraday response (data key, KBS field codes)
└── vci/
    ├── ohlcv_daily_raw.json       # Raw VCI OHLCV response (list of symbol arrays)
    ├── price_board_raw.json       # Raw VCI price board response (nested listingInfo/bidAsk/matchPrice)
    └── intraday_raw.json          # Raw VCI intraday response (truncTime/matchPrice/matchVol/matchType)
```

## How to Update Fixtures

Fixtures must be updated when a provider changes its API response shape.

**Do NOT update fixtures lightly.** A fixture change means the contract has drifted.
Always update the corresponding contract test expectations alongside the fixture.

### Update process

1. **Capture new raw response** from the live provider:
   ```python
   from vnstock.core.utils.client import send_request
   raw = send_request(url=..., headers=..., method="GET", params=...)
   import json; print(json.dumps(raw, indent=2, ensure_ascii=False))
   ```

2. **Review the diff** between the old and new fixture:
   - Missing required fields → **major drift**, update adapter + contract
   - Added optional fields → **minor drift**, update fixture only
   - Changed field names → **major drift**, update adapter + contract

3. **Update the fixture file** with the new raw response sample.
   Keep samples small (5–10 rows for OHLCV, 2–3 symbols for price board).

4. **Run contract tests** to verify the adapter still normalizes correctly:
   ```bash
   PYTHONPATH=. pytest tests/contracts/providers/ -m "contract" -v
   ```

5. **Update normalized expectations** if required columns changed.

6. **Commit both** the fixture and the test changes together.

## Format Notes

| Provider | OHLCV raw format | Notes |
|---|---|---|
| DNSE | `{"t": [...], "o": [...], ...}` | Unix epoch timestamps, prices already in VND |
| KBS  | `{"data_day": [{"t": "YYYY-MM-DD", "o": ..., ...}]}` | Prices in milli-VND (divide by 1000) |
| VCI  | `[{"t": [...], "o": [...], ...}]` | List wrapper, Unix epoch timestamps |

| Provider | Price board raw format | Notes |
|---|---|---|
| DNSE | List of symbol dicts with short field codes (`sym`, `c`, `f`, ...) | |
| KBS  | List of symbol dicts with KBS field codes (`SB`, `CP`, `CL`, ...) | |
| VCI  | List of objects with nested `listingInfo`, `bidAsk`, `matchPrice` | |
