from __future__ import annotations

from types import ModuleType

from vnstock.providers.fiinquantx.bridge import (
    FiinQuantXState,
    load_fiinquantx_sdk,
)


def test_missing_sdk_is_reported_without_import_failure() -> None:
    result = load_fiinquantx_sdk()

    assert result.state is FiinQuantXState.NOT_INSTALLED
    assert result.module is None
    assert result.version is None


def test_supported_sdk_uses_verified_import_name(monkeypatch) -> None:
    module = ModuleType("FiinQuantX")
    imported_names: list[str] = []

    def import_module(name: str) -> ModuleType:
        imported_names.append(name)
        return module

    monkeypatch.setattr("vnstock.providers.fiinquantx.bridge.version", lambda _: "0.1.64")
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.bridge.importlib.import_module",
        import_module,
    )

    result = load_fiinquantx_sdk()

    assert result.state is FiinQuantXState.INSTALLED_SUPPORTED
    assert result.module is module
    assert imported_names == ["FiinQuantX"]
