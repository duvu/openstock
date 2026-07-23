# vnstock-service API Contract

## Overview

`vnstock-service` is a **localhost-only** HTTP data service listening on port **6900**.
It exposes Vietnamese financial market data to local consumers (e.g. vnalpha) via a simple
REST-like JSON API backed by vnstock's provider/plugin runtime.

- **Base URL:** `http://127.0.0.1:6900`
- **Transport:** HTTP/1.1 (stdlib `http.server`, no TLS)
- **All methods are `GET`.** The service is read-only; no mutating endpoints exist.
- **Scope:** Data extraction and normalization only. No auth login, order, portfolio,
  transfer, margin, or trading endpoints exist or will ever exist.

---

## Required Endpoints

| Endpoint | Dataset | Status | Notes |
|---|---|---|---|
| `GET /v1/reference/symbols` | `reference.symbols` | Available | Full symbol listing |
| `GET /v1/reference/corporate-actions` | `reference.corporate_actions` | Available (KBS/VCI partial) | Params: `symbol`, optional `start`, `end`; raw evidence only, no adjusted prices |
| `GET /v1/equity/ohlcv` | `equity.ohlcv` | Available | Params: `symbol`, `start`, `end`, `interval` |
| `GET /v1/equity/quote` | `equity.quote` | Available | Real-time / last quote |
| `GET /v1/index/ohlcv` | `index.ohlcv` | Available | Params: `symbol=VNINDEX` |
| `GET /v1/providers/health` | — | Available | Provider health store |
| `GET /v1/providers/capabilities` | — | Available | Provider capability matrix |

Additional available endpoints (not required by current vnalpha consumers):

| Endpoint | Dataset | Notes |
|---|---|---|
| `GET /healthz` | — | Simple liveness check |
| `GET /v1/providers` | — | Registered provider names |
| `GET /v1/equity/intraday-trades` | `equity.intraday_trades` | |
| `GET /v1/company/info` | `reference.company_info` | |
| `GET /v1/reference/index-membership` | `reference.index_membership_snapshot` | Current snapshot only; not historical membership evidence |
| `GET /v1/reference/sector-membership` | `reference.sector_membership_snapshot` | Current snapshot only; not historical taxonomy evidence |
| `GET /v1/fundamental/balance-sheet` | `fundamental.balance_sheet` | |
| `GET /v1/fundamental/income-statement` | `fundamental.income_statement` | |
| `GET /v1/fundamental/cash-flow` | `fundamental.cash_flow` | |
| `GET /v1/fundamental/financial-ratio` | `fundamental.financial_ratio` | |
| `GET /v1/fund/nav` | `fund.nav` | |

---

## Query Parameters

### Data parameters (forwarded to provider)

| Parameter | Type | Example | Description |
|---|---|---|---|
| `symbol` | string | `FPT` | Ticker symbol |
| `start` | string (ISO 8601 date) | `2024-01-01` | Start date (inclusive) |
| `end` | string (ISO 8601 date) | `2024-12-31` | End date (inclusive) |
| `interval` | string | `1D`, `1W`, `1M` | OHLCV bar interval |

### Runtime control parameters

These parameters control service-level behaviour and are **not** forwarded to the provider as data params.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | string | _(auto)_ | Pin to a specific provider, e.g. `kbs`, `vci`, `dnse`. Bypasses automatic provider routing. |
| `validate` | boolean string | `false` | Set `true` to run quality validation on the response. Attaches a quality report to `meta`. |
| `quality_mode` | string | `warn` | Quality enforcement mode: `warn`, `raise`, or `silent`. |

---

## Response Envelope

All data endpoints return a JSON envelope with the following top-level keys:

```json
{
  "data": [...],
  "meta": {
    "dataset": "equity.ohlcv",
    "provider": "kbs",
    "quality_status": "ok",
    "fetched_at": "2024-06-15T08:30:00+07:00"
  },
  "diagnostics": {
    "request_id": "req_a1b2c3d4e5f6",
    "duration_ms": 142,
    "rows": 10,
    "source_requested": null
  }
}
```

### Envelope fields

| Field | Always present | Description |
|---|---|---|
| `data` | Yes | Array of records (objects). Empty array `[]` when no data. |
| `meta.dataset` | Yes | Canonical dataset name, e.g. `equity.ohlcv`. |
| `meta.provider` | Yes | Provider that served the data. |
| `meta.quality_status` | Yes | `"ok"`, `"warn"`, `"fail"`, or `"skipped"`. |
| `meta.fetched_at` | Yes | ISO 8601 timestamp of when the fetch completed. |
| `diagnostics` | Yes | Request diagnostics (non-functional, for observability). |
| `diagnostics.request_id` | Yes | Unique request identifier. |
| `diagnostics.duration_ms` | Yes | Server-side fetch duration in milliseconds. |
| `diagnostics.rows` | Yes | Number of rows in `data`. |

### Non-data endpoints

`/v1/providers/health` and `/v1/providers/capabilities` return their own structured
objects at the top level (see [Examples](SERVICE_EXAMPLES.md)).

---

## Error Responses

All error responses use a standard JSON body. The HTTP status code indicates the error class.

### Error status codes

| HTTP Status | `error` field | Cause |
|---|---|---|
| `400 Bad Request` | `platform_error` | Invalid or missing parameters for the dataset. |
| `404 Not Found` | `not_found` | Unknown endpoint path. |
| `404 Not Found` | `unsupported_dataset` | Path maps to a dataset with no registered provider. |
| `422 Unprocessable Entity` | `contract_validation_failed` | Data contract check failed (when `validate=true`). |
| `503 Service Unavailable` | `no_healthy_provider` | All providers for the dataset are in cooldown or failed. |
| `502 Bad Gateway` | `provider_fetch_error` | Upstream provider returned an error. |
| `500 Internal Server Error` | `internal_error` | Unexpected server-side error. |

### Error body shape

```json
{
  "error": "no_healthy_provider",
  "message": "No healthy provider available for dataset 'equity.ohlcv'.",
  "dataset": "equity.ohlcv",
  "request_id": "req_a1b2c3d4e5f6"
}
```

---

## Deprecated Aliases

The following path aliases are still accepted but emit a `DeprecationWarning`
in server logs. Consumers must migrate to the canonical paths.

| Deprecated path | Canonical path |
|---|---|
| `GET /v1/market/ohlcv` | `GET /v1/equity/ohlcv` |
| `GET /v1/reference/listing` | `GET /v1/reference/symbols` |

---

## Forbidden Endpoints

The following route prefixes are explicitly blocked and will return `404`.
They must never be added to this service.

- `/v1/auth/login`
- `/v1/order*`
- `/v1/account*`
- `/v1/portfolio*`
- `/v1/transfer*`
- `/v1/margin*`
- `/v1/trading*`

---

## See Also

- [SERVICE_EXAMPLES.md](SERVICE_EXAMPLES.md) — `curl` examples and sample responses
- [LOCAL_DATA_SERVICE.md](LOCAL_DATA_SERVICE.md) — how to start and configure the service
- [DATASET_CONTRACTS.md](DATASET_CONTRACTS.md) — per-dataset column contracts
- [PROVIDER_DIAGNOSTICS.md](PROVIDER_DIAGNOSTICS.md) — provider health and diagnostics
