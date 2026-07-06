"""
Unit tests for DataResult and DataFrame.attrs metadata propagation.
"""

from datetime import datetime

import pandas as pd
import pytest

from vnstock.core.result import _FORBIDDEN_METADATA_KEYS, DataResult


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "symbol": ["FPT"],
            "time": [pd.Timestamp("2024-01-01")],
            "open": [100.0],
            "high": [105.0],
            "low": [99.0],
            "close": [103.0],
            "volume": [100000.0],
        }
    )


class TestDataResultMetadataPropagation:
    """Tasks 53-55: Metadata propagation via to_dataframe()."""

    def test_to_dataframe_returns_dataframe(self, sample_df):
        result = DataResult(dataset="equity.ohlcv", provider="KBS", data=sample_df)
        df = result.to_dataframe()
        assert isinstance(df, pd.DataFrame)

    def test_dataset_in_attrs(self, sample_df):
        """Task 53: dataset is attached to DataFrame.attrs."""
        result = DataResult(dataset="equity.ohlcv", provider="KBS", data=sample_df)
        df = result.to_dataframe()
        assert df.attrs["dataset"] == "equity.ohlcv"

    def test_provider_in_attrs(self, sample_df):
        result = DataResult(dataset="equity.ohlcv", provider="KBS", data=sample_df)
        df = result.to_dataframe()
        assert df.attrs["provider"] == "KBS"

    def test_quality_status_in_attrs(self, sample_df):
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            quality_status="PASS",
        )
        df = result.to_dataframe()
        assert df.attrs["quality_status"] == "PASS"

    def test_quality_key_backward_compat(self, sample_df):
        """Task 54: df.attrs['quality'] is set for backward compatibility."""
        report = {"checks": []}
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            quality_report=report,
        )
        df = result.to_dataframe()
        assert df.attrs["quality"] == report

    def test_empty_quality_report(self, sample_df):
        """Task 54: Empty quality report is still set in attrs."""
        result = DataResult(dataset="equity.ohlcv", provider="KBS", data=sample_df)
        df = result.to_dataframe()
        # quality_report defaults to empty dict — should be in attrs
        assert "quality" in df.attrs

    def test_diagnostics_in_attrs(self, sample_df):
        """Task 55: Diagnostics are attached to DataFrame.attrs."""
        diag = {"routing_reason": "default priority", "selected_provider": "KBS"}
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            diagnostics=diag,
        )
        df = result.to_dataframe()
        assert df.attrs["diagnostics"] == diag

    def test_fetched_at_in_attrs(self, sample_df):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            fetched_at=ts,
        )
        df = result.to_dataframe()
        assert df.attrs["fetched_at"] == ts

    def test_ingestion_run_id_in_attrs(self, sample_df):
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            ingestion_run_id="run-abc-123",
        )
        df = result.to_dataframe()
        assert df.attrs["ingestion_run_id"] == "run-abc-123"


class TestNoSecretsInMetadata:
    """Task 52: Auth secrets must not be in DataResult or DataFrame.attrs."""

    def test_forbidden_keys_defined(self):
        """Forbidden metadata keys set is non-empty."""
        assert len(_FORBIDDEN_METADATA_KEYS) > 0

    def test_password_not_in_forbidden_keys_not_in_result(self, sample_df):
        """'password' is listed in forbidden keys."""
        assert "password" in _FORBIDDEN_METADATA_KEYS

    def test_access_token_forbidden(self):
        assert "access_token" in _FORBIDDEN_METADATA_KEYS

    def test_dataresult_does_not_accept_token_field(self, sample_df):
        """DataResult has no token/password/api_key field."""
        result = DataResult(dataset="equity.ohlcv", provider="KBS", data=sample_df)
        result_dict = result.__dict__
        for forbidden in _FORBIDDEN_METADATA_KEYS:
            assert forbidden not in result_dict, (
                f"Forbidden key '{forbidden}' found in DataResult"
            )


class TestAuthDiagnosticsInDataResult:
    """Tasks 83-87: Safe auth metadata attaches to DataResult.diagnostics."""

    def test_auth_diagnostics_no_credential_material(self, sample_df):
        """Auth diagnostics must not contain token/password/secret."""
        from vnstock.core.auth.diagnostics import AuthDiagnostics

        diag = AuthDiagnostics.unauthenticated("KBS").to_dict()
        result = DataResult(
            dataset="equity.ohlcv",
            provider="KBS",
            data=sample_df,
            diagnostics={"auth": diag},
        )
        df = result.to_dataframe()
        auth_meta = df.attrs["diagnostics"]["auth"]
        body_str = str(auth_meta).lower()
        for dangerous in ["token", "password", "secret", "bearer", "api_key"]:
            assert dangerous not in body_str

    def test_unauthenticated_auth_diag(self, sample_df):
        """Unauthenticated diagnostics has correct defaults."""
        from vnstock.core.auth.diagnostics import AuthDiagnostics

        diag = AuthDiagnostics.unauthenticated("KBS")
        assert diag.auth_used is False
        assert diag.auth_type == "none"
        assert diag.provider == "KBS"

    def test_auth_diag_to_dict_safe(self):
        """to_dict() produces a plain dict with no credential material."""
        from vnstock.core.auth.diagnostics import AuthDiagnostics

        d = AuthDiagnostics(
            provider="TCBS",
            auth_used=True,
            auth_type="interactive",
            credential_label="tcbs:local_file",
            experimental=True,
        ).to_dict()
        assert isinstance(d, dict)
        assert d["auth_used"] is True
        assert d["auth_type"] == "interactive"
        assert d["provider"] == "TCBS"
        assert "token" not in d
        assert "password" not in d

    def test_build_diagnostics_attaches_auth(self, sample_df):
        """_build_diagnostics includes 'auth' key with safe data."""
        from unittest.mock import MagicMock

        from vnstock.core.runtime.plugin_runtime import PluginRuntime

        runtime = PluginRuntime.__new__(PluginRuntime)
        runtime._router = MagicMock()
        runtime.runtime_path = "test"
        diag = runtime._build_diagnostics(
            routing_decision=None,
            provider_diagnostics={},
            latency_ms=12.5,
            contract_errors=[],
            provider_name="KBS",
        )
        assert "auth" in diag
        assert diag["auth"]["auth_used"] is False
        assert diag["auth"]["auth_type"] == "none"

    def test_build_diagnostics_no_credential_in_provider_diag(self, sample_df):
        """Credential fields in provider_diagnostics are stripped."""
        from unittest.mock import MagicMock

        from vnstock.core.runtime.plugin_runtime import PluginRuntime

        runtime = PluginRuntime.__new__(PluginRuntime)
        runtime._router = MagicMock()
        runtime.runtime_path = "test"
        diag = runtime._build_diagnostics(
            routing_decision=None,
            provider_diagnostics={
                "api_key": "SHOULD_BE_STRIPPED",
                "access_token": "SHOULD_BE_STRIPPED",
                "safe_field": "ok",
            },
            latency_ms=None,
            contract_errors=[],
            provider_name="FMP",
        )
        provider_diag = diag.get("provider_diagnostics", {})
        assert "api_key" not in provider_diag
        assert "access_token" not in provider_diag
        if "safe_field" in diag.get("provider_diagnostics", {}):
            assert diag["provider_diagnostics"]["safe_field"] == "ok"

    def test_existing_quality_metadata_preserved(self, sample_df):
        """Auth diagnostics addition does not remove quality metadata."""
        from vnstock.core.auth.diagnostics import AuthDiagnostics

        auth_diag = AuthDiagnostics.unauthenticated("VCI").to_dict()
        result = DataResult(
            dataset="equity.ohlcv",
            provider="VCI",
            data=sample_df,
            quality_status="PASS",
            quality_report={"contract_errors": []},
            diagnostics={"auth": auth_diag, "routing": {"reason": "default"}},
        )
        df = result.to_dataframe()
        assert df.attrs["quality_status"] == "PASS"
        assert df.attrs["quality"]["contract_errors"] == []
        assert "auth" in df.attrs["diagnostics"]
        assert "routing" in df.attrs["diagnostics"]
