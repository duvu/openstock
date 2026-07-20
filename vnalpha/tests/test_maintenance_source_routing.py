from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import pytest

from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    ProvisioningStatus,
)
from vnalpha.data_provisioning.source_policy import InvalidSourceForDataset
from vnalpha.maintenance.source_routing import (
    RoutedDataProvisioningService,
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


def test_each_maintenance_artifact_routes_to_its_own_source() -> None:
    policy = resolve_maintenance_source_policy(
        reference_source="vci",
        equity_source="kbs",
        index_source="fiinquantx",
        membership_source="fiinquantx",
    )
    delegate = _RecordingDelegate()
    service = RoutedDataProvisioningService(
        duckdb.connect(":memory:"),
        policy,
        delegate=delegate,
    )

    requests = (
        DataProvisioningRequest("download", "symbols"),
        DataProvisioningRequest("sync", "daily", symbols=("FPT",), date="2026-07-17"),
        DataProvisioningRequest("repair", "ohlcv", symbol="FPT"),
        DataProvisioningRequest("download", "index", symbol="VNINDEX"),
        DataProvisioningRequest("download", "index-membership", symbol="VN30"),
        DataProvisioningRequest("download", "sector-membership", symbol="BANKS"),
        DataProvisioningRequest("build", "canonical", symbol="FPT"),
    )
    for request in requests:
        service.execute(request)

    assert [request.source for request in delegate.requests] == [
        "vci",
        "kbs",
        "kbs",
        "fiinquantx",
        "fiinquantx",
        "fiinquantx",
        None,
    ]


def test_reference_symbols_reject_fiinquantx_explicitly() -> None:
    with pytest.raises(InvalidSourceForDataset):
        resolve_maintenance_source_policy(reference_source="fiinquantx")


def test_policy_serialization_records_independent_dataset_ownership() -> None:
    policy = resolve_maintenance_source_policy(
        reference_source="vci",
        equity_source="kbs",
        index_source="vci",
    )
    payload = policy.to_dict()
    assert payload["reference.symbols"]["source"] == "vci"
    assert payload["equity.ohlcv"]["source"] == "kbs"
    assert payload["index.ohlcv"]["source"] == "vci"
    assert payload["reference.index_membership_snapshot"]["source"] == "vci"
