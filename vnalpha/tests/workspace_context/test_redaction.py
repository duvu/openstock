from __future__ import annotations

from vnalpha.workspace_context.redaction import redact_workspace_text


def test_workspace_redaction_reports_text_status_and_categories() -> None:
    value = redact_workspace_text("api_key=secret password=hidden compare FPT")

    assert value.text == "api_key=[REDACTED] password=[REDACTED] compare FPT"
    assert value.status == "redacted"
    assert value.matched_categories == ("api_key", "password")
