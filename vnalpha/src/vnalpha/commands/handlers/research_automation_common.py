from __future__ import annotations

from datetime import date

from vnalpha.commands.errors import CommandValidationError
from vnalpha.research_automation.models import ResearchArtifact


def parse_optional_date(value: str | bool | None, option: str) -> date | None:
    if value is None:
        return None
    if value is True:
        raise CommandValidationError(f"--{option} requires YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandValidationError(f"--{option} requires YYYY-MM-DD.") from exc


def positive_integer(value: str | bool | None, option: str, default: int) -> int:
    if value is None:
        return default
    if value is True:
        raise CommandValidationError(f"--{option} requires a positive integer.")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CommandValidationError(
            f"--{option} requires a positive integer."
        ) from exc
    if parsed <= 0:
        raise CommandValidationError(f"--{option} requires a positive integer.")
    return parsed


def workflow_warnings(artifact: ResearchArtifact) -> list[str]:
    quality_warnings = artifact.quality_status.get("warnings", ())
    return list(
        dict.fromkeys([*(str(item) for item in quality_warnings), *artifact.caveats])
    )


__all__ = ["parse_optional_date", "positive_integer", "workflow_warnings"]
