from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from vnalpha.assistant.groundedness import GroundednessResult
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.observability.context import get_correlation_id


def persist_research_answer_audit(
    conn,
    *,
    assistant_session_id: str,
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    answer: AssistantAnswer,
    groundedness: GroundednessResult,
) -> str:
    """Persist traceable metadata for one returned research-intelligence answer."""

    audit_id = str(uuid4())
    created_at = datetime.now(UTC)
    tools = [step.tool_name for step in plan.steps]
    caveats = _collect_caveats(tool_outputs, answer)
    conn.execute(
        """
        INSERT INTO research_answer_audit (
            research_answer_audit_id,
            assistant_session_id,
            created_at,
            intent,
            tools_json,
            artifact_refs_json,
            dataset_freshness_json,
            groundedness_status,
            groundedness_json,
            policy_status,
            caveats_json,
            correlation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            audit_id,
            assistant_session_id,
            created_at,
            plan.intent,
            _dump(tools),
            _dump(list(groundedness.artifact_refs)),
            _dump(groundedness.dataset_freshness),
            groundedness.status,
            _dump(groundedness.to_dict()),
            groundedness.policy_status,
            _dump(caveats),
            get_correlation_id(),
        ],
    )
    _emit_audit_event(
        audit_id=audit_id,
        assistant_session_id=assistant_session_id,
        intent=plan.intent,
        tools=tools,
        groundedness=groundedness,
    )
    return audit_id


def list_research_answer_audits(conn, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT research_answer_audit_id, assistant_session_id, created_at, intent,
               tools_json, artifact_refs_json, dataset_freshness_json,
               groundedness_status, groundedness_json, policy_status,
               caveats_json, correlation_id
        FROM research_answer_audit
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [max(1, min(int(limit), 200))],
    ).fetchall()
    keys = [
        "research_answer_audit_id",
        "assistant_session_id",
        "created_at",
        "intent",
        "tools",
        "artifact_refs",
        "dataset_freshness",
        "groundedness_status",
        "groundedness",
        "policy_status",
        "caveats",
        "correlation_id",
    ]
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(zip(keys, row, strict=True))
        for key in ("tools", "artifact_refs", "dataset_freshness", "groundedness", "caveats"):
            item[key] = json.loads(item[key]) if item[key] else None
        if item["created_at"] is not None:
            item["created_at"] = str(item["created_at"])
        result.append(item)
    return result


def _collect_caveats(
    tool_outputs: dict[str, Any], answer: AssistantAnswer
) -> list[str]:
    caveats: list[str] = []
    if answer.risks_caveats.strip():
        caveats.append(answer.risks_caveats.strip())

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {"caveats", "warnings"} and isinstance(nested, list):
                    caveats.extend(str(item) for item in nested if item)
                else:
                    walk(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested)

    walk(tool_outputs)
    return _dedupe(caveats)


def _emit_audit_event(
    *,
    audit_id: str,
    assistant_session_id: str,
    intent: str,
    tools: list[str],
    groundedness: GroundednessResult,
) -> None:
    try:
        from vnalpha.observability.audit import log_audit

        log_audit(
            "RESEARCH_ANSWER_AUDITED",
            f"Research answer audit persisted for {intent}",
            module="vnalpha.assistant.research_audit",
            session_id=assistant_session_id,
            object_type="research_answer_audit",
            object_id=audit_id,
            extra={
                "intent": intent,
                "tools": tools,
                "groundedness_status": groundedness.status,
                "policy_status": groundedness.policy_status,
                "artifact_ref_count": len(groundedness.artifact_refs),
            },
        )
    except Exception:  # noqa: BLE001
        pass


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = ["list_research_answer_audits", "persist_research_answer_audit"]
