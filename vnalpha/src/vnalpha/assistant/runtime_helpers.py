from __future__ import annotations

import json
import os
from datetime import date

from vnalpha.assistant.effective_date import normalize_date_candidate
from vnalpha.assistant.errors import RefusalError
from vnalpha.assistant.models import (
    AssistantPlan,
    AssistantRequest,
    PromptPersistenceRecord,
    RefusalMessage,
    text_hash,
)
from vnalpha.data_availability.dates import normalize_optional_date
from vnalpha.workspace_context.redaction import redact_workspace_text


def _prompt_projection(request: AssistantRequest) -> PromptPersistenceRecord:
    redacted = redact_workspace_text(request.current_user_prompt).text
    prompt_digest = text_hash(redacted)
    raw_stored = os.environ.get("VNALPHA_ASSISTANT_STORE_RAW", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    workspace_ref = (
        text_hash(request.workspace_context)
        if request.workspace_context is not None
        else None
    )
    chat_payload = (
        json.dumps(request.to_dict()["chat_context"], sort_keys=True)
        if request.chat_context is not None
        else None
    )
    chat_ref = text_hash(chat_payload) if chat_payload is not None else None
    summary = f"prompt chars={len(redacted)} sha256={prompt_digest}"
    return PromptPersistenceRecord(
        prompt_text=redacted if raw_stored else None,
        prompt_summary=summary,
        prompt_hash=prompt_digest,
        prompt_chars=len(redacted),
        workspace_context_ref=workspace_ref,
        chat_context_ref=chat_ref,
        raw_stored=raw_stored,
    )


def _refusal_result(exc: RefusalError) -> tuple[RefusalMessage, AssistantPlan]:
    reason = exc.args[0] if exc.args else str(exc)
    return (
        RefusalMessage(
            reason=reason,
            policy_category=getattr(exc, "policy_category", "UNKNOWN"),
            suggestion=getattr(exc, "suggestion", None),
        ),
        AssistantPlan(
            intent="unsupported_or_unsafe",
            steps=[],
            refusal_reason=reason,
        ),
    )


def _request_as_of_date(value: str | None) -> date:
    normalized = normalize_date_candidate(value)
    return date.fromisoformat(normalize_optional_date(normalized))


def _log_assistant_lifecycle(event_type: str, operation: str, *, status: str) -> None:
    from vnalpha.observability.trace import log_trace

    log_trace(event_type, operation, status=status)
