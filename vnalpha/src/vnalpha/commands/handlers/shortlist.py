from __future__ import annotations

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


def handle_shortlist(
    parsed: ParsedCommand,
    conn=None,
    **kwargs,
) -> CommandResult:
    if conn is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/shortlist",
            summary="No database connection.",
        )

    validate_command_input(
        parsed,
        {"date", "limit", "setup", "sector", "min-score", "min_score"},
        maximum_positionals=0,
    )
    date = _requested_date(parsed)
    limit = _limit(parsed)
    setup_filter = _normalize_text_option(parsed.options.get("setup"))
    sector_filter = _normalize_text_option(parsed.options.get("sector"))
    min_score = _min_score(parsed)

    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/shortlist",
            summary="No tool executor available.",
        )

    output = tool_executor.call(
        "shortlist.generate",
        date=date,
        top=limit,
        min_score=min_score,
    )
    data = output.data
    if data is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title="/shortlist",
            summary=output.summary,
            warnings=output.warnings,
        )

    candidates = list(data.get("shortlist") or [])
    method = data.get("methodology") if isinstance(data.get("methodology"), dict) else {}
    warnings = list(output.warnings or [])

    candidates, filter_applied = _filter_candidates(
        candidates, setup_filter=setup_filter, sector_filter=sector_filter
    )
    if filter_applied:
        warnings.append(
            "Post-filtered shortlist by setup/sector for this command scope."
        )

    if not candidates:
        scope = _format_empty_summary(date, setup_filter, sector_filter, output.summary)
        return CommandResult(
            status=CommandStatus.EMPTY_RESULT,
            title=f"/shortlist — {date}",
            summary=scope,
            warnings=warnings,
        )

    rows = [
        [
            item.get("symbol", ""),
            _fmt_float(item.get("shortlist_score")),
            _fmt_float(item.get("candidate_score")),
            item.get("setup_type", ""),
            item.get("sector", ""),
            ", ".join(item.get("risk_flags", []) or []),
            _fmt_float(item.get("risk_quality_score")),
            "; ".join(item.get("why_shortlisted", []))
            if isinstance(item.get("why_shortlisted"), list)
            else str(item.get("why_shortlisted", "")),
            "; ".join(item.get("why_not_immediate", []))
            if isinstance(item.get("why_not_immediate"), list)
            else str(item.get("why_not_immediate", "")),
        ]
        for item in candidates
    ]

    table = ResultTable(
        title="Research shortlist",
        columns=[
            ResultColumn("symbol", "Symbol"),
            ResultColumn("shortlist_score", "Shortlist Score"),
            ResultColumn("candidate_score", "Candidate Score"),
            ResultColumn("setup", "Setup"),
            ResultColumn("sector", "Sector"),
            ResultColumn("risk_flags", "Risk Flags"),
            ResultColumn("risk_quality", "Risk Quality"),
            ResultColumn("why_shortlisted", "Why shortlisted"),
            ResultColumn("why_not_immediate", "Why restrained"),
        ],
        rows=rows,
    )

    panel_lines = {
        "methodology_version": method.get("version", "shortlist-v1"),
        "formula": method.get("formula", "0.75*candidate_score + 0.15*sector_score + ..."),
        "min_score": method.get("min_score", 0.0),
        "considered_count": data.get("considered_count", len(candidates)),
        "method_focus": (
            "Highest shortlist scores remain research prioritization only, not execution."
        ),
    }
    return CommandResult(
        status=CommandStatus.PARTIAL if warnings else CommandStatus.SUCCESS,
        title=f"/shortlist — {date}",
        summary=output.summary,
        tables=[table],
        panels=[ResultPanel(title="Shortlist methodology", content=panel_lines)],
        artifacts=[
            ResultArtifact(
                name=f"shortlist.generate:{data.get('as_of_date') or date or 'latest'}",
                data=data,
            )
        ],
        metadata={
            "research_view": "shortlist",
            "artifact_id": f"shortlist.generate:{data.get('as_of_date') or date or 'latest'}",
            "subject": "SHORTLIST",
            "as_of_date": data.get("as_of_date"),
            "workflow_status": "partial" if warnings else "complete",
            "missing_data": list(data.get("missing_data") or []),
            "artifact_refs": list(data.get("artifact_refs") or []),
        },
        warnings=warnings,
    )


def _requested_date(parsed: ParsedCommand) -> str | None:
    value = parsed.options.get("date")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--date requires an ISO date value.")
    return normalize_date(value)


def _limit(parsed: ParsedCommand) -> int | None:
    return _positive_integer(
        parsed.options.get("limit"), "--limit must be a positive integer."
    )


def _min_score(parsed: ParsedCommand) -> float | None:
    value = parsed.options.get("min-score")
    if value is None:
        value = parsed.options.get("min_score")
    if value is None:
        return None
    return _positive_float(
        value,
        "--min-score must be a non-negative number.",
    )


def _normalize_text_option(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _filter_candidates(
    items: list[dict],
    setup_filter: str | None,
    sector_filter: str | None,
) -> tuple[list[dict], bool]:
    if setup_filter is None and sector_filter is None:
        return items, False

    filtered = []
    for item in items:
        if setup_filter and str(item.get("setup_type") or "").upper() != setup_filter:
            continue
        if sector_filter and str(item.get("sector") or "").upper() != sector_filter:
            continue
        filtered.append(item)

    return filtered, True


def _positive_integer(value: object, message: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError(message)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:  # noqa: BLE001
        raise CommandValidationError(message) from exc
    if parsed <= 0:
        raise CommandValidationError(message)
    return parsed


def _positive_float(value: object, message: str) -> float:
    if isinstance(value, bool):
        raise CommandValidationError(message)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:  # noqa: BLE001
        raise CommandValidationError(message) from exc
    if parsed < 0.0:
        raise CommandValidationError(message)
    return parsed


def _fmt_float(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def _format_empty_summary(
    date: str | None,
    setup_filter: str | None,
    sector_filter: str | None,
    default_summary: str | None,
) -> str:
    if setup_filter or sector_filter:
        fragments: list[str] = []
        if setup_filter:
            fragments.append(f"setup={setup_filter}")
        if sector_filter:
            fragments.append(f"sector={sector_filter}")
        return (
            f"No shortlist candidates matched filters ({', '.join(fragments)})"
            + (f" on {date}" if date else "")
            + "."
        )
    return default_summary or "No shortlist candidates available."
