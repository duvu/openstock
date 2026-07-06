"""Tests for vnstock.service.serializers."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from vnstock.core.result import DataResult
from vnstock.service.serializers import (
    RequestContext,
    _redact,
    serialize_data_result,
)


def _make_result(
    *,
    dataset: str = "equity.ohlcv",
    provider: str = "KBS",
    data: pd.DataFrame | None = None,
    quality_status: str | None = "PASS",
    diagnostics: dict | None = None,
    fetched_at: datetime | None = None,
) -> DataResult:
    if data is None:
        data = pd.DataFrame({"time": ["2024-01-01"], "close": [100.0]})
    if fetched_at is None:
        fetched_at = datetime(2026, 7, 3, 0, 0, 0, tzinfo=timezone.utc)
    return DataResult(
        dataset=dataset,
        provider=provider,
        data=data,
        quality_status=quality_status,
        diagnostics=diagnostics or {"runtime_path": "plugin_runtime"},
        fetched_at=fetched_at,
    )


class TestRedact:
    """Test the _redact helper."""

    def test_removes_password(self):
        assert _redact({"password": "secret", "foo": "bar"}) == {"foo": "bar"}

    def test_removes_api_key(self):
        assert _redact({"api_key": "xyz"}) == {}

    def test_removes_access_token(self):
        assert _redact({"access_token": "tok"}) == {}

    def test_removes_refresh_token(self):
        assert _redact({"refresh_token": "tok"}) == {}

    def test_removes_cookie(self):
        assert _redact({"cookie": "sid=abc"}) == {}

    def test_case_insensitive(self):
        assert _redact({"PASSWORD": "x"}) == {}

    def test_nested_removal(self):
        obj = {"outer": {"token": "secret", "safe": "ok"}}
        result = _redact(obj)
        assert result["outer"] == {"safe": "ok"}

    def test_list_passthrough(self):
        result = _redact([{"token": "bad"}, {"safe": "ok"}])
        assert result == [{}, {"safe": "ok"}]

    def test_safe_keys_preserved(self):
        obj = {"routing": {"decision": "auto"}, "latency_ms": 42}
        assert _redact(obj) == obj


class TestSerializeDataResult:
    """Test the serialize_data_result function."""

    def test_envelope_has_required_keys(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert "data" in envelope
        assert "meta" in envelope
        assert "diagnostics" in envelope

    def test_data_is_list_of_records(self):
        df = pd.DataFrame(
            {"time": ["2024-01-01", "2024-01-02"], "close": [100.0, 101.0]}
        )
        result = _make_result(data=df)
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert isinstance(envelope["data"], list)
        assert len(envelope["data"]) == 2
        assert envelope["data"][0]["close"] == 100.0

    def test_meta_request_id(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv", request_id="req_test123")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["request_id"] == "req_test123"

    def test_meta_dataset(self):
        result = _make_result(dataset="equity.ohlcv")
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["dataset"] == "equity.ohlcv"

    def test_meta_provider(self):
        result = _make_result(provider="VCI")
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["provider"] == "VCI"

    def test_meta_quality_status(self):
        result = _make_result(quality_status="PASS")
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["quality_status"] == "PASS"

    def test_meta_fetched_at(self):
        dt = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
        result = _make_result(fetched_at=dt)
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert "2026-07-03" in envelope["meta"]["fetched_at"]

    def test_meta_source_requested_default(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["source_requested"] == "auto"

    def test_meta_source_requested_explicit(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv", source_requested="KBS")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["source_requested"] == "KBS"

    def test_meta_runtime_path(self):
        result = _make_result(diagnostics={"runtime_path": "plugin_runtime"})
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["runtime_path"] == "plugin_runtime"

    def test_diagnostics_shape(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        diag = envelope["diagnostics"]
        assert "routing" in diag
        assert "provider_diagnostics" in diag
        assert "quality" in diag
        assert "warnings" in diag

    def test_auto_request_id_generated(self):
        result = _make_result()
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        assert envelope["meta"]["request_id"].startswith("req_")


class TestRedactionInEnvelope:
    """Sensitive fields must never appear in serialized envelopes."""

    SENSITIVE_KEYS = ["password", "api_key", "access_token", "refresh_token", "cookie"]

    @pytest.mark.parametrize("key", SENSITIVE_KEYS)
    def test_sensitive_key_not_in_diagnostics(self, key):
        result = _make_result(
            diagnostics={"runtime_path": "plugin_runtime", key: "should-be-redacted"}
        )
        ctx = RequestContext(dataset="equity.ohlcv")
        envelope = serialize_data_result(result, ctx)
        diag_str = str(envelope["diagnostics"]).lower()
        assert "should-be-redacted" not in diag_str

    def test_no_credential_in_full_envelope(self):
        result = _make_result(
            diagnostics={
                "runtime_path": "plugin_runtime",
                "provider_diagnostics": {
                    "api_key": "super-secret-key",
                    "latency_ms": 42,
                },
            }
        )
        ctx = RequestContext(dataset="equity.ohlcv")
        import json

        envelope_str = json.dumps(serialize_data_result(result, ctx))
        assert "super-secret-key" not in envelope_str
