from __future__ import annotations

from vnalpha.commands.handlers.model import handle_model
from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.model_routing import DEFAULT_OVERRIDE_STORE


def test_model_command_is_registered() -> None:
    assert "model" in build_default_registry().names()


def test_models_alias_routes_to_model_profiles() -> None:
    parsed = parse("/models")
    assert parsed.command_name == "model"
    assert parsed.positional == ["profiles"]


def test_model_profiles_lists_all_profiles(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "provider/default")
    monkeypatch.setenv("VNALPHA_MODEL_SMALL", "provider/small")
    monkeypatch.setenv("VNALPHA_MODEL_REASONING", "provider/reasoning")
    monkeypatch.setenv("VNALPHA_MODEL_LONG_CONTEXT", "provider/long")

    result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model profiles",
            positional=["profiles"],
        )
    )

    assert result.status is CommandStatus.SUCCESS
    assert isinstance(result.panels[0].content, dict)
    profiles = result.panels[0].content["profiles"]
    assert {item["profile"] for item in profiles} == {
        "small",
        "default",
        "reasoning",
        "long_context",
    }


def test_model_explain_route_is_deterministic(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("VNALPHA_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("VNALPHA_MODEL_REASONING", "reasoning-model")
    DEFAULT_OVERRIDE_STORE.clear_override(scope="all")

    result = handle_model(
        ParsedCommand(
            command_name="model",
            raw_text="/model explain-route deep_symbol_analysis",
            positional=["explain-route", "deep_symbol_analysis"],
        )
    )

    assert result.status is CommandStatus.SUCCESS
    assert isinstance(result.panels[0].content, dict)
    assert result.panels[0].content["profile"] == "reasoning"
    assert result.panels[0].content["model_id"] == "reasoning-model"


def test_model_invalid_scope_is_validation_error_at_handler_boundary() -> None:
    parsed = ParsedCommand(
        command_name="model",
        raw_text="/model use small --scope global",
        positional=["use", "small"],
        options={"scope": "global"},
    )

    try:
        handle_model(parsed)
    except Exception as exc:
        assert type(exc).__name__ == "CommandValidationError"
        assert "scope" in str(exc)
    else:
        raise AssertionError("Expected invalid scope to be rejected")
