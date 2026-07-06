"""Tests for capability matrix (vnstock/core/provider/matrix.py)."""

from __future__ import annotations

from vnstock.core.provider.matrix import build_matrix, render_matrix_text


class TestBuildMatrix:
    """build_matrix returns correct structure."""

    def test_returns_required_keys(self):
        result = build_matrix()
        assert "providers" in result
        assert "dataset_types" in result
        assert "asset_classes" in result
        assert "matrix" in result
        assert "summary" in result

    def test_all_known_providers_present(self):
        result = build_matrix()
        providers = {p.lower() for p in result["providers"]}
        for expected in ("KBS", "VCI", "DNSE", "TCBS"):
            assert expected.lower() in providers

    def test_tcbs_supports_equity_ohlcv(self):
        result = build_matrix()
        assert result["matrix"]["TCBS"]["ohlcv"]["equity"] is True

    def test_all_dataset_types_present(self):
        result = build_matrix()
        assert "ohlcv" in result["dataset_types"]
        assert "intraday_trades" in result["dataset_types"]

    def test_matrix_shape(self):
        result = build_matrix()
        for provider in result["providers"]:
            assert provider in result["matrix"]
            for dt in result["dataset_types"]:
                assert dt in result["matrix"][provider]
                for ac in result["asset_classes"]:
                    val = result["matrix"][provider][dt][ac]
                    assert isinstance(val, bool)

    def test_vci_supports_equity_ohlcv(self):
        result = build_matrix()
        assert result["matrix"]["VCI"]["ohlcv"]["equity"] is True

    def test_fmp_requires_auth(self):
        """FMP is present in capabilities with requires_auth=True."""
        from vnstock.core.provider.capabilities import query_capabilities

        caps = query_capabilities(provider="FMP")
        assert len(caps) > 0
        for cap in caps:
            assert cap.requires_auth is True

    def test_filter_by_provider(self):
        result = build_matrix(providers=["VCI", "KBS"])
        assert set(result["providers"]) == {"VCI", "KBS"}

    def test_filter_by_dataset_type(self):
        result = build_matrix(dataset_types=["ohlcv"])
        assert result["dataset_types"] == ["ohlcv"]

    def test_filter_by_asset_class(self):
        result = build_matrix(asset_classes=["equity"])
        assert result["asset_classes"] == ["equity"]

    def test_summary_total_positive(self):
        result = build_matrix()
        for provider in result["providers"]:
            total = result["summary"][provider]["total"]
            assert isinstance(total, int)
            assert total >= 0

    def test_summary_dataset_types_subset(self):
        result = build_matrix()
        all_dts = set(result["dataset_types"])
        for provider in result["providers"]:
            provider_dts = set(result["summary"][provider]["dataset_types"])
            assert provider_dts.issubset(all_dts)

    def test_unknown_provider_filter_returns_empty(self):
        result = build_matrix(providers=["nonexistent_provider"])
        assert result["providers"] == []
        assert result["matrix"] == {}


class TestRenderMatrixText:
    """render_matrix_text produces non-empty string output."""

    def test_returns_string(self):
        matrix_dict = build_matrix()
        text = render_matrix_text(matrix_dict)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_contains_provider_names(self):
        matrix_dict = build_matrix(providers=["VCI", "KBS"])
        text = render_matrix_text(matrix_dict)
        assert "VCI" in text
        assert "KBS" in text

    def test_contains_check_mark_for_supported(self):
        matrix_dict = build_matrix(
            providers=["VCI"],
            dataset_types=["ohlcv"],
            asset_classes=["equity"],
        )
        text = render_matrix_text(matrix_dict)
        assert "✓" in text

    def test_multiline_output(self):
        matrix_dict = build_matrix()
        text = render_matrix_text(matrix_dict)
        lines = [line for line in text.splitlines() if line.strip()]
        # At least header + separator + one provider row
        assert len(lines) >= 3
