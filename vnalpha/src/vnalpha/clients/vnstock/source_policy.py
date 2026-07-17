from __future__ import annotations

import os
from collections.abc import Iterator, Set
from dataclasses import dataclass

_BASE_APPROVED_SOURCES = frozenset(
    {"KBS", "VCI", "MSN", "DNSE", "TCBS", "FMARKET", "FMP"}
)
_FIINQUANTX = "FIINQUANTX"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


@dataclass(frozen=True, slots=True)
class FiinQuantXPersistenceApproval:
    acknowledged: bool

    @property
    def approved(self) -> bool:
        return self.acknowledged

    def diagnostics(self) -> dict[str, bool]:
        return {
            "acknowledged": self.acknowledged,
            "approved": self.approved,
        }


def fiinquantx_persistence_approval() -> FiinQuantXPersistenceApproval:
    return FiinQuantXPersistenceApproval(
        acknowledged=_enabled("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED"),
    )


def fiinquantx_persistence_approved() -> bool:
    """Return whether licensed FiinQuantX rows may enter vnalpha persistence."""

    return fiinquantx_persistence_approval().approved


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
    "FiinQuantXPersistenceApproval",
    "approved_persistence_sources",
    "fiinquantx_persistence_approval",
    "fiinquantx_persistence_approved",
    "validate_persistence_source",
]
