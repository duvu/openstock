from __future__ import annotations

import pytest
from rich.text import Text

from vnalpha.chat.errors import sanitize_public_error


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
    ],
)
def test_public_error_redacts_common_credential_forms(
    message: str, private_fragment: str
) -> None:
    # When
    sanitized = sanitize_public_error(message)

    # Then
    assert private_fragment not in sanitized
    assert "[REDACTED]" in sanitized
