from __future__ import annotations

import pytest

from vnalpha.clients.vnstock.source_policy import (
    ENVIRONMENT_APPROVED_SOURCES,
    approved_persistence_sources,
    fiinquantx_persistence_approval,
    validate_persistence_source,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningService,
    DataProvisioningValidationError,
)


def _fiinquantx_request() -> DataProvisioningRequest:
    return DataProvisioningRequest(
        "download",
        "ohlcv",
        symbol="FPT",
        start="2026-07-01",
        end="2026-07-10",
        source="FIINQUANTX",
    )


def test_fiinquantx_is_rejected_without_commercial_persistence_approval(
    monkeypatch,
) -> None:
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", raising=False)

    assert "FIINQUANTX" not in approved_persistence_sources()
    assert "FIINQUANTX" not in ENVIRONMENT_APPROVED_SOURCES
    with pytest.raises(ValueError, match="commercial approval"):
        validate_persistence_source("fiinquantx")
    with pytest.raises(DataProvisioningValidationError):
        DataProvisioningService.validate_request(_fiinquantx_request())


def test_boolean_acknowledgement_enables_persistence(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")

    approval = fiinquantx_persistence_approval()

    assert approval.acknowledged is True
    assert approval.approved is True
    assert approval.diagnostics() == {"acknowledged": True, "approved": True}
    assert validate_persistence_source("FIINQUANTX") == "FIINQUANTX"


def test_fiinquantx_is_available_only_after_explicit_approval(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")

    approval = fiinquantx_persistence_approval()

    assert approval.approved is True
    assert "FIINQUANTX" in approved_persistence_sources()
    assert "FIINQUANTX" in ENVIRONMENT_APPROVED_SOURCES
    assert validate_persistence_source("fiinquantx") == "FIINQUANTX"
    DataProvisioningService.validate_request(_fiinquantx_request())
