# Local Data Service

The vnstock local data service is a lightweight HTTP server that exposes market data endpoints on your local machine.

## Purpose

- Serve data from vnstock providers over HTTP on `127.0.0.1`
- Allow external tools (notebooks, dashboards, scripts) to query data via REST
- Remain data-read only — no account, order, portfolio, or auth mutation endpoints

## Starting the Service

```bash
vnstock-serve --host 127.0.0.1 --port 6900
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `6900` | Bind port |
| `--log-level` | `info` | Logging level (`debug`, `info`, `warning`, `error`) |
| `--with-auth` | off | Enable auth-aware routing (requires credentials set up via CLI) |

## Available Endpoints

### Health

```
GET /healthz
```

Returns `{"status": "ok", "service": "vnstock"}`.

### Provider Metadata

```
GET /v1/providers
GET /v1/providers/health
GET /v1/providers/capabilities
```

Returns provider registry, health status, and capability matrix.

### Auth Status (Safe)

```
GET /v1/auth/status
GET /v1/auth/providers
```

Returns which providers have credentials stored. **No token material is ever returned.**

### Data Endpoints

```
GET /v1/market/<dataset>?symbol=<symbol>&start=<date>&end=<date>&interval=<interval>
GET /v1/reference/<dataset>
GET /v1/fundamental/<dataset>?symbol=<symbol>&period=<period>
GET /v1/fund/<dataset>
```

Examples:

```bash
curl "http://127.0.0.1:6900/v1/market/ohlcv?symbol=FPT&start=2024-01-01&end=2024-12-31"
curl "http://127.0.0.1:6900/v1/reference/listing"
```

## Forbidden Endpoints

The following endpoint groups **do not exist** and will return `404 Not Found`:

- `/v1/auth/login` — No REST login; use `vnstock-auth login` CLI instead
- `/v1/order*` — No order placement
- `/v1/account*` — No account info
- `/v1/portfolio*` — No portfolio data
- `/v1/transfer*` — No fund transfers
- `/v1/margin*` — No margin operations

These endpoints are structurally absent, not access-controlled. There is no way to enable them.

## Authentication

The service itself does not perform login. Use the CLI:

```bash
vnstock-auth login tcbs
```

Then start the service with `--with-auth` to enable authenticated providers.

See [AUTH_AND_CREDENTIALS.md](AUTH_AND_CREDENTIALS.md) for full auth documentation.

## Local-Only Scope

The service defaults to `127.0.0.1` (localhost only). It is designed for single-user local use:

- No TLS/HTTPS (localhost only)
- No rate limiting or API keys
- No multi-user access controls
- No session management

**Do not expose this service to the public internet.** It is not hardened for that use case.

## Dependencies

The service uses Python's stdlib `http.server` — no extra runtime dependencies required.
