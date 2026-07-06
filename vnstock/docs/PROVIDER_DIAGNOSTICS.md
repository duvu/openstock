# Provider Diagnostics

This document describes the diagnostics attached to routing decisions and
DataResult objects in the vnstock plugin platform.

## Routing Diagnostics

Every call to `PluginRouter.resolve()` records a `RoutingDecision` that can
be inspected for debugging and monitoring.

### RoutingDecision fields

| Field | Type | Description |
|-------|------|-------------|
| `dataset` | str | The requested dataset name |
| `requested_source` | str \| None | The `source=` argument supplied by caller |
| `selected_provider` | str \| None | Provider that was selected |
| `candidates` | list[str] | All providers registered for the dataset |
| `rejected` | dict[str, str] | Providers rejected + reason |
| `fallback` | bool | True if selection required falling back to a lower health tier |
| `reason` | str | Human-readable routing reason |
| `health_snapshot` | dict | Health state of each candidate at decision time |
| `warnings` | list[str] | Non-fatal warnings (e.g. DEGRADED provider selected) |

### Accessing diagnostics

```python
provider = router.resolve("equity.ohlcv")

# Full RoutingDecision object
decision = router.last_decision

# Plain dict (backward-compatible)
diag = router.last_diagnostics
```

### Health snapshot

The `health_snapshot` dict is keyed by provider name and contains a snapshot
of the `ProviderHealth` for each candidate at the time of routing:

```python
{
    "KBS": {
        "provider": "KBS",
        "dataset": "equity.ohlcv",
        "status": "HEALTHY",
        "latency_ms": 120.0,
        "freshness_score": None,
        "last_success_at": "2024-01-01T10:00:00+00:00",
        "last_failure_at": None,
        "failure_count": 0,
        "success_count": 5,
        "cooldown_until": None,
        "notes": None
    }
}
```

## DataResult Diagnostics

When a `DataResult` is created, routing and provider diagnostics are attached
to `DataResult.diagnostics`. These propagate to `DataFrame.attrs["diagnostics"]`
via `DataResult.to_dataframe()`.

```python
from vnstock.core.result import DataResult

result = DataResult(
    dataset="equity.ohlcv",
    provider="KBS",
    data=df,
    quality_status="PASS",
    diagnostics={
        "routing": router.last_diagnostics,
        "provider_notes": "fetched 200 rows",
    },
    fetched_at=datetime.utcnow(),
)

df_out = result.to_dataframe()
print(df_out.attrs["diagnostics"])   # dict with routing + provider_notes
print(df_out.attrs["provider"])      # "KBS"
print(df_out.attrs["quality"])       # quality_report (backward compat key)
```

## Health State

The `InMemoryProviderHealthStore` tracks health per `(provider, dataset)` pair.

### Recording outcomes

```python
from vnstock.core.provider.health import InMemoryProviderHealthStore

store = InMemoryProviderHealthStore()

# After a successful fetch
store.record_success("KBS", "equity.ohlcv", latency_ms=95.0)

# After a failed fetch
store.record_failure("KBS", "equity.ohlcv", notes="HTTP 503")

# Inspect
h = store.get("KBS", "equity.ohlcv")
print(h.status)          # HealthStatus.HEALTHY or DEGRADED or FAILING
print(h.failure_count)
print(h.cooldown_until)
```

### Health status semantics

| Status | Meaning |
|--------|---------|
| `HEALTHY` | Provider responding correctly. Selected first in auto routing. |
| `DEGRADED` | Intermittent errors or schema drift. Eligible as fallback. |
| `FAILING` | Consistently failing. Excluded from auto routing by default. |
| `UNKNOWN` | No data recorded yet. Treated as HEALTHY on first attempt. |
| `DISABLED` | Administratively disabled. Never selected. |

### Cooldown

After `failure_threshold` (default 3) consecutive failures, the provider
enters a `cooldown_seconds` (default 60) cooldown window. During cooldown,
the provider is skipped in auto routing.

Cooldown resets on the next successful fetch.

## Provider Comparison Diagnostics

The `comparison` module provides functions to compare DataFrames from two
providers, useful for monitoring and quality assurance:

```python
from vnstock.core.provider.comparison import (
    compare_ohlcv,
    compare_quote,
    compare_coverage,
    compare_freshness,
)

# Compare OHLCV data from two providers
diff = compare_ohlcv(df_kbs, df_vci)
print(diff["max_close_diff_pct"])    # Max relative close price difference
print(diff["aligned_rows"])          # Rows with matching timestamps

# Coverage comparison
cov = compare_coverage(df_kbs, df_vci)
print(cov["overlap_rows"])

# Freshness
fresh = compare_freshness(df_kbs, df_vci, label_a="KBS", label_b="VCI")
print(fresh["fresher_provider"])
```

## Security Note

Diagnostics **must not** contain authentication secrets. The `DataResult`
class enforces this via `_FORBIDDEN_METADATA_KEYS`. Never pass tokens,
passwords, API keys, or session cookies into the `diagnostics` dict.
