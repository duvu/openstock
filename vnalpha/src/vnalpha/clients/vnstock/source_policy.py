from __future__ import annotations

from collections.abc import Iterator, Set
from typing import Final

_BASE_APPROVED_SOURCES: Final = frozenset(
    {"KBS", "VCI", "MSN", "DNSE", "TCBS", "FMARKET", "FMP", "FIINQUANTX"}
)


def approved_persistence_sources() -> frozenset[str]:
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
    if normalized not in approved_persistence_sources():
        approved = ", ".join(sorted(approved_persistence_sources()))
        raise ValueError(f"Source must be an approved provider ({approved}).")
    return normalized


ENVIRONMENT_APPROVED_SOURCES = EnvironmentApprovedSources()


__all__ = [
    "ENVIRONMENT_APPROVED_SOURCES",
    "approved_persistence_sources",
    "validate_persistence_source",
]
