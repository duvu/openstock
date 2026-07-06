# 03. Data pipeline

## Purpose

The data pipeline is the foundation of `vnalpha`. A pattern detector is only useful when its input data is validated, auditable, and reproducible.

The pipeline must enforce this rule:

```text
No unvalidated anonymous DataFrame should enter the feature engine.
```

## Data flow

```text
vnstock fetch
→ validated DataFrame + quality metadata
→ raw/provider-level storage
→ quality gate
→ canonical OHLCV
→ feature store
→ pattern engine
```

## Data sources

Initial sources:

- `vnstock` unified API;
- local CSV/manual import for fallback testing;
- optional provider-specific adapters only when `vnstock` does not expose a required dataset.

Required datasets for MVP:

```text
OHLCV daily per ticker
VN-Index OHLCV
ticker master
sector/industry mapping
```

Optional later datasets:

```text
foreign flow
proprietary trading flow
financial statements
valuation ratios
corporate actions
news/events
```

## Ingestion principles

### 1. Store provider metadata

Every fetched record should preserve:

```text
provider
source_priority
fetched_at
ingestion_run_id
quality_status
quality_report_json
provider_diagnostics_json
```

### 2. Separate provider data from canonical data

Use two storage layers:

```text
market_ohlcv      = provider-level data, for audit and comparison
canonical_ohlcv   = selected dataset used by research and pattern detection
```

### 3. Never overwrite silently

If the same symbol/date/provider is fetched again and values differ, the system should log the difference or version the ingestion run.

### 4. Validate before feature computation

Features must be computed only from canonical data that passes the quality gate.

## Suggested tables

### ingestion_run

```sql
CREATE TABLE ingestion_run (
    id TEXT PRIMARY KEY,
    run_date DATE NOT NULL,
    dataset TEXT NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT,
    config_json JSON,
    summary_json JSON
);
```

### market_ohlcv

```sql
CREATE TABLE market_ohlcv (
    symbol TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    interval TEXT NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,

    provider TEXT NOT NULL,
    source_priority INT,
    fetched_at TIMESTAMP NOT NULL,

    quality_status TEXT,
    quality_report_json JSON,
    provider_diagnostics_json JSON,
    ingestion_run_id TEXT,

    PRIMARY KEY(symbol, time, interval, provider)
);
```

### canonical_ohlcv

```sql
CREATE TABLE canonical_ohlcv (
    symbol TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    interval TEXT NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,

    selected_provider TEXT,
    quality_status TEXT,
    selection_reason TEXT,
    ingestion_run_id TEXT,

    PRIMARY KEY(symbol, time, interval)
);
```

### ticker_master

```sql
CREATE TABLE ticker_master (
    symbol TEXT PRIMARY KEY,
    exchange TEXT,
    sector TEXT,
    industry TEXT,
    company_name TEXT,
    market_cap DOUBLE,
    listing_status TEXT,
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMP
);
```

## Quality gate

The quality gate converts data validation results into scanner decisions.

Possible statuses:

```text
PASS
WARN_ACCEPTED
REJECT
```

### PASS

Data can enter canonical OHLCV.

Examples:

```text
valid OHLC schema
no critical nulls
no invalid high/low/close relationship
enough lookback history
acceptable missing-session ratio
```

### WARN_ACCEPTED

Data can enter canonical OHLCV but should carry warning flags.

Examples:

```text
minor freshness warning on historical backfill
small number of missing sessions
non-critical provider warning
```

### REJECT

Data must not enter feature computation.

Examples:

```text
missing close/high/low
close > high
close < low
negative volume
too many missing bars
large provider divergence
insufficient history
```

## Canonical selection policy

Initial policy:

```yaml
ohlcv_daily:
  primary: KBS
  fallback:
    - VCI
    - DNSE
  validate: true
  quality_mode: warn
  min_history_sessions: 250
```

Selection logic:

```text
1. Try primary provider.
2. Validate returned data.
3. If PASS, select provider as canonical.
4. If WARN_ACCEPTED, select only if no better fallback exists.
5. If REJECT, try fallback provider.
6. Store all provider-level data for audit.
7. Store selected row in canonical_ohlcv.
```

## Batch ingestion requirements

Full-market scanning requires batch ingestion.

The ingestion module should support:

```text
symbol universe input
start/end dates
provider policy
retry/backoff
quality report collection
partial failure handling
run summary
```

Example CLI:

```bash
python -m vnalpha.ingestion.sync_ohlcv \
  --start 2020-01-01 \
  --end 2026-07-03 \
  --interval 1D \
  --validate \
  --universe hose-hnx-upcom
```

## Data quality checks for technical signals

Additional scanner-level checks:

```text
minimum average traded value
minimum number of sessions
maximum missing-session ratio
corporate-action anomaly detection
volume zero streak detection
outlier gap detection
```

These checks should produce exclusion reasons such as:

```text
LOW_LIQUIDITY
INSUFFICIENT_HISTORY
DATA_QUALITY_REJECTED
TOO_MANY_MISSING_BARS
UNADJUSTED_CORPORATE_ACTION_RISK
```

## Data lineage in downstream objects

Every `pattern_instance` should store:

```text
ingestion_run_id
data_quality_status
selected_provider
feature_version
pattern_detector_version
```

This makes it possible to answer:

- Which data version generated this signal?
- Which provider was used?
- Did the signal come from warning-level data?
- Would the signal change if another provider were used?

## MVP deliverables

- `sync_universe.py`
- `sync_ohlcv.py`
- `quality_gate.py`
- `build_canonical.py`
- `market_ohlcv` table
- `canonical_ohlcv` table
- `ticker_master` table
- ingestion run summary
