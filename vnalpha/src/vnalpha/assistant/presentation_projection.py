from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep
from vnalpha.core.text_safety import sanitize_text

PRESENTATION_SCHEMA_VERSION = 1
MAX_PRESENTATION_ROWS = 50

_WATCHLIST_TOOLS = frozenset(
    {
        "watchlist.scan",
        "watchlist.filter",
        "watchlist.summarize_deep",
    }
)
_WATCHLIST_COLUMNS: tuple[dict[str, object], ...] = (
    {"name": "rank", "title": "Rank", "align": "right", "no_wrap": True},
    {"name": "symbol", "title": "Symbol", "align": "left", "no_wrap": True},
    {"name": "score", "title": "Score", "align": "right", "no_wrap": True},
    {"name": "class", "title": "Class", "align": "left", "no_wrap": False},
    {"name": "setup", "title": "Setup", "align": "left", "no_wrap": False},
    {
        "name": "risk_flags",
        "title": "Risk flags",
        "align": "left",
        "no_wrap": False,
    },
    {"name": "quality", "title": "Quality", "align": "left", "no_wrap": True},
)


def attach_assistant_presentation(
    answer: AssistantAnswer,
    plan: AssistantPlan,
    tool_outputs: Mapping[str, Any],
) -> AssistantAnswer:
    """Attach one bounded, transport-safe presentation projection to an answer."""

    projection = build_assistant_presentation(plan, tool_outputs)
    if projection:
        answer.research_metadata = {
            **answer.research_metadata,
            "presentation": projection,
        }
    return answer


def build_assistant_presentation(
    plan: AssistantPlan,
    tool_outputs: Mapping[str, Any],
) -> dict[str, object]:
    """Project allowlisted assistant tool results into a versioned UI contract."""

    tables: list[dict[str, object]] = []
    for step in plan.steps:
        if step.tool_name not in _WATCHLIST_TOOLS:
            continue
        table = _watchlist_table(step, tool_outputs.get(step.step_id))
        if table is not None:
            tables.append(table)
    if not tables:
        return {}
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "tables": tables,
    }


def _watchlist_table(
    step: ToolPlanStep,
    output: object,
) -> dict[str, object] | None:
    data = _tool_data(output)
    effective_date = step.arguments.get("date")

    if step.tool_name == "watchlist.summarize_deep":
        if not isinstance(data, Mapping):
            return None
        raw_rows = data.get("top_candidates")
        effective_date = data.get("as_of_date") or effective_date
        title_prefix = "Watchlist top candidates"
    else:
        raw_rows = data
        title_prefix = (
            "Filtered watchlist"
            if step.tool_name == "watchlist.filter"
            else "Watchlist"
        )

    rows = _mapping_rows(raw_rows)
    if rows is None:
        return None
    total_rows = len(rows)
    visible_rows = rows[:MAX_PRESENTATION_ROWS]
    truncated = total_rows > len(visible_rows)

    return {
        "kind": "watchlist",
        "title": _table_title(
            title_prefix,
            effective_date=effective_date,
            shown_rows=len(visible_rows),
            total_rows=total_rows,
            truncated=truncated,
        ),
        "columns": [dict(column) for column in _WATCHLIST_COLUMNS],
        "rows": [_candidate_row(row) for row in visible_rows],
        "total_rows": total_rows,
        "truncated": truncated,
    }


def _tool_data(output: object) -> object:
    if isinstance(output, Mapping):
        return output.get("data", output)
    return getattr(output, "data", output)


def _mapping_rows(value: object) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    return [row for row in value if isinstance(row, Mapping)]


def _candidate_row(row: Mapping[str, Any]) -> list[str]:
    quality = (
        row.get("data_quality_status")
        or row.get("quality_status")
        or row.get("quality")
    )
    risk_flags = row.get("risk_flags")
    if risk_flags is None:
        risk_flags = row.get("risk_flags_json")
    return [
        _cell(row.get("rank")),
        _cell(row.get("symbol")),
        _score(row.get("score")),
        _cell(row.get("candidate_class")),
        _cell(row.get("setup_type")),
        _risk_flags(risk_flags),
        _cell(quality),
    ]


def _table_title(
    prefix: str,
    *,
    effective_date: object,
    shown_rows: int,
    total_rows: int,
    truncated: bool,
) -> str:
    date_part = _cell(effective_date)
    if truncated:
        count_part = f"showing {shown_rows} of {total_rows} candidates"
    else:
        noun = "candidate" if total_rows == 1 else "candidates"
        count_part = f"{total_rows} {noun}"
    return sanitize_text(f"{prefix} · {date_part} · {count_part}").strip()


def _score(value: object) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _cell(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:.3f}"


def _risk_flags(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                pass
            else:
                return _risk_flags(decoded)
        return _cell(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        flags = [_cell(item) for item in value]
        visible = [flag for flag in flags if flag != "—"]
        return ", ".join(visible) if visible else "—"
    return "—"


def _cell(value: object) -> str:
    if value is None:
        return "—"
    text = sanitize_text(value).strip()
    return text or "—"


__all__ = [
    "MAX_PRESENTATION_ROWS",
    "PRESENTATION_SCHEMA_VERSION",
    "attach_assistant_presentation",
    "build_assistant_presentation",
]
