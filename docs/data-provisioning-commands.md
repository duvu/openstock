# Data Provisioning Commands

`vnalpha data` is the explicit, bounded path for preparing research data. It uses only the approved vnstock ingestion adapters and deterministic warehouse builders. It does not provide SQL, shell, filesystem, brokerage, account, portfolio, allocation, margin, transfer, order, or execution capability.

## Download raw data

```text
vnalpha data download symbols [--source PROVIDER]
vnalpha data download ohlcv SYMBOL [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--source PROVIDER]
vnalpha data download index [SYMBOL] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--source PROVIDER]
```

`ohlcv` requires one equity symbol. `index` defaults to `VNINDEX` when omitted.

## Build derived research artifacts

```text
vnalpha data build canonical SYMBOL
vnalpha data build features SYMBOL --date YYYY-MM-DD
vnalpha data build score SYMBOL --date YYYY-MM-DD
vnalpha data build market-regime --date YYYY-MM-DD
vnalpha data build sector-strength --date YYYY-MM-DD
```

The slash-command equivalents use the same validation and service:

```text
/data download ohlcv FPT --start 2026-01-01
/data build features FPT --date 2026-07-10
/data build market-regime --date 2026-07-10
```

Each successful result contains the artifact, status, applicable inserted/skipped or build counts, source, effective dates, warnings, and correlation ID. Failures are sanitized; use the correlation ID to inspect the audit trail. Invalid syntax, dates, unsupported data types, missing required symbols, and unsupported options fail before any provider request or warehouse mutation.

OHLCV downloads report one outcome per requested symbol:

```text
SUCCESS  valid rows were persisted
EMPTY    the provider returned a valid response with no rows
FAILED   a connection, timeout, HTTP, or provider runtime failure occurred
INVALID  JSON, OHLCV data, or provider quality validation failed
SKIPPED  the provider explicitly marked the request as skipped/current
```

A batch is `SUCCESS` only when every symbol is `SUCCESS` or `SKIPPED`, `PARTIAL` when useful work completed alongside a problem outcome, and `FAILED` when no required symbol completed. Failed, empty, and invalid output includes the affected symbol, a diagnostics reference, and a bounded `vnalpha data download ohlcv SYMBOL ...` remediation command. Provider exception text is not exposed in public output.

Existing `sync`, `build`, and `score` commands remain available and call the same provisioning service.
