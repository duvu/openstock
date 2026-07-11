from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from vnalpha.assistant.groundedness import GroundednessResult
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.policy import ResearchPolicyResult
from vnalpha.observability.context import get_correlation_id


def persist_research_answer_audit(
    conn,
    *,
    assistant_session_id: str,
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    answer: AssistantAnswer,
    groundedness: GroundednessResult,
    policy: ResearchPolicyResult,
) -> str:
    """Persist compact, redaction-safe evidence for one research answer."""

    audit_id = str(uuid4())
    tools = [step.tool_name for step in plan.steps]
    artifact_refs = _collect_values(tool_outputs, "artifact_refs")
    freshness = _collect_freshness(tool_outputs)
    caveats = _dedupe(
        [
            answer.risks_caveats.strip(),
            *_collect_values(tool_outputs, "caveats"),
            *_collect_values(tool_outputs, "warnings"),
        ]
    )
    conn.execute(
        """
        INSERT INTO research_answer_audit (
            research_answer_audit_id, assistant_session_id, created_at, intent,
            tools_json, artifact_refs_json, dataset_freshness_json,
            groundedness_status, groundedness_json, policy_status, policy_json,
            caveats_json, correlation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            audit_id,
            assistant_session_id,
            datetime.now(UTC),
            plan.intent,
            _dump(tools),
            _dump(artifact_refs),
            _dump(freshness),
            groundedness.status,
            _dump(groundedness.to_dict()),
            policy.status,
            _dump(policy.to_dict()),
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
        policy=policy,
        artifact_ref_count=len(artifact_refs),
    )
    return audit_id


def list_research_answer_audits(conn, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT research_answer_audit_id, assistant_session_id, created_at, intent,
               tools_json, artifact_refs_json, dataset_freshness_json,
               groundedness_status, groundedness_json, policy_status,
               policy_json, caveats_json, correlation_id
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
        "policy",
        "caveats",
        "correlation_id",
    ]
    decoded: list[dict[str, Any]] = []
    for row in rows:
        item = dict(zip(keys, row, strict=True))
        for key in (
            "tools",
            "artifact_refs",
            "dataset_freshness",
            "groundedness",
            "policy",
            "caveats",
        ):
            item[key] = json.loads(item[key]) if item[key] else None
        if item["created_at"] is not None:
            item["created_at"] = str(item["created_at"])
        decoded.append(item)
    return decoded


def _emit_audit_event(
    *,
    audit_id: str,
    assistant_session_id: str,
    intent: str,
    tools: list[str],
    groundedness: GroundednessResult,
    policy: ResearchPolicyResult,
    artifact_ref_count: int,
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
                "policy_status": policy.status,
                "artifact_ref_count": artifact_ref_count,
            },
        )
    except Exception:  # noqa: BLE001
        pass


def _collect_values(value: Any, key_name: str) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == key_name:
                if isinstance(nested, (list, tuple, set)):
                    result.extend(str(item) for item in nested if item)
                elif nested:
                    result.append(str(nested))
            else:
                result.extend(_collect_values(nested, key_name))
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            result.extend(_collect_values(nested, key_name))
    return _dedupe(result)


def _collect_freshness(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                next_path = f"{path}.{key}" if path else str(key)
                if key in {
                    "freshness",
                    "as_of_date",
                    "as_of_bar_date",
                    "benchmark_as_of_bar_date",
                    "generated_at",
                    "computed_at",
                }:
                    result[next_path] = nested
                else:
                    visit(nested, next_path)
        elif isinstance(item, (list, tuple)):
            for index, nested in enumerate(item[:20]):
                visit(nested, f"{path}[{index}]")

    visit(value, "")
    return result


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


__all__ = ["list_research_answer_audits", "persist_research_answer_audit"]
