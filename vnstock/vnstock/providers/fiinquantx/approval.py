from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


@dataclass(frozen=True, slots=True)
class FiinQuantXLicenseApproval:
    acknowledged: bool

    @property
    def approved(self) -> bool:
        return self.acknowledged

    def diagnostics(self) -> dict[str, bool]:
        return {
            "acknowledged": self.acknowledged,
            "approved": self.approved,
        }


def fiinquantx_license_approval() -> FiinQuantXLicenseApproval:
    return FiinQuantXLicenseApproval(
        acknowledged=_enabled("VNSTOCK_FIINQUANTX_LICENSED"),
    )


__all__ = [
    "FiinQuantXLicenseApproval",
    "fiinquantx_license_approval",
]
