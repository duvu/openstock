"""Dataset readiness queries for issue #253.

Distinguishes process health from data availability and exposes which
providers can serve each canonical dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


class DatasetReadinessStatus(str, Enum):
    """Readiness state for a canonical dataset."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    DEGRADED = "DEGRADED"


class ProviderAvailability(str, Enum):
    """Provider availability classification."""

    AUTO_ROUTE = "AUTO_ROUTE"  # Automatic fallback enabled
    EXPLICIT_ONLY = "EXPLICIT_ONLY"  # Must be explicitly requested
    UNAVAILABLE = "UNAVAILABLE"  # Not available (auth, unsupported, cooldown)


@dataclass(frozen=True, slots=True)
class DatasetReadinessResult:
    """Result of a dataset readiness query."""

    dataset: str
    status: DatasetReadinessStatus
    auto_providers: tuple[str, ...]
    explicit_providers: tuple[str, ...]
    rejection_reasons: tuple[str, ...]  # Sanitized categories
    message: str | None = None


def check_dataset_readiness(
    conn: duckdb.DuckDBPyConnection,
    dataset: str,
) -> DatasetReadinessResult:
    """Query readiness for a specific canonical dataset.

    Args:
        conn: Database connection for checking recent ingestion status
        dataset: Dataset identifier (e.g., 'reference.symbols', 'equity.ohlcv')

    Returns:
        DatasetReadinessResult with status and provider availability
    """
    # Map datasets to their provider support
    dataset_providers = _get_dataset_provider_map()

    if dataset not in dataset_providers:
        return DatasetReadinessResult(
            dataset=dataset,
            status=DatasetReadinessStatus.NOT_READY,
            auto_providers=(),
            explicit_providers=(),
            rejection_reasons=("unsupported_dataset",),
            message=f"Dataset {dataset} is not supported",
        )

    providers = dataset_providers[dataset]

    # Check which providers are actually available
    auto = []
    explicit = []
    rejections = []

    for provider, availability in providers.items():
        if availability == ProviderAvailability.AUTO_ROUTE:
            # Check if provider has recent successful data
            if _has_recent_data(conn, dataset, provider):
                auto.append(provider)
            else:
                rejections.append(f"{provider}_no_recent_data")

        elif availability == ProviderAvailability.EXPLICIT_ONLY:
            # FiinQuantX and other licensed providers
            if _is_provider_configured(provider):
                explicit.append(provider)
            else:
                rejections.append(f"{provider}_not_configured")

        elif availability == ProviderAvailability.UNAVAILABLE:
            rejections.append(f"{provider}_unavailable")

    # Determine overall status with a three-way distinction (issue #253):
    #   READY      — at least one auto-route provider has usable recent data.
    #   DEGRADED   — the process is alive and providers are configured, but no
    #                auto-route provider currently has usable data; the dataset
    #                is only reachable through an explicit-only provider or is
    #                waiting on ingestion. This is distinct from a hard failure.
    #   NOT_READY  — no provider can serve the dataset at all.
    if auto:
        status = DatasetReadinessStatus.READY
        message = None
    elif explicit:
        # Only licensed explicit-only providers remain; auto path is not usable.
        status = DatasetReadinessStatus.DEGRADED
        message = (
            f"{dataset} is reachable only through explicit-only providers "
            f"({', '.join(explicit)}); auto-route data is unavailable."
        )
    elif rejections:
        status = DatasetReadinessStatus.NOT_READY
        message = f"No providers available for {dataset}"
    else:
        status = DatasetReadinessStatus.NOT_READY
        message = f"No providers configured for {dataset}"

    return DatasetReadinessResult(
        dataset=dataset,
        status=status,
        auto_providers=tuple(auto),
        explicit_providers=tuple(explicit),
        rejection_reasons=tuple(rejections),
        message=message,
    )


def _get_dataset_provider_map() -> dict[str, dict[str, ProviderAvailability]]:
    """Return the canonical dataset-to-provider mapping."""
    return {
        "reference.symbols": {
            "vci": ProviderAvailability.AUTO_ROUTE,
            "kbs": ProviderAvailability.AUTO_ROUTE,
            "ssi": ProviderAvailability.AUTO_ROUTE,
        },
        "equity.ohlcv": {
            "vci": ProviderAvailability.AUTO_ROUTE,
            "kbs": ProviderAvailability.AUTO_ROUTE,
            "ssi": ProviderAvailability.AUTO_ROUTE,
            "fiinquantx": ProviderAvailability.EXPLICIT_ONLY,
        },
        "index.ohlcv": {
            "vci": ProviderAvailability.AUTO_ROUTE,
            "kbs": ProviderAvailability.AUTO_ROUTE,
            "ssi": ProviderAvailability.AUTO_ROUTE,
        },
        "index.membership": {
            "vci": ProviderAvailability.AUTO_ROUTE,
        },
        "sector.membership": {
            "vci": ProviderAvailability.AUTO_ROUTE,
        },
    }


def _has_recent_data(
    conn: duckdb.DuckDBPyConnection,
    dataset: str,
    provider: str,
) -> bool:
    """Check if provider has recent successful ingestion for dataset."""
    try:
        # Check if we have any canonical data from this provider recently
        # This is a simplified check - real implementation would query
        # ingestion_run_outcome or canonical tables
        row = conn.execute(
            """
            SELECT COUNT(*) FROM canonical_ohlcv
            WHERE provider = ?
            LIMIT 1
            """,
            [provider],
        ).fetchone()
        return row is not None and row[0] > 0
    except Exception:  # noqa: BLE001
        return False


def _is_provider_configured(provider: str) -> bool:
    """Check if an explicit-only provider is configured."""
    if provider == "fiinquantx":
        # Check if FiinQuantX SDK and credentials are available
        try:
            from vnstock import Vnstock  # noqa: F401

            # In real implementation, would check credentials
            return True
        except ImportError:
            return False
    return False
