"""Smoke tests for vnstock-service contract."""

import inspect

import pytest

from vnstock.service.dataset_mapper import MapperError, path_to_dataset


def test_reference_symbols_endpoint():
    assert path_to_dataset("/v1/reference/symbols") == "reference.symbols"


def test_equity_ohlcv_endpoint():
    assert path_to_dataset("/v1/equity/ohlcv") == "equity.ohlcv"


def test_equity_quote_endpoint():
    assert path_to_dataset("/v1/equity/quote") == "equity.quote"


def test_index_ohlcv_endpoint():
    assert path_to_dataset("/v1/index/ohlcv") == "index.ohlcv"


def test_all_required_endpoints_exist():
    """All endpoints required by vnalpha must be mappable."""
    required = [
        "/v1/reference/symbols",
        "/v1/equity/ohlcv",
        "/v1/equity/quote",
        "/v1/index/ohlcv",
    ]
    for path in required:
        dataset = path_to_dataset(path)
        assert isinstance(dataset, str)
        assert "." in dataset


def test_unknown_endpoint_raises():
    with pytest.raises(MapperError):
        path_to_dataset("/v1/unknown/endpoint")


def test_providers_health_route_exists():
    """Verify that /v1/providers/health is handled in server routes."""
    from vnstock.service import server

    src = inspect.getsource(server)
    assert "/v1/providers/health" in src


def test_providers_capabilities_route_exists():
    from vnstock.service import server

    src = inspect.getsource(server)
    assert "/v1/providers/capabilities" in src


# ---------------------------------------------------------------------------
# dataset_mapper correctness
# ---------------------------------------------------------------------------


def test_mapper_error_carries_path():
    bad_path = "/v1/does/not/exist"
    with pytest.raises(MapperError) as exc_info:
        path_to_dataset(bad_path)
    assert exc_info.value.path == bad_path


def test_mapper_error_is_value_error():
    with pytest.raises(ValueError):
        path_to_dataset("/v1/bad/path")


def test_trailing_slash_normalised():
    """Trailing slashes on paths must not cause a MapperError."""
    assert path_to_dataset("/v1/equity/ohlcv/") == "equity.ohlcv"
    assert path_to_dataset("/v1/reference/symbols/") == "reference.symbols"


def test_deprecated_alias_returns_canonical_dataset():
    """Deprecated alias must still resolve to the canonical dataset name."""
    with pytest.warns(DeprecationWarning):
        result = path_to_dataset("/v1/market/ohlcv")
    assert result == "equity.ohlcv"


def test_deprecated_listing_alias():
    with pytest.warns(DeprecationWarning):
        result = path_to_dataset("/v1/reference/listing")
    assert result == "reference.symbols"


def test_dataset_names_are_dotted():
    """Every canonical mapping must produce a dotted dataset name."""
    from vnstock.service.dataset_mapper import _CANONICAL

    for path, dataset in _CANONICAL.items():
        assert "." in dataset, f"Dataset for '{path}' has no dot: '{dataset}'"


# ---------------------------------------------------------------------------
# extract_runtime_params
# ---------------------------------------------------------------------------


def test_extract_runtime_params_source():
    from vnstock.service.dataset_mapper import extract_runtime_params

    result = extract_runtime_params({"source": ["kbs"], "symbol": ["FPT"]})
    assert result == {"source": "kbs"}


def test_extract_runtime_params_all_keys():
    from vnstock.service.dataset_mapper import extract_runtime_params

    q = {"source": ["vci"], "validate": ["true"], "quality_mode": ["raise"]}
    result = extract_runtime_params(q)
    assert result == {"source": "vci", "validate": "true", "quality_mode": "raise"}


def test_extract_runtime_params_empty():
    from vnstock.service.dataset_mapper import extract_runtime_params

    assert extract_runtime_params({}) == {}


def test_extract_runtime_params_ignores_data_params():
    from vnstock.service.dataset_mapper import extract_runtime_params

    result = extract_runtime_params({"symbol": ["FPT"], "start": ["2024-01-01"]})
    assert result == {}


# ---------------------------------------------------------------------------
# server module structure
# ---------------------------------------------------------------------------


def test_server_has_run_server_function():
    from vnstock.service import server

    assert callable(server.run_server)


def test_server_default_port_is_6900():
    import inspect

    from vnstock.service.server import run_server

    sig = inspect.signature(run_server)
    assert sig.parameters["port"].default == 6900


def test_server_default_host_is_localhost():
    import inspect

    from vnstock.service.server import run_server

    sig = inspect.signature(run_server)
    assert sig.parameters["host"].default == "127.0.0.1"
