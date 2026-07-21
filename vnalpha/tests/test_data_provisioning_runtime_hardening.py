from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock


def test_market_regime_builder_receives_date_and_complete_is_success() -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
        ProvisioningStatus,
    )

    snapshot = MagicMock(
        quality="COMPLETE",
        methodology_version="market-regime-v1",
        generated_at="2026-07-10T10:00:00+00:00",
        lineage={"benchmark_input": "canonical_ohlcv"},
    )
    builder = MagicMock(return_value=snapshot)
    service = DataProvisioningService(
        MagicMock(),
        dependencies=DataProvisioningDependencies(build_market_regime=builder),
    )

    result = service.execute(
        DataProvisioningRequest("build", "market-regime", date="2026-07-10")
    )

    assert builder.call_args.args[1] == date(2026, 7, 10)
    assert result.status is ProvisioningStatus.SUCCESS
    assert result.freshness == "exact"
    assert result.lineage["methodology_version"] == "market-regime-v1"
