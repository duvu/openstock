from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator, Set
from dataclasses import dataclass

_BASE_APPROVED_SOURCES = frozenset(
    {"KBS", "VCI", "MSN", "DNSE", "TCBS", "FMARKET", "FMP"}
)
_FIINQUANTX = "FIINQUANTX"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PLACEHOLDER_REFERENCES = frozenset(
    {
        "none",
        "n/a",
        "na",
        "pending",
        "placeholder",
        "tbd",
        "todo",
        "unknown",
        "unapproved",
    }
)
_APPROVAL_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{5,127}$")


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _normalize_approval_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in _PLACEHOLDER_REFERENCES:
        return None
    if _APPROVAL_REFERENCE_PATTERN.fullmatch(normalized) is None:
        return None
    return normalized


@dataclass(frozen=True, slots=True)
class FiinQuantXPersistenceApproval:
    acknowledged: bool
    reference: str | None

    @property
    def approved(self) -> bool:
        return self.acknowledged and self.reference is not None

    @property
    def reference_fingerprint(self) -> str | None:
        if self.reference is None:
            return None
        return hashlib.sha256(self.reference.encode("utf-8")).hexdigest()[:12]

    def diagnostics(self) -> dict[str, bool | str | None]:
        return {
            "acknowledged": self.acknowledged,
            "approved": self.approved,
            "reference_configured": self.reference is not None,
            "reference_fingerprint": self.reference_fingerprint,
        }


def fiinquantx_persistence_approval() -> FiinQuantXPersistenceApproval:
    return FiinQuantXPersistenceApproval(
        acknowledged=_enabled("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED"),
        reference=_normalize_approval_reference(
            os.environ.get("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVAL_REF")
        ),
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
            "commercial approval and sets both "
            "VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true and a reviewed "
            "VNALPHA_FIINQUANTX_PERSISTENCE_APPROVAL_REF."
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
