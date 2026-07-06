# Auth and Credentials Guide

This guide explains how authentication works in vnstock and how credentials are stored and managed.

## Philosophy

**vnstock is a data-read platform.** Authentication exists solely to access market data from providers that require it. No account management, order placement, portfolio tracking, or fund transfers are supported.

Auth is **command-based and local**. Credentials are never sent to a REST endpoint. All login operations happen via the CLI.

## Supported Auth Modes

| Provider | Auth Type | Required | Notes |
|----------|-----------|----------|-------|
| KBS | None | No | Public provider |
| VCI | None | No | Public provider |
| DNSE | None | No | Public provider (market data only) |
| MSN | None | No | Public provider |
| FMarket | None | No | Public provider |
| FMP | API Key | Yes | Set via env var or CLI |
| TCBS | Interactive | No (explicit only) | Experimental; token-based |

## CLI Auth Commands

### Login

```bash
vnstock-auth login tcbs
```

Prompts for username, password, and OTP (if required). Credentials are stored locally in `~/.config/vnstock/credentials/tcbs.json` with `chmod 600` permissions.

### Check Status

```bash
vnstock-auth status
```

Shows which providers have stored credentials. **Never displays token material.**

### Logout

```bash
vnstock-auth logout tcbs
```

Removes the session token from the credential store. Credentials remain on disk until explicitly deleted.

### Delete

```bash
vnstock-auth delete tcbs
```

Permanently deletes stored credentials for the provider.

## Credential Storage

Credentials are stored in the local file system using `LocalFileCredentialStore`:

- **Path:** `~/.config/vnstock/credentials/<provider>.json`
- **Permissions:** File is `chmod 600`, directory is `chmod 700`
- **Format:** JSON with non-sensitive fields plus encrypted token material

### Alternative Stores

| Store | Description | Use Case |
|-------|-------------|----------|
| `MemoryCredentialStore` | In-process dict | Tests only |
| `EnvCredentialStore` | `VNSTOCK_<PROVIDER>_TOKEN` env var | CI/CD, containers |
| `LocalFileCredentialStore` | `~/.config/vnstock/` | Default for users |
| `KeyringCredentialStore` | System keyring | Desktop systems |
| `VaultCredentialStore` | HashiCorp Vault | Enterprise (stub) |

### Environment Variable Override

For CI/CD or containerized environments, set:

```bash
export VNSTOCK_TCBS_TOKEN=<your-bearer-token>
```

This is read by `EnvCredentialStore` and takes precedence if configured.

## Auth Policies

The routing system supports four auth policies:

| Policy | Description |
|--------|-------------|
| `FORBID_AUTHENTICATED` | Never use authenticated providers |
| `PREFER_NO_AUTH` | Use public providers first (default) |
| `ALLOW_AUTHENTICATED` | Use authenticated providers if available |
| `REQUIRE_AUTHENTICATED` | Only use authenticated providers |

The default policy is `PREFER_NO_AUTH` — authenticated providers are never selected unless explicitly requested.

## TCBS Experimental Auth

TCBS authenticated mode is **experimental** and **explicit-only**. It:

- Requires interactive login via `vnstock-auth login tcbs`
- Is never auto-selected by the routing system
- Only unlocks data-read endpoints (no account/order/portfolio access)
- May break without notice as TCBS auth APIs are undocumented

To use TCBS with auth:

```python
from vnstock import Vnstock

stock = Vnstock(symbol="FPT", source="TCBS")  # explicit source selection
df = stock.quote.history(start="2024-01-01", end="2024-12-31")
```

## Security Notes

- **Tokens are never logged** — all auth diagnostics are redacted before appearing in logs or DataResult metadata.
- **No REST login endpoint** — the local data service has no `/v1/auth/login` endpoint.
- **Single-user scope** — this is a localhost tool, not a multi-user server.
- **Data-only boundary** — even with credentials, only market data endpoints are available.
