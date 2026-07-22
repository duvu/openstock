from __future__ import annotations

from vnalpha.clients.vnstock.source_policy import (
    ENVIRONMENT_APPROVED_SOURCES,
    approved_persistence_sources,
    validate_persistence_source,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningService,
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


def test_fiinquantx_is_accepted_for_persistence() -> None:
    assert "FIINQUANTX" in approved_persistence_sources()
    assert "FIINQUANTX" in ENVIRONMENT_APPROVED_SOURCES
    assert validate_persistence_source("fiinquantx") == "FIINQUANTX"
    DataProvisioningService.validate_request(_fiinquantx_request())
