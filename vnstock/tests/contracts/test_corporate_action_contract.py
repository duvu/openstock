from __future__ import annotations

import pandas as pd
import pytest

from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.corporate_actions import (
    CORPORATE_ACTION_COLUMNS,
    normalize_corporate_actions,
)
from vnstock.providers.kbs.plugin import KBSProviderPlugin
from vnstock.providers.vci.plugin import VCIProviderPlugin
from vnstock.service.dataset_mapper import path_to_dataset


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "cash-1",
                "ticker": "SSI",
                "event_code": "DIV",
                "event_title_en": "Cash dividend",
                "public_date": "2024-01-02",
                "record_date": "2024-01-10",
                "exright_date": "2024-01-09",
                "value_per_share": 1_000,
            },
            {
                "id": "stock-1",
                "ticker": "SSI",
                "event_code": "DIV",
                "event_title_en": "Stock dividend ratio 10%",
                "public_date": "2024-02-02",
                "exercise_ratio": 0.10,
            },
            {
                "id": "bonus-1",
                "ticker": "SSI",
                "event_code": "ISS",
                "event_title_en": "Bonus Issue ratio 20%",
                "public_date": "2024-03-02",
                "exercise_ratio": 0.20,
            },
            {
                "id": "split-1",
                "ticker": "SSI",
                "event_code": "ISS",
                "event_title_en": "Stock split 1:2",
                "public_date": "2024-04-02",
                "exercise_ratio": 2.0,
            },
            {
                "id": "consolidate-1",
                "ticker": "SSI",
                "event_code": "ISS",
                "event_title_en": "Reverse split 2:1",
                "public_date": "2024-05-02",
                "exercise_ratio": 0.5,
            },
            {
                "id": "rights-1",
                "ticker": "SSI",
                "event_code": "ISS",
                "event_title_en": "Rights issue 2:1",
                "public_date": "2024-06-02",
                "exercise_ratio": 0.5,
                "issue_price": 10_000,
            },
        ]
    )


def test_contract_and_http_path_are_registered() -> None:
    contract = CONTRACT_REGISTRY.get("reference.corporate_actions")
    assert contract.required_columns == [
        "provider_event_id",
        "symbol",
        "action_type",
        "provider",
        "source_reference",
        "source_version",
        "content_hash",
        "source_payload_json",
    ]
    assert path_to_dataset("/v1/reference/corporate-actions") == (
        "reference.corporate_actions"
    )


def test_normalizer_covers_supported_action_taxonomy_and_provenance() -> None:
    result = normalize_corporate_actions(_rows(), provider="VCI", symbol="SSI")

    assert list(result.columns) == CORPORATE_ACTION_COLUMNS
    assert result["action_type"].tolist() == [
        "CASH_DIVIDEND",
        "STOCK_DIVIDEND",
        "STOCK_BONUS",
        "SPLIT",
        "CONSOLIDATION",
        "RIGHTS_ISSUE",
    ]
    assert result.loc[0, "cash_amount"] == 1_000
    assert result.loc[5, "subscription_price"] == 10_000
    assert result["ratio"].tolist() == [None, 0.1, 0.2, 2.0, 0.5, 0.5]
    assert result["content_hash"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert result["source_reference"].str.startswith("vci://company/SSI/events/").all()
    assert result.attrs["source_authority"] == "MARKET_DATA_PROVIDER"


def test_normalizer_is_deterministic_and_filters_bounded_dates() -> None:
    first = normalize_corporate_actions(
        _rows(), provider="KBS", symbol="SSI", start="2024-03-01", end="2024-04-30"
    )
    second = normalize_corporate_actions(
        _rows(), provider="KBS", symbol="SSI", start="2024-03-01", end="2024-04-30"
    )

    assert first.to_dict(orient="records") == second.to_dict(orient="records")
    assert first["provider_event_id"].tolist() == ["bonus-1", "split-1"]


def test_normalizer_accepts_vci_camel_case_payload() -> None:
    result = normalize_corporate_actions(
        [
            {
                "id": "camel-1",
                "ticker": "SSI",
                "eventCode": "DIV",
                "eventTitleEn": "Cash dividend",
                "publicDate": "2024-07-01",
                "exrightDate": "2024-07-08",
                "recordDate": "2024-07-09",
                "valuePerShare": 750,
            }
        ],
        provider="VCI",
        symbol="SSI",
    )
    assert result.loc[0, "action_type"] == "CASH_DIVIDEND"
    assert result.loc[0, "cash_amount"] == 750
    assert str(result.loc[0, "ex_date"]) == "2024-07-08"


def test_valid_empty_response_keeps_exact_contract() -> None:
    result = normalize_corporate_actions(pd.DataFrame(), provider="VCI", symbol="SSI")
    assert list(result.columns) == CORPORATE_ACTION_COLUMNS
    assert result.empty
    assert result.attrs["result_semantics"] == "valid_empty"


@pytest.mark.parametrize("plugin_type", [KBSProviderPlugin, VCIProviderPlugin])
def test_kbs_and_vci_declare_partial_corporate_action_capability(plugin_type) -> None:
    capability = plugin_type().capabilities()["reference.corporate_actions"]
    assert capability["supported"] is True
    assert capability["status"] == "partial"
    assert capability["auth_required"] is False


def test_provider_parameter_validation_is_bounded() -> None:
    plugin = KBSProviderPlugin()
    with pytest.raises(ValueError, match="start"):
        plugin.validate_params(
            "reference.corporate_actions",
            {"symbol": "SSI", "start": "2024-02-01", "end": "2024-01-01"},
        )
    with pytest.raises(ValueError, match="page_size"):
        plugin.validate_params(
            "reference.corporate_actions", {"symbol": "SSI", "page_size": 501}
        )
