from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from rich.text import Text

from vnalpha.chat.errors import (
    format_actionable_tool_failure,
    sanitize_public_error,
)
from vnalpha.closed_loop.events import EventInput, emit_event, event_types
from vnalpha.core.text_safety import sanitize_error_summary, sanitize_text
from vnalpha.observability.errors import capture_exception
from vnalpha.observability.redaction import redact_str
from vnalpha.tools.errors import PublicToolFailure


def test_actionable_fields_cannot_compose_rich_markup() -> None:
    output = format_actionable_tool_failure(
        PublicToolFailure(
            "safe [link=https://evil",
            ("]click[/link]",),
            "",
        )
    )

    assert Text.from_markup(output).spans == []
    assert len(output) <= 4_096


def test_long_basic_credential_is_redacted_across_scan_boundary() -> None:
    token = base64.b64encode(b"u:secret-private-230-" + (b"x" * 7_000)).decode()
    message = ("x" * 3_800) + " Basic " + token

    for projection in (sanitize_public_error, sanitize_error_summary):
        result = projection(message)
        assert "Basic [REDACTED]" in result
        assert "dTpzZWNyZXQtcHJpdmF0ZS0yMzA" not in result
        assert len(result) <= 4_096


def test_standalone_alphabetic_bearer_token_is_redacted() -> None:
    for projection in (sanitize_text, sanitize_public_error, sanitize_error_summary):
        result = projection("Bearer abcdef")
        assert result == "Bearer [REDACTED]"


@pytest.mark.parametrize(
    "message",
    [
        "Bearer shares remain a legacy security form.",
        "Bearer shares.",
        "Bearer Bonds: Market Overview",
        "Database unavailable at postgresql://localhost:5432.",
        "Database unavailable at postgresql://localhost:5432?sslmode=require",
        "Database unavailable at postgresql://[::1]:5432",
        "Cache unavailable at redis://localhost:6379?db=0",
        "See https://example.com:443?email=a@b",
        "Database unavailable at postgresql://localhost:5432?contact=a@b",
    ],
)
def test_shared_sanitizer_preserves_benign_consumers(message: str) -> None:
    assert sanitize_text(message) == message
    assert sanitize_public_error(message) == message
    assert sanitize_error_summary(message) == message
    assert redact_str(message, mode="redacted") == message


@pytest.mark.parametrize(
    "message",
    [
        "postgresql+psycopg://alice:s3cr3t-private-230",
        "postgresql+asyncpg://alice:s3cr3t-private-230",
        "mysql+pymysql://alice:s3cr3t-private-230",
    ],
)
def test_driver_qualified_cropped_dsn_is_redacted(message: str) -> None:
    for projection in (sanitize_text, sanitize_public_error, sanitize_error_summary):
        result = projection(message)
        assert "[REDACTED]" in result
        assert "s3cr3t-private-230" not in result


def test_error_record_redacts_common_nested_credential_keys(tmp_path) -> None:
    run_context = SimpleNamespace(
        run_id="issue-230-nested-keys",
        surface="test",
        errors_path=tmp_path / "errors.jsonl",
    )

    try:
        raise RuntimeError("controlled failure")
    except RuntimeError as exc:
        capture_exception(
            exc,
            context={
                "nested": [
                    {"auth_header": "auth-header-private-230"},
                    {"credential_value": "credential-private-230"},
                    {"cookie_header": "cookie-private-230"},
                ]
            },
            run_ctx=run_context,
            mode="redacted",
        )

    record = json.loads(run_context.errors_path.read_text().strip())
    assert record["redaction_status"] == "redacted"
    assert record["context"]["nested"] == [
        {"auth_header": "[REDACTED]"},
        {"credential_value": "[REDACTED]"},
        {"cookie_header": "[REDACTED]"},
    ]


def test_metadata_mode_retains_structural_closed_loop_fields(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_LOG_CONTENT_MODE", "metadata")
    emit_event(
        tmp_path,
        EventInput(
            event_type="REPAIR_FAILED",
            correlation_id="correlation-230",
            run_id="run-230",
            status="FAILED",
        ),
    )

    assert redact_str("correlation-230", mode="metadata") == "correlation-230"
    assert event_types(tmp_path, "events") == ["REPAIR_FAILED"]
    record_path = next(tmp_path.rglob("events.jsonl"))
    record = json.loads(record_path.read_text().strip())
    assert record["correlation_id"] == "correlation-230"
    assert record["run_id"] == "run-230"
    assert record["status"] == "FAILED"
    assert record["detail"] == ""
    assert record["redaction_status"] == "metadata"
