"""vnalpha test configuration."""

import pytest


@pytest.fixture
def tmp_warehouse(tmp_path):
    """Return a temporary DuckDB warehouse path."""
    return tmp_path / "test_warehouse.duckdb"


@pytest.fixture(autouse=True)
def reset_vnalpha_config():
    """Reset config singleton between tests."""
    from vnalpha.core.config import reset_config

    yield
    reset_config()
