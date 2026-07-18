from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from rich.text import Text

from vnalpha.chat.errors import sanitize_public_error
from vnalpha.core.text_safety import sanitize_error_summary, sanitize_text
from vnalpha.observability.errors import capture_exception
from vnalpha.observability.redaction import redact_dict, redact_str


def test_scan_cropped_jwt_redacts_before_first_segment_delimiter() -> None:
    header = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "pad": "x" * 9_000}).encode()
        )
        .decode()
        .rstrip("=")
    )
    token = f"{header}.eyJzdWIiOiJ1In0.signature1234"
    message = ("x" * 3_800) + " " + token

    for projection in (sanitize_public_error, sanitize_error_summary):
        result = projection(message)
        assert "[REDACTED]" in result
        assert header[:64] not in result


def test_unsecured_jwt_with_punctuation_is_redacted() -> None:
    message = "token eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjM0NTYifQ., retry"

    for projection in (sanitize_text, sanitize_public_error, sanitize_error_summary):
        result = projection(message)
        assert "eyJhbGciOiJub25lIn0" not in result
        assert "[REDACTED], retry" in result


@pytest.mark.parametrize(
    "message",
    [
        "See [postgresql://localhost:5432]",
        "See <postgresql://localhost:5432>",
        "See `postgresql://localhost:5432`",
    ],
)
def test_wrapped_endpoints_remain_visible_without_active_markup(message: str) -> None:
    assert sanitize_text(message) == message
    assert sanitize_error_summary(message) == message
    assert redact_str(message, mode="redacted") == message

    public = sanitize_public_error(message)
    rendered = Text.from_markup(public)
    assert rendered.plain == message
    assert rendered.spans == []


def test_error_record_sanitizes_keys_and_preserves_operational_token_metrics(
    tmp_path,
) -> None:
    run_context = SimpleNamespace(
        run_id="issue-230-key-content",
        surface="test",
        errors_path=tmp_path / "errors.jsonl",
    )

    try:
        raise RuntimeError("controlled failure")
    except RuntimeError as exc:
        capture_exception(
            exc,
            context={
                "metrics": {
                    "token_budgets": {"symbol_card": 1_600},
                    "token_estimate": 77,
                    "before_token_estimate": 80,
                    "auth_status": "configured",
                },
                "password=key-secret-private-230": "benign",
                "Bearer key-private-230": "benign",
            },
            run_ctx=run_context,
            mode="redacted",
        )

    record = json.loads(run_context.errors_path.read_text().strip())
    assert record["context"]["metrics"] == {
        "token_budgets": {"symbol_card": 1_600},
        "token_estimate": 77,
        "before_token_estimate": 80,
        "auth_status": "configured",
    }
    serialized = json.dumps(record, sort_keys=True)
    assert "key-secret-private-230" not in serialized
    assert "key-private-230" not in serialized


def test_redacted_mapping_preserves_safe_non_string_keys() -> None:
    assert redact_dict({1: "safe"}, mode="redacted") == {1: "safe"}
