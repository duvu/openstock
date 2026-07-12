from __future__ import annotations

from pathlib import Path

from vnalpha.closed_loop.service import ClosedLoopService
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.observability.context import resolve_log_root


def service() -> ClosedLoopService:
    return ClosedLoopService(ClosedLoopStore(resolve_log_root()))


def invalid(summary: str):
    from vnalpha.commands.models import CommandResult

    return CommandResult(
        status="VALIDATION_ERROR", title="Closed-loop command", summary=summary
    )


def failed(title: str, summary: str):
    from vnalpha.commands.models import CommandResult

    return CommandResult(status="FAILED", title=title, summary=summary)


def report_payload(report) -> dict:
    return {
        "artifact_id": report.artifact_id,
        "correlation_id": report.correlation_id,
        "passed": report.passed,
        "checks": [check.model_dump(mode="json") for check in report.checks],
    }


def path_value(value) -> Path | None:
    return value if isinstance(value, Path) else None
