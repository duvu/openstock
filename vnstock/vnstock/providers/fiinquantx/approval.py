from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

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


def normalize_approval_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in _PLACEHOLDER_REFERENCES:
        return None
    if _APPROVAL_REFERENCE_PATTERN.fullmatch(normalized) is None:
        return None
    return normalized


def approval_reference_fingerprint(reference: str | None) -> str | None:
    normalized = normalize_approval_reference(reference)
    if normalized is None:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class FiinQuantXLicenseApproval:
    acknowledged: bool
    reference: str | None

    @property
    def approved(self) -> bool:
        return self.acknowledged and self.reference is not None

    @property
    def reference_configured(self) -> bool:
        return self.reference is not None

    @property
    def reference_fingerprint(self) -> str | None:
        return approval_reference_fingerprint(self.reference)

    def diagnostics(self) -> dict[str, bool | str | None]:
        return {
            "acknowledged": self.acknowledged,
            "approved": self.approved,
            "reference_configured": self.reference_configured,
            "reference_fingerprint": self.reference_fingerprint,
        }


def fiinquantx_license_approval() -> FiinQuantXLicenseApproval:
    return FiinQuantXLicenseApproval(
        acknowledged=_enabled("VNSTOCK_FIINQUANTX_LICENSED"),
        reference=normalize_approval_reference(
            os.environ.get("VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF")
        ),
    )


__all__ = [
    "FiinQuantXLicenseApproval",
    "approval_reference_fingerprint",
    "fiinquantx_license_approval",
    "normalize_approval_reference",
]
