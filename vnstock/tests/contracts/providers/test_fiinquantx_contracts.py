"""Contract fixtures for FiinQuantX documentation drift.

These tests preserve synthetic payload variants that must be explicit in the
normalization boundary contract and keep unsupported variants from being
mistakenly treated as production truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from vnstock.providers.fiinquantx.normalize import normalize_ohlcv

_FIXTURES = (
    Path(__file__).parent.parent.parent / "fixtures" / "providers" / "fiinquantx"
)

pytestmark = pytest.mark.contract


def _load_fixture(name: str):
    path = _FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _normalize_fixture_rows(name: str) -> pd.DataFrame:
    return normalize_ohlcv(pd.DataFrame(_load_fixture(name)), "equity.ohlcv")


class TestFiinQuantXInconsistencyFixtures:
    """Track documented inconsistencies as explicit regression fixtures."""

    def test_timestamp_string_variant_normalizes(self):
        normalized = _normalize_fixture_rows("ohlcv_timestamp_string.json")

        assert list(normalized.columns) == [
            "symbol",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
        ]
        assert normalized.loc[0, "symbol"] == "VCB"
        assert normalized.loc[0, "time"].date() == pd.Timestamp("2026-07-14").date()

    def test_timestamp_integer_ms_variant_normalizes(self):
        normalized = _normalize_fixture_rows("ohlcv_timestamp_integer_ms.json")

        assert normalized.loc[0, "time"].date() == pd.Timestamp("2026-07-14").date()

    def test_field_casing_variant_is_normalized(self):
        normalized = _normalize_fixture_rows("ohlcv_field_casing.json")

        assert normalized.loc[0, "symbol"] == "VCB"
        assert normalized.loc[0, "time"].date() == pd.Timestamp("2026-07-14").date()

    def test_return_payload_variant_and_unknown_semantics_are_documented(self):
        flow_fixture = _load_fixture("flows_fb_fs_direction_ambiguity.json")
        freefloat_fixture = _load_fixture("freefloat_unit_variants.json")

        assert flow_fixture["notes"].startswith("Direction")
        assert len(flow_fixture["rows"]) == 2
        assert freefloat_fixture["notes"].startswith("Free-float unit is unresolved")
        assert len(freefloat_fixture["rows"]) == 2
