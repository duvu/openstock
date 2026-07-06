# vnstock-service API Examples

Practical `curl` examples with realistic sample responses.
All requests target `http://127.0.0.1:6900`.

---

## 1. Reference symbols — `GET /v1/reference/symbols`

```bash
curl -s "http://127.0.0.1:6900/v1/reference/symbols?source=kbs" | python3 -m json.tool
```

**Example response**

```json
{
  "data": [
    {
      "symbol": "FPT",
      "organ_name": "Công ty Cổ phần FPT",
      "organ_short_name": "FPT Corp",
      "organ_type_code": "CTY",
      "com_group_code": "HOSE",
      "exchange": "HOSE"
    },
    {
      "symbol": "VNM",
      "organ_name": "Công ty Cổ phần Sữa Việt Nam",
      "organ_short_name": "Vinamilk",
      "organ_type_code": "CTY",
      "com_group_code": "HOSE",
      "exchange": "HOSE"
    },
    {
      "symbol": "HPG",
      "organ_name": "Công ty Cổ phần Tập đoàn Hoà Phát",
      "organ_short_name": "Hoa Phat Group",
      "organ_type_code": "CTY",
      "com_group_code": "HOSE",
      "exchange": "HOSE"
    },
    {
      "symbol": "TCB",
      "organ_name": "Ngân hàng TMCP Kỹ thương Việt Nam",
      "organ_short_name": "Techcombank",
      "organ_type_code": "NH",
      "com_group_code": "HOSE",
      "exchange": "HOSE"
    }
  ],
  "meta": {
    "dataset": "reference.symbols",
    "provider": "kbs",
    "quality_status": "skipped",
    "fetched_at": "2024-06-15T08:01:22+07:00"
  },
  "diagnostics": {
    "request_id": "req_4f8a1c2d9e3b",
    "duration_ms": 87,
    "rows": 4,
    "source_requested": "kbs"
  }
}
```

---

## 2. Equity OHLCV — `GET /v1/equity/ohlcv`

```bash
curl -s "http://127.0.0.1:6900/v1/equity/ohlcv?symbol=FPT&start=2024-01-01&end=2024-01-10&interval=1D" \
  | python3 -m json.tool
```

**Example response**

```json
{
  "data": [
    {
      "time": "2024-01-02",
      "open": 97400.0,
      "high": 98700.0,
      "low": 96800.0,
      "close": 98200.0,
      "volume": 1823400
    },
    {
      "time": "2024-01-03",
      "open": 98200.0,
      "high": 99500.0,
      "low": 97900.0,
      "close": 99100.0,
      "volume": 2145600
    },
    {
      "time": "2024-01-04",
      "open": 99100.0,
      "high": 100200.0,
      "low": 98600.0,
      "close": 99800.0,
      "volume": 1987200
    },
    {
      "time": "2024-01-05",
      "open": 99800.0,
      "high": 101500.0,
      "low": 99200.0,
      "close": 101000.0,
      "volume": 2534100
    },
    {
      "time": "2024-01-08",
      "open": 101000.0,
      "high": 102300.0,
      "low": 100400.0,
      "close": 101700.0,
      "volume": 1762800
    },
    {
      "time": "2024-01-09",
      "open": 101700.0,
      "high": 103000.0,
      "low": 101100.0,
      "close": 102500.0,
      "volume": 2089500
    },
    {
      "time": "2024-01-10",
      "open": 102500.0,
      "high": 103800.0,
      "low": 101800.0,
      "close": 103200.0,
      "volume": 1654300
    }
  ],
  "meta": {
    "dataset": "equity.ohlcv",
    "provider": "kbs",
    "quality_status": "skipped",
    "fetched_at": "2024-06-15T08:05:44+07:00"
  },
  "diagnostics": {
    "request_id": "req_9c3e7b1a4d2f",
    "duration_ms": 124,
    "rows": 7,
    "source_requested": null
  }
}
```

With quality validation enabled:

```bash
curl -s "http://127.0.0.1:6900/v1/equity/ohlcv?symbol=FPT&start=2024-01-01&end=2024-01-10&interval=1D&validate=true"
```

The `meta.quality_status` field will then be `"ok"` or `"warn"` instead of `"skipped"`.

---

## 3. Provider health — `GET /v1/providers/health`

```bash
curl -s "http://127.0.0.1:6900/v1/providers/health" | python3 -m json.tool
```

**Example response**

```json
{
  "health": {
    "kbs": {
      "equity.ohlcv": {
        "provider": "kbs",
        "dataset": "equity.ohlcv",
        "status": "healthy",
        "last_success_at": "2024-06-15T07:58:12+07:00",
        "last_failure_at": null,
        "consecutive_failures": 0,
        "in_cooldown": false
      },
      "equity.quote": {
        "provider": "kbs",
        "dataset": "equity.quote",
        "status": "healthy",
        "last_success_at": "2024-06-15T08:00:05+07:00",
        "last_failure_at": null,
        "consecutive_failures": 0,
        "in_cooldown": false
      },
      "reference.symbols": {
        "provider": "kbs",
        "dataset": "reference.symbols",
        "status": "healthy",
        "last_success_at": "2024-06-15T07:55:30+07:00",
        "last_failure_at": null,
        "consecutive_failures": 0,
        "in_cooldown": false
      }
    },
    "vci": {
      "equity.ohlcv": {
        "provider": "vci",
        "dataset": "equity.ohlcv",
        "status": "degraded",
        "last_success_at": "2024-06-14T22:14:08+07:00",
        "last_failure_at": "2024-06-15T07:50:33+07:00",
        "consecutive_failures": 2,
        "in_cooldown": true
      }
    }
  }
}
```

---

## 4. Provider capabilities — `GET /v1/providers/capabilities`

```bash
curl -s "http://127.0.0.1:6900/v1/providers/capabilities" | python3 -m json.tool
```

**Example response**

```json
{
  "capabilities": {
    "kbs": {
      "datasets": [
        "equity.ohlcv",
        "equity.quote",
        "equity.intraday_trades",
        "index.ohlcv",
        "reference.symbols",
        "reference.company_info"
      ],
      "intervals": ["1D", "1W", "1M"],
      "auth_required": false,
      "experimental": false
    },
    "vci": {
      "datasets": [
        "equity.ohlcv",
        "equity.quote",
        "index.ohlcv",
        "fundamental.balance_sheet",
        "fundamental.income_statement",
        "fundamental.cash_flow",
        "fundamental.financial_ratio"
      ],
      "intervals": ["1D", "1W", "1M", "1Y"],
      "auth_required": false,
      "experimental": false
    },
    "dnse": {
      "datasets": [
        "equity.ohlcv",
        "equity.quote",
        "equity.intraday_trades",
        "index.ohlcv"
      ],
      "intervals": ["1D", "1W", "1M"],
      "auth_required": false,
      "experimental": false
    },
    "fmp": {
      "datasets": [
        "equity.ohlcv",
        "equity.quote",
        "fundamental.balance_sheet",
        "fundamental.income_statement",
        "fundamental.cash_flow"
      ],
      "intervals": ["1D", "1W", "1M", "1Y"],
      "auth_required": true,
      "experimental": false
    }
  }
}
```

---

## 5. Error examples

### Unknown endpoint

```bash
curl -s "http://127.0.0.1:6900/v1/unknown/path"
```

```json
{
  "error": "not_found",
  "message": "Endpoint '/v1/unknown/path' not found."
}
```

### No healthy provider

```bash
curl -s "http://127.0.0.1:6900/v1/equity/ohlcv?symbol=FPT&start=2024-01-01&end=2024-01-10"
```

```json
{
  "error": "no_healthy_provider",
  "message": "No healthy provider available for dataset 'equity.ohlcv'.",
  "dataset": "equity.ohlcv",
  "request_id": "req_7d4b2e9a1c5f"
}
```

### Bad request parameters

```bash
curl -s "http://127.0.0.1:6900/v1/equity/ohlcv?symbol=FPT&start=not-a-date"
```

```json
{
  "error": "platform_error",
  "message": "Invalid parameters: 'start' must be a valid date string (YYYY-MM-DD).",
  "dataset": "equity.ohlcv",
  "request_id": "req_2a8f3c6d0e4b"
}
```
