from __future__ import annotations

import os
from collections.abc import Iterator, Set

_BASE_APPROVED_SOURCES = frozenset(
    {"KBS", "VCI", "MSN", "DNSE", "TCBS", "FMARKET", "FMP"}
)
_FIINQUANTX = "FIINQUANTX"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def fiinquantx_persistence_approved() -> bool:
    """Return whether licensed FiinQuantX rows may enter vnalpha persistence."""

    return _enabled("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED")


def approved_persistence_sources() -> frozenset[str]:
    if fiinquantx_persistence_approved():
        return frozenset((*_BASE_APPROVED_SOURCES, _FIINQUANTX))
    return _BASE_APPROVED_SOURCES


class EnvironmentApprovedSources(Set[str]):
    """Dynamic set used by validation code that is imported before dotenv/config."""

    def __contains__(self, value: object) -> bool:
        return value in approved_persistence_sources()

    def __iter__(self) -> Iterator[str]:
        return iter(approved_persistence_sources())

    def __len__(self) -> int:
        return len(approved_persistence_sources())


def validate_persistence_source(source: str | None) -> str | None:
    if source is None:
        return None
    normalized = source.strip().upper()
    if not normalized:
        return None
    if normalized == _FIINQUANTX and not fiinquantx_persistence_approved():
        raise ValueError(
            "FIINQUANTX persistence is disabled until the operator records "
            "commercial approval and sets "
            "VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true."
        )
    if normalized not in approved_persistence_sources():
        approved = ", ".join(sorted(approved_persistence_sources()))
        raise ValueError(f"Source must be an approved provider ({approved}).")
    return normalized


ENVIRONMENT_APPROVED_SOURCES = EnvironmentApprovedSources()


__all__ = [
    "ENVIRONMENT_APPROVED_SOURCES",
    "approved_persistence_sources",
    "fiinquantx_persistence_approved",
    "validate_persistence_source",
]
