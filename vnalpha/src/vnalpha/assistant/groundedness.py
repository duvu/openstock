"""Fail-closed groundedness validation for deep research answers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan

_DECIMAL_RE = re.compile(r"(?<![\w-])[-+]?\d+\.\d+%?")
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@dataclass(frozen=True, slots=True)
class GroundednessResult:
    status: str
    valid_source_refs: tuple[str, ...] = ()
    unsupported_source_refs: tuple[str, ...] = ()
    unsupported_numeric_claims: tuple[str, ...] = ()
    undisclosed_missing_data: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "valid_source_refs": list(self.valid_source_refs),
            "unsupported_source_refs": list(self.unsupported_source_refs),
            "unsupported_numeric_claims": list(self.unsupported_numeric_claims),
            "undisclosed_missing_data": list(self.undisclosed_missing_data),
            "messages": list(self.messages),
        }


class GroundednessValidator:
    """Validate references, decimal metrics, and missing-data disclosure."""

    def validate(
        self,
        answer: AssistantAnswer,
        plan: AssistantPlan,
        tool_outputs: dict[str, Any],
    ) -> GroundednessResult:
        valid_refs = _valid_source_refs(plan, tool_outputs)
        supplied_refs = tuple(dict.fromkeys(answer.grounded_source_refs))
        unsupported_refs = tuple(ref for ref in supplied_refs if ref not in valid_refs)
        payload_values = _numeric_payload_values(tool_outputs)
        unsupported_numbers = tuple(
            claim
            for claim in _decimal_claims(answer)
            if not _matches_payload_number(claim, payload_values)
        )
        required_missing = _missing_data(tool_outputs)
        disclosed_text = " ".join(
            [
                answer.summary,
                answer.basis,
                answer.risks_caveats,
                *answer.missing_data,
            ]
        ).lower()
        undisclosed_missing = tuple(
            item for item in required_missing if item.lower() not in disclosed_text
        )

        messages: list[str] = []
        if not answer.basis.strip():
            messages.append("basis is empty")
        if not answer.risks_caveats.strip():
            messages.append("risks_caveats is empty")
        if not supplied_refs:
            messages.append("grounded_source_refs is empty")
        if unsupported_refs:
            messages.append("one or more source references are not present in the plan/tool payloads")
        if unsupported_numbers:
            messages.append("one or more decimal metrics are not present in tool payloads")
        if undisclosed_missing:
            messages.append("one or more missing artifacts were not disclosed")

        hard_fail = bool(
            unsupported_refs
            or unsupported_numbers
            or not supplied_refs
            or not answer.basis.strip()
            or not answer.risks_caveats.strip()
        )
        status = "FAIL" if hard_fail else "PARTIAL" if undisclosed_missing else "PASS"
        return GroundednessResult(
            status=status,
            valid_source_refs=tuple(sorted(valid_refs)),
            unsupported_source_refs=unsupported_refs,
            unsupported_numeric_claims=unsupported_numbers,
            undisclosed_missing_data=undisclosed_missing,
            messages=tuple(messages),
        )


def _valid_source_refs(
    plan: AssistantPlan, tool_outputs: dict[str, Any]
) -> set[str]:
    refs = {
        f"tool:{step.tool_name}:{step.step_id}" for step in plan.steps
    } | {step.tool_name for step in plan.steps} | {step.step_id for step in plan.steps}
    for output in tool_outputs.values():
        if not isinstance(output, dict):
            continue
        data = output.get("data", output)
        if not isinstance(data, dict):
            continue
        artifact_refs = data.get("artifact_refs", [])
        if isinstance(artifact_refs, (list, tuple)):
            refs.update(str(item) for item in artifact_refs if item)
    return refs


def _numeric_payload_values(tool_outputs: dict[str, Any]) -> set[float]:
    values: set[float] = set()

    def visit(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            numeric = float(value)
            for digits in range(0, 7):
                values.add(round(numeric, digits))
            if -1.0 <= numeric <= 1.0:
                for digits in range(0, 5):
                    values.add(round(numeric * 100.0, digits))
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)

    visit(tool_outputs)
    return values


def _decimal_claims(answer: AssistantAnswer) -> tuple[str, ...]:
    text = " ".join((answer.summary, answer.basis, answer.risks_caveats))
    text = _ISO_DATE_RE.sub("", text)
    return tuple(dict.fromkeys(_DECIMAL_RE.findall(text)))


def _matches_payload_number(claim: str, payload_values: set[float]) -> bool:
    is_percent = claim.endswith("%")
    try:
        value = float(claim.rstrip("%"))
    except ValueError:
        return False
    candidates = {round(value, digits) for digits in range(0, 7)}
    if is_percent:
        candidates.update(round(value / 100.0, digits) for digits in range(0, 7))
    return bool(candidates & payload_values)


def _missing_data(tool_outputs: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for output in tool_outputs.values():
        if not isinstance(output, dict):
            continue
        data = output.get("data", output)
        if not isinstance(data, dict):
            continue
        raw = data.get("missing_data", [])
        if isinstance(raw, (list, tuple)):
            values.extend(str(item) for item in raw if item)
    return tuple(dict.fromkeys(values))
