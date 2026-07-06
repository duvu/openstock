# Design: Phase 5 Alpha Discovery TUI MVP

## Overview

Phase 5 creates the first usable end-to-end research loop for `openstock`.

```text
vnstock-service
→ vnalpha sync
→ DuckDB warehouse
→ canonical OHLCV
→ feature store
→ scoring engine
→ daily watchlist
→ TUI workspace
```

The design is TUI-first. No Streamlit or web dashboard is part of this phase.

## System architecture

```text
openstock
├── docker-compose.yml
├── Makefile
├── .env.example
├── vnstock/
│   └── vnstock-service
└── vnalpha/
    ├── vnalpha-cli
    ├── vnalpha-core
    ├── vnalpha-warehouse
    ├── vnalpha-scoring
    └── vnalpha-tui
```

## Runtime flow

### Daily local workflow

```bash
make up-vnstock
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui
```

### Data flow

```text
vnstock-service /v1/reference/symbols
→ symbol_master

vnstock-service /v1/equity/ohlcv
→ market_ohlcv_raw
→ canonical_ohlcv
→ feature_snapshot
→ candidate_score
→ daily_watchlist
→ TUI
```

## vnstock contract

`vnalpha` must only call `vnstock-service` through HTTP.

Required endpoints:

```text
GET /v1/reference/symbols
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/providers/health
GET /v1/providers/capabilities
```

Required response envelope:

```text
data
meta
diagnostics
```

Required lineage fields to preserve:

```text
provider
quality_status
quality_report
diagnostics
fetched_at
runtime_path
ingestion_run_id
```

## vnalpha package structure

```text
vnalpha/
├── pyproject.toml
├── src/vnalpha/
│   ├── cli.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── types.py
│   ├── clients/
│   │   └── vnstock/
│   │       ├── client.py
│   │       ├── schemas.py
│   │       └── errors.py
│   ├── warehouse/
│   │   ├── connection.py
│   │   ├── schema.py
│   │   ├── migrations.py
│   │   └── repositories.py
│   ├── ingestion/
│   │   ├── sync_symbols.py
│   │   ├── sync_ohlcv.py
│   │   └── build_canonical.py
│   ├── features/
│   │   ├── price.py
│   │   ├── volume.py
│   │   ├── volatility.py
│   │   ├── relative_strength.py
│   │   └── build_features.py
│   ├── scoring/
│   │   ├── rules.py
│   │   ├── score.py
│   │   ├── risk_flags.py
│   │   └── generate_watchlist.py
│   └── tui/
│       ├── app.py
│       ├── screens/
│       │   ├── home.py
│       │   ├── watchlist.py
│       │   ├── symbol_detail.py
│       │   ├── rejected.py
│       │   └── provider_health.py
│       └── widgets/
│           ├── score_table.py
│           ├── risk_panel.py
│           └── mini_chart.py
├── configs/
│   ├── services.yaml
│   ├── scoring.yaml
│   └── universe.yaml
└── tests/
```

## CLI design

Use `Typer` for command routing.

Required commands:

```bash
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui
```

Optional aliases:

```bash
vnalpha run daily --universe VN30
```

## Warehouse design

Use DuckDB for MVP.

Minimum tables:

```text
ingestion_run
symbol_master
market_ohlcv_raw
canonical_ohlcv
feature_snapshot
candidate_score
daily_watchlist
rejected_symbol
```

### ingestion_run

```text
ingestion_run_id
started_at
finished_at
status
source_service
source_endpoint
universe
params_json
error_json
```

### symbol_master

```text
symbol
exchange
name
sector
industry
is_active
last_seen_at
```

### market_ohlcv_raw

```text
ingestion_run_id
symbol
time
interval
open
high
low
close
volume
provider
quality_status
quality_report_json
diagnostics_json
fetched_at
raw_json
```

### canonical_ohlcv

```text
symbol
time
interval
open
high
low
close
volume
selected_provider
quality_status
ingestion_run_id
source_service_run_id
```

### feature_snapshot

```text
symbol
date
close
ma20
ma50
ma100
ma20_slope
ma50_slope
volume_ma20
volume_ratio
atr14
return_20d
return_60d
rs_20d_vs_vnindex
rs_60d_vs_vnindex
distance_to_ma20
distance_to_52w_high
base_range_30d
close_strength
volatility_20d
```

### candidate_score

```text
symbol
date
score
candidate_class
setup_type
trend_score
relative_strength_score
volume_score
base_score
breakout_score
risk_quality_score
evidence_json
risk_flags_json
lineage_json
```

### daily_watchlist

```text
date
rank
symbol
score
candidate_class
setup_type
risk_flags_json
lineage_json
created_at
```

## Feature design

Minimum features:

```text
ma20
ma50
ma100
ma20_slope
ma50_slope
volume_ma20
volume_ratio
atr14
return_20d
return_60d
rs_20d_vs_vnindex
rs_60d_vs_vnindex
distance_to_ma20
distance_to_52w_high
base_range_30d
close_strength
volatility_20d
```

Rules:

```text
- Features must be computed only from canonical_ohlcv.
- Relative strength must compare against VNINDEX or configured benchmark.
- Missing windows must produce explicit rejected reasons or null-safe outputs.
- Feature calculations must be reproducible by date.
```

## Scoring design

Score weights:

```text
Trend score              25
Relative strength score  25
Volume score             15
Base/compression score   15
Breakout proximity       10
Risk/data quality        10
```

Candidate classes:

```text
STRONG_CANDIDATE  score >= 80
WATCH_CANDIDATE   65 <= score < 80
WEAK_CANDIDATE    50 <= score < 65
IGNORE            score < 50
```

Setup types v1:

```text
TREND_CONTINUATION
ACCUMULATION_BASE
BASE_BREAKOUT_ATTEMPT
PULLBACK_TO_MA20
RELATIVE_STRENGTH_LEADER
```

Risk flags:

```text
EXTENDED_FROM_MA20
LOW_LIQUIDITY
HIGH_VOLATILITY
WEAK_RS
BAD_MARKET_REGIME
POOR_DATA_QUALITY
VOLUME_SPIKE_ABNORMAL
MISSING_HISTORY
```

## TUI design

Use `Textual` and `Rich`.

### Screen: Home

Show:

```text
date
universe
benchmark
latest ingestion status
candidate count
provider health summary
```

### Screen: Daily Watchlist

Columns:

```text
rank
symbol
score
candidate_class
setup_type
close
return_20d
rs_20d
volume_ratio
risk_flags
provider
quality_status
```

Hotkeys:

```text
up/down   move selection
enter     open symbol detail
r         refresh
f         filter
s         sort
q         quit
```

### Screen: Symbol Detail

Show:

```text
symbol
score breakdown
setup type
evidence
risk flags
lineage
recent OHLCV summary
optional terminal mini chart
```

### Screen: Rejected Symbols

Show rejected symbols and reasons:

```text
LOW_LIQUIDITY
MISSING_HISTORY
POOR_DATA_QUALITY
BELOW_TREND_FILTER
```

### Screen: Provider Health

Show provider status, dataset, last status, latency, and failure counts where available.

## Safety and language boundary

The system must use research language only:

Allowed:

```text
candidate
watchlist
monitor
setup
evidence
risk flag
invalidation reference
```

Forbidden:

```text
buy
sell
place order
execute
portfolio allocation
investment advice
guaranteed return
```

## Testing strategy

Required tests:

```text
vnstock client typed envelope parsing
warehouse schema creation
canonical OHLCV build from fixture data
feature calculations on synthetic data
scoring rules on synthetic feature snapshots
watchlist generation ordering
TUI smoke import/start test
forbidden language checks in API/TUI strings
```

## Implementation order

```text
PR 1: vnalpha skeleton + CLI + config
PR 2: vnstock client + mocked tests
PR 3: DuckDB warehouse + sync symbols/OHLCV
PR 4: feature store v1
PR 5: scoring + daily watchlist
PR 6: TUI MVP
PR 7: openstock orchestration Makefile/docker-compose
```
