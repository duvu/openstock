from __future__ import annotations

from dataclasses import dataclass, field

from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.maintenance.source_routing import (
    resolve_maintenance_source_policy,
)


@dataclass
class _RecordingDelegate:
    requests: list[DataProvisioningRequest] = field(default_factory=list)

    def execute(self, request: DataProvisioningRequest) -> DataProvisioningResult:
        self.requests.append(request)
        return DataProvisioningResult(
            status=ProvisioningStatus.SUCCESS,
            operation=request.operation,
            artifact=request.artifact,
            correlation_id="test-correlation",
            source=request.source,
        )


def test_legacy_source_applies_only_to_equity_and_index_ohlcv() -> None:
    policy = resolve_maintenance_source_policy(legacy_ohlcv_source="fiinquantx")
    assert policy.reference_symbols.source is None
    assert policy.equity_ohlcv.source == "fiinquantx"
    assert policy.equity_ohlcv.fallback_allowed is False
    assert policy.index_ohlcv.source == "fiinquantx"
    assert policy.index_ohlcv.fallback_allowed is False
    assert policy.index_membership.source == "vci"
    assert policy.sector_membership.source == "vci"
