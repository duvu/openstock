# Feature Snapshot: Status, Lineage, and Skipped Symbols

## feature_data_status Values

Each row in `feature_snapshot` carries a `feature_data_status` that describes
the quality of the underlying OHLCV bars used to build the features.

| Value | Meaning | Source bar vs target date |
|-------|---------|---------------------------|
| `EXACT_DATE` | Latest bar date matches the target date exactly | `as_of_bar_date == target_date` |
| `STALE_DATE` | Latest available bar is older than the target date | `as_of_bar_date < target_date` |
| `MISSING_BENCHMARK` | The selected benchmark data was absent; only symbol features built | N/A |

**Precedence**: `EXACT_DATE` > `STALE_DATE` > `MISSING_BENCHMARK`. A row is
`MISSING_BENCHMARK` only when the benchmark DataFrame is empty; it takes
priority over any bar-staleness check because the benchmark is a hard
dependency for several relative-strength features.

## Skipped-Symbol Behavior

`build_features()` skips a symbol silently in two cases. Neither case produces
a `feature_snapshot` row.

| Skip reason | Condition | Logged as |
|-------------|-----------|-----------|
| `MISSING_CANONICAL` | No rows in `canonical_ohlcv` for the symbol | warning log |
| `INSUFFICIENT_HISTORY` | Fewer rows than the minimum required for feature calculation | warning log |

Skipped symbols are **not** persisted to `feature_snapshot`. Downstream steps
(scoring, watchlist) will simply have no features for those symbols on that
date. The skips are visible in the application logs.

## Lineage Propagation

`feature_snapshot` stores `lineage_json` — a JSON object describing the OHLCV
source used when building features.

### lineage_json fields

| Field | Description |
|-------|-------------|
| `provider` | Data provider name (e.g. `"KBS"`, `"DNSE"`) |
| `ingestion_run_id` | UUID of the ingestion run that produced the source row |
| `quality_status` | Quality status of the source bar (e.g. `"GOOD"`, `"WARN"`) |
| `as_of_bar_date` | The actual bar date used (same as `as_of_bar_date` column) |
| `feature_build_version` | Package version of `vnalpha` at feature build time |
| `benchmark_symbol` | Actual index used for relative strength (`VNINDEX`, `VN30`, `HNXINDEX`, or `UPCOMINDEX`) |
| `benchmark_as_of_bar_date` | Actual benchmark bar date aligned to the feature row |
| `benchmark_provider` | Provider selected for the benchmark canonical bar |
| `benchmark_ingestion_run_id` | Ingestion run selected for the benchmark canonical bar |

## Benchmark-Aware Relative Strength

Relative-strength evidence is stored in `relative_strength_snapshot`, keyed by
symbol, date, actual benchmark, and horizon. VNINDEX legacy feature columns
remain readable, but a non-VNINDEX calculation never writes data into a column
labeled `vs_vnindex`.

The default policy selects VNINDEX for HOSE, HNXINDEX for HNX, and UPCOMINDEX
for UPCOM common equities. VN30 is an approved secondary benchmark and can be
selected explicitly. Both feature-build interfaces accept `--benchmark`:

```text
vnalpha build features --date 2026-07-10 --benchmark VN30
vnalpha data build features FPT --date 2026-07-10 --benchmark VN30
```

Scoring and deep-analysis feature context read the normalized evidence and
display the benchmark recorded in lineage. Readiness requires successful 20-
and 60-session evidence for that same benchmark; a missing horizon is not
treated as a successful relative-strength input.

### lineage_status in candidate_score

When `score_universe()` creates a `candidate_score` row it also propagates
lineage from `feature_snapshot.lineage_json` and computes a `lineage_status`:

| lineage_status | Meaning |
|----------------|---------|
| `COMPLETE` | Both `provider` and `ingestion_run_id` present |
| `PARTIAL` | `provider` present but `ingestion_run_id` missing |
| `MISSING_PROVIDER` | `provider` is null |
| `MISSING_INGESTION_RUN` | `ingestion_run_id` is null |

A `lineage_status` of `COMPLETE` means the candidate score can be fully traced
from source ingestion through feature build to scoring. Partial or missing
lineage does not block scoring but surfaces in audit queries.

### Propagated lineage fields in candidate_score

The following fields from `feature_snapshot.lineage_json` are written to
`candidate_score`:

- `provider`
- `ingestion_run_id`
- `feature_build_version`
- `as_of_bar_date`
- `source_quality_status`
