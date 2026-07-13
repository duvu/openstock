"""`/watchlist-summary` command handler."""

from __future__ import annotations

from collections.abc import Sequence

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_context_validation import validate_command_input
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultArtifact,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date


def handle_watchlist_summary(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    """Summarize persisted watchlist structure for research review."""
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/watchlist-summary",
            summary="No database connection.",
        )

    validate_command_input(parsed, {"date", "top"}, maximum_positionals=0)
    date = _requested_date(parsed)
    top = _top(parsed)

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/watchlist-summary",
            summary="No tool executor available.",
        )

    output = tool_executor.call("watchlist.summarize_deep", date=date, top=top)
    data = output.data
    if data is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/watchlist-summary",
            summary=output.summary,
            warnings=output.warnings,
        )

    watchlist_size = int(data.get("watchlist_size") or 0)
    if watchlist_size <= 0:
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title=f"/watchlist-summary — {date}",
            summary=output.summary,
            warnings=output.warnings,
        )

    top_candidates = list(data.get("top_candidates") or [])
    class_rows = _dict_rows(data.get("candidate_class_distribution"), "Class")
    setup_rows = _dict_rows(data.get("setup_distribution"), "Setup")
    sector_rows = _dict_rows(data.get("sector_distribution"), "Sector")
    risk_rows = _dict_rows(data.get("risk_flag_distribution"), "Risk")
    quality_rows = _dict_rows(data.get("quality_distribution"), "Quality")

    tables = [
        ResultTable(
            title="Candidate class distribution",
            columns=[ResultColumn("class", "Class"), ResultColumn("count", "Count")],
            rows=class_rows,
        ),
        ResultTable(
            title="Setup distribution",
            columns=[ResultColumn("setup", "Setup"), ResultColumn("count", "Count")],
            rows=setup_rows,
        ),
        ResultTable(
            title="Sector distribution",
            columns=[ResultColumn("sector", "Sector"), ResultColumn("count", "Count")],
            rows=sector_rows,
        ),
        ResultTable(
            title="Quality distribution",
            columns=[
                ResultColumn("quality", "Quality"),
                ResultColumn("count", "Count"),
            ],
            rows=quality_rows,
        ),
    ]
    if risk_rows:
        tables.append(
            ResultTable(
                title="Risk flag distribution",
                columns=[
                    ResultColumn("flag", "Risk flag"),
                    ResultColumn("count", "Count"),
                ],
                rows=risk_rows,
            )
        )

    candidate_rows = [
        [
            item.get("rank"),
            item.get("symbol", ""),
            _fmt_float(item.get("score")),
            item.get("candidate_class", ""),
            item.get("setup_type", ""),
            item.get("sector", ""),
            ", ".join(item.get("risk_flags", [])),
            item.get("data_quality_status", ""),
        ]
        for item in top_candidates
    ]
    if candidate_rows:
        tables.append(
            ResultTable(
                title="Top candidates",
                columns=[
                    ResultColumn("rank", "Rank"),
                    ResultColumn("symbol", "Symbol"),
                    ResultColumn("score", "Score"),
                    ResultColumn("class", "Class"),
                    ResultColumn("setup", "Setup"),
                    ResultColumn("sector", "Sector"),
                    ResultColumn("risk_flags", "Risk flags"),
                    ResultColumn("quality", "Quality"),
                ],
                rows=candidate_rows,
            )
        )

    strongest = [
        item.get("symbol", "") for item in top_candidates[:3] if item.get("symbol")
    ]
    near_confirmation = [
        item.get("symbol", "")
        for item in top_candidates
        if item.get("candidate_class") in {"WATCH_CANDIDATE", "STRONG_CANDIDATE"}
        and item.get("symbol")
    ]
    extended = [
        item.get("symbol", "")
        for item in top_candidates
        if (item.get("score") is not None and float(item.get("score")) < 0.5)
        and item.get("symbol")
    ]
    risk_flagged = [
        item.get("symbol", "")
        for item in top_candidates
        if item.get("risk_flags") and item.get("symbol")
    ]

    focus_lines = {
        "watchlist_size": watchlist_size,
        "next_session_focus": (
            f"Prioritize risk-flagged symbols for confirmation checks: {', '.join(risk_flagged)}"
            if risk_flagged
            else "No explicit risk-flagged names in top candidates."
        ),
        "strongest_names": ", ".join(strongest) if strongest else "—",
        "near_confirmation_names": ", ".join(near_confirmation[:5])
        if near_confirmation
        else "—",
        "extended_names": ", ".join(extended) if extended else "—",
    }

    panels = [
        ResultPanel(title="Research focus", content=focus_lines),
        ResultPanel(
            title="Top candidate groups",
            content={
                "risk_flagged": ", ".join(risk_flagged) if risk_flagged else "—",
                "strongest": ", ".join(strongest) if strongest else "—",
                "near_confirmation": ", ".join(near_confirmation[:5])
                if near_confirmation
                else "—",
                "extended": ", ".join(extended) if extended else "—",
            },
        ),
    ]

    return CommandResult(
        status=CommandStatus.PARTIAL if output.warnings else CommandStatus.SUCCESS,
        title=f"/watchlist-summary — {date}",
        summary=output.summary,
        tables=tables,
        panels=panels,
        artifacts=[
            ResultArtifact(
                name=f"watchlist.summarize_deep:{data.get('as_of_date') or date or 'latest'}",
                data=data,
            )
        ],
        metadata={
            "research_view": "watchlist_summary",
            "artifact_id": f"watchlist.summarize_deep:{data.get('as_of_date') or date or 'latest'}",
            "subject": "WATCHLIST",
            "as_of_date": data.get("as_of_date"),
            "workflow_status": "partial" if output.warnings else "complete",
            "missing_data": list(data.get("missing_data") or []),
            "artifact_refs": list(data.get("artifact_refs") or []),
        },
        warnings=output.warnings,
    )


def _requested_date(parsed: ParsedCommand) -> str | None:
    value = parsed.options.get("date")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--date requires an ISO date value.")
    return normalize_date(value)


def _top(parsed: ParsedCommand) -> int | None:
    value = parsed.options.get("top")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--top must be a positive integer.")
    try:
        top = int(value)
    except ValueError as exc:  # noqa: BLE001
        raise CommandValidationError("--top must be a positive integer.") from exc
    if top <= 0:
        raise CommandValidationError("--top must be a positive integer.")
    return top


def _dict_rows(raw: object, key_name: str) -> list[list[str | int]]:
    if not isinstance(raw, dict) or not raw:
        return []
    return [[str(key), int(value)] for key, value in _sorted_distribution(raw)]


def _sorted_distribution(raw: dict[str, int]) -> Sequence[tuple[str, int]]:
    return sorted(raw.items(), key=lambda item: (-item[1], str(item[0])))


def _fmt_float(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)
