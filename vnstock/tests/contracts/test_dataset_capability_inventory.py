from __future__ import annotations

from pathlib import Path
from typing import assert_never

from vnstock.core.capability_inventory import (
    CapabilityStatus,
    load_dataset_capability_inventory,
)
from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.service.dataset_mapper import canonical_dataset_routes


def test_dataset_capability_inventory_matches_runtime_contracts() -> None:
    inventory = load_dataset_capability_inventory()
    rows = {row.dataset: row for row in inventory.datasets}
    routes = canonical_dataset_routes()
    provider_datasets = {
        dataset
        for capabilities in default_plugin_registry().capability_matrix().values()
        for dataset in capabilities
    }
    service_contract = (
        Path(__file__).resolve().parents[2] / "docs" / "SERVICE_CONTRACT.md"
    ).read_text(encoding="utf-8")

    assert set(rows) == set(CONTRACT_REGISTRY.names())
    assert all(row.contract is CapabilityStatus.IMPLEMENTED for row in rows.values())
    assert provider_datasets <= set(rows)
    for row in rows.values():
        match row.service:
            case CapabilityStatus.IMPLEMENTED:
                assert row.service_route is not None
                assert routes[row.service_route] == row.dataset
                assert row.service_route in service_contract
            case (
                CapabilityStatus.PARTIAL
                | CapabilityStatus.EXPERIMENTAL
                | CapabilityStatus.UNSUPPORTED
                | CapabilityStatus.DEFERRED
            ):
                assert row.service_route is None
            case unexpected:
                assert_never(unexpected)
    assert rows["foreign_flow.daily"].service is CapabilityStatus.DEFERRED
    assert rows["foreign_flow.daily"].provider is CapabilityStatus.DEFERRED
    assert "fund.holdings" not in service_contract
