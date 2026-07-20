"""Dataset-level readiness over canonical warehouse evidence and provider config."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


class DatasetReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    DEGRADED = "DEGRADED"


class ProviderAvailability(str, Enum):
    AUTO_ROUTE = "AUTO_ROUTE"
    EXPLICIT_ONLY = "EXPLICIT_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


_DATASET_ALIASES = {
    "index.membership": "reference.index_membership_snapshot",
    "sector.membership": "reference.sector_membership_snapshot",
}

_INDEX_SYMBOLS = ("VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPCOM")


@dataclass(frozen=True, slots=True)
class DatasetReadinessResult:
    dataset: str
    status: DatasetReadinessStatus
    auto_providers: tuple[str, ...]
    explicit_providers: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    message: str | None = None


def check_dataset_readiness(
    conn: duckdb.DuckDBPyConnection,
    dataset: str,
) -> DatasetReadinessResult:
    """Report usable provider paths without presenting process liveness as data."""
    canonical_dataset = _canonical_dataset(dataset)
    provider_map = _get_dataset_provider_map()
    if canonical_dataset not in provider_map:
        return DatasetReadinessResult(
            dataset=canonical_dataset,
            status=DatasetReadinessStatus.NOT_READY,
            auto_providers=(),
            explicit_providers=(),
            rejection_reasons=("unsupported_dataset",),
            message=f"Dataset {canonical_dataset} is not supported",
        )

    auto: list[str] = []
    explicit: list[str] = []
    rejections: list[str] = []
    for provider, availability in provider_map[canonical_dataset].items():
        if availability is ProviderAvailability.AUTO_ROUTE:
            if _has_usable_warehouse_evidence(conn, canonical_dataset, provider):
                auto.append(provider)
            else:
                rejections.append(f"{provider}:no_usable_warehouse_evidence")
        elif availability is ProviderAvailability.EXPLICIT_ONLY:
            ready, reason = _explicit_provider_readiness(provider, canonical_dataset)
            if ready:
                explicit.append(provider)
            else:
                rejections.append(f"{provider}:{reason}")
        else:
            rejections.append(f"{provider}:unavailable")

    if auto:
        status = DatasetReadinessStatus.READY
        message = None
    elif explicit:
        status = DatasetReadinessStatus.DEGRADED
        message = (
            f"{canonical_dataset} is available only through explicit-only "
            f"providers ({', '.join(explicit)}); the auto-route warehouse path "
            "has no usable evidence."
        )
    else:
        status = DatasetReadinessStatus.NOT_READY
        message = f"No usable provider path is available for {canonical_dataset}"

    return DatasetReadinessResult(
        dataset=canonical_dataset,
        status=status,
        auto_providers=tuple(sorted(auto)),
        explicit_providers=tuple(sorted(explicit)),
        rejection_reasons=tuple(sorted(rejections)),
        message=message,
    )


def _canonical_dataset(dataset: str) -> str:
    normalized = dataset.strip().lower()
    return _DATASET_ALIASES.get(normalized, normalized)


def _get_dataset_provider_map() -> dict[str, dict[str, ProviderAvailability]]:
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
            "fiinquantx": ProviderAvailability.EXPLICIT_ONLY,
        },
        "reference.index_membership_snapshot": {
            "vci": ProviderAvailability.AUTO_ROUTE,
            "fiinquantx": ProviderAvailability.EXPLICIT_ONLY,
        },
        "reference.sector_membership_snapshot": {
            "vci": ProviderAvailability.AUTO_ROUTE,
            "fiinquantx": ProviderAvailability.EXPLICIT_ONLY,
        },
    }


def _has_usable_warehouse_evidence(
    conn: duckdb.DuckDBPyConnection,
    dataset: str,
    provider: str,
) -> bool:
    """Query the actual table and provider column owned by each dataset."""
    normalized = provider.upper()
    try:
        if dataset == "reference.symbols":
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM symbol_source_snapshot
                WHERE UPPER(source) = ? AND snapshot_status = 'SUCCESS'
                """,
                [normalized],
            ).fetchone()
        elif dataset in {"equity.ohlcv", "index.ohlcv"}:
            index_predicate = "IN" if dataset == "index.ohlcv" else "NOT IN"
            placeholders = ",".join("?" for _ in _INDEX_SYMBOLS)
            row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM canonical_ohlcv
                WHERE UPPER(selected_provider) = ?
                  AND symbol {index_predicate} ({placeholders})
                  AND quality_status IN ('PASS', 'SUCCESS')
                """,
                [normalized, *_INDEX_SYMBOLS],
            ).fetchone()
        elif dataset in {
            "reference.index_membership_snapshot",
            "reference.sector_membership_snapshot",
        }:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM reference_membership_snapshot
                WHERE dataset = ? AND UPPER(provider) = ?
                  AND status IN ('COMPLETE', 'SUCCESS', 'PASS')
                """,
                [dataset, normalized],
            ).fetchone()
        else:
            return False
    except Exception:  # noqa: BLE001 - readiness must remain bounded and truthful
        return False
    return bool(row and row[0] > 0)


def _explicit_provider_readiness(provider: str, dataset: str) -> tuple[bool, str]:
    if provider != "fiinquantx":
        return False, "unsupported_explicit_provider"
    if dataset == "reference.symbols":
        return False, "unsupported_dataset"
    if importlib.util.find_spec("fiinquantx") is None:
        return False, "sdk_missing"
    try:
        version = importlib.metadata.version("fiinquantx")
    except importlib.metadata.PackageNotFoundError:
        return False, "sdk_missing"
    if version != "0.1.64":
        return False, "sdk_version_unsupported"
    if not os.getenv("FIINQUANT_USERNAME") or not os.getenv("FIINQUANT_PASSWORD"):
        return False, "credentials_missing"
    if os.getenv("VNSTOCK_FIINQUANTX_LICENSED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        return False, "license_acknowledgement_missing"
    return True, "ready"


__all__ = [
    "DatasetReadinessResult",
    "DatasetReadinessStatus",
    "ProviderAvailability",
    "check_dataset_readiness",
]
