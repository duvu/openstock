from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from rich.text import Text

from vnalpha.chat.errors import sanitize_public_error
from vnalpha.core.text_safety import sanitize_error_summary
from vnalpha.observability.errors import capture_exception
from vnalpha.observability.redaction import redact_str

_PRIVATE_FRAGMENTS = (
    "dsn-private-tail-230",
    "basic-private-tail-230",
    "jwt-private-tail-230",
    "pem-private-tail-230",
)


def test_public_error_escapes_arbitrary_rich_markup() -> None:
    # Given
    message = (
        "[link=https://evil.example]details[/link] "
        "[#ff00ff]deceptive[/#ff00ff] [bold red]urgent[/bold red]"
    )

    # When
    sanitized = sanitize_public_error(message)
    rendered = Text.from_markup(sanitized)

    # Then
    assert rendered.spans == []
    assert "details" in rendered.plain
    assert "deceptive" in rendered.plain
    assert "urgent" in rendered.plain


def test_public_error_truncation_cannot_reactivate_rich_markup() -> None:
    # Given
    markup = "[link=https://evil.example]details[/link]"
    message = "x" * 2_001 + markup + "y" * (3_071 - len(markup))
    assert len(message) == 5_072

    # When
    sanitized = sanitize_public_error(message)
    rendered = Text.from_markup(sanitized)

    # Then
    assert len(sanitized) <= 4_096
    assert rendered.spans == []


@pytest.mark.parametrize(
    "message, private_fragment",
    [
        (
            "database failed at postgresql://alice:s3cr3t@db.internal/research",
            "s3cr3t",
        ),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        (
            "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        ),
        (
            "-----BEGIN PRIVATE KEY-----\nprivate-key-material-230\n"
            "-----END PRIVATE KEY-----",
            "private-key-material-230",
        ),
        (
            '{"Authorization": "Bearer quoted-auth-private-230"}',
            "quoted-auth-private-230",
        ),
        (
            "Authorization=Basic equals-auth-private-230",
            "equals-auth-private-230",
        ),
        ("Basic c3RhbmRhbG9uZS1wcml2YXRlLTIzMA==", "cml2YXRlLTIzMA"),
        (
            'Authorization: Basic "quoted auth private 230"',
            "quoted auth private 230",
        ),
        ("bearer=legacy-private-230", "legacy-private-230"),
        ("Bearer: legacy-colon-private-230", "legacy-colon-private-230"),
        ("Bearer standalone-private-230", "standalone-private-230"),
        (
            'password="correct horse battery staple"',
            "horse battery staple",
        ),
        ("api_key='alpha beta gamma'", "beta gamma"),
    ],
)
def test_error_projections_redact_common_credential_forms(
    message: str, private_fragment: str
) -> None:
    # When
    sanitized_values = (
        sanitize_public_error(message),
        sanitize_error_summary(message),
        redact_str(message, mode="redacted"),
    )

    # Then
    for sanitized in sanitized_values:
        assert private_fragment not in sanitized
        assert "[REDACTED]" in sanitized


def _boundary_crossing_credentials() -> tuple[str, ...]:
    padding = "x" * 3_000
    tail_padding = "z" * 5_000
    tail = " remediation=/data-sync-FPT correlation_id=boundary-230"
    return (
        padding
        + " postgresql://alice:"
        + ("d" * 3_500)
        + _PRIVATE_FRAGMENTS[0]
        + "@db.internal/research"
        + tail_padding
        + tail,
        padding
        + " Authorization: Basic "
        + ("b" * 3_500)
        + _PRIVATE_FRAGMENTS[1]
        + tail_padding
        + tail,
        padding
        + " eyJhbGciOiJIUzI1NiJ9."
        + ("j" * 3_500)
        + "."
        + _PRIVATE_FRAGMENTS[2]
        + tail_padding
        + tail,
        padding
        + " -----BEGIN PRIVATE KEY-----\n"
        + ("p" * 3_500)
        + _PRIVATE_FRAGMENTS[3]
        + "\n-----END PRIVATE KEY-----"
        + tail_padding
        + tail,
    )


@pytest.mark.parametrize("message", _boundary_crossing_credentials())
def test_oversized_public_error_does_not_retain_credential_tail(message: str) -> None:
    sanitized = sanitize_public_error(message)

    assert not any(fragment in sanitized for fragment in _PRIVATE_FRAGMENTS)


@pytest.mark.parametrize("message", _boundary_crossing_credentials())
def test_oversized_audit_summary_does_not_retain_credential_tail(message: str) -> None:
    sanitized = sanitize_error_summary(message)

    assert not any(fragment in sanitized for fragment in _PRIVATE_FRAGMENTS)


@pytest.mark.parametrize("message", _boundary_crossing_credentials())
def test_observability_redaction_uses_common_credential_boundary(message: str) -> None:
    sanitized = redact_str(message, mode="redacted")

    assert not any(fragment in sanitized for fragment in _PRIVATE_FRAGMENTS)


def test_captured_error_record_contains_no_common_credential_payload(tmp_path) -> None:
    message = " ".join(_boundary_crossing_credentials())
    run_context = SimpleNamespace(
        run_id="issue-230-capture",
        surface="test",
        errors_path=tmp_path / "errors.jsonl",
    )

    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        capture_exception(
            exc,
            context={
                "detail": "Basic c3RhbmRhbG9uZS1wcml2YXRlLTIzMA==",
                "legacy": "bearer=record-private-230",
            },
            run_ctx=run_context,
            likely_cause='Authorization: Basic "quoted auth private 230"',
            suggested_next='password="suggested-next-private-230"',
            mode="redacted",
        )

    record = json.loads(run_context.errors_path.read_text().strip())
    persisted = json.dumps(record, sort_keys=True)
    assert record["redaction_status"] == "redacted"
    assert not any(fragment in persisted for fragment in _PRIVATE_FRAGMENTS)
    assert "cml2YXRlLTIzMA" not in persisted
    assert "quoted auth private 230" not in persisted
    assert "suggested-next-private-230" not in persisted
    assert "record-private-230" not in persisted
