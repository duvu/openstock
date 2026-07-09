from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.cleaning import clean_workspace
from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace, get_status


def handle_context(parsed: ParsedCommand, **kwargs) -> CommandResult:
    subcommand = parsed.positional[0].lower() if parsed.positional else "status"

    if subcommand == "status":
        report = get_status()
        return CommandResult(
            status="SUCCESS",
            title="/context status",
            summary=(
                f"Workspace {report.workspace_id} is {report.status}. "
                f"Mode: {report.mode}."
            ),
            panels=[
                ResultPanel(
                    title="Workspace Health",
                    content={
                        "workspace_id": report.workspace_id,
                        "title": report.title,
                        "status": report.status,
                        "mode": report.mode,
                        "active_date": report.active_date,
                        "active_symbols": ", ".join(report.active_symbols)
                        if report.active_symbols
                        else "",
                        "open_tasks": len(report.open_tasks),
                        "warnings": len(report.warnings),
                        "errors": len(report.errors),
                        "last_updated_at": report.last_updated_at,
                        "last_compacted_at": report.last_compacted_at,
                        "context_size": report.context_size,
                        "suggested_action": report.suggested_action,
                    },
                )
            ],
            warnings=list(report.warnings),
        )

    if subcommand == "compact":
        workspace = get_or_create_latest_workspace()
        result = compact_workspace(workspace.workspace_id)
        return CommandResult(
            status="SUCCESS",
            title="/context compact",
            summary=(
                f"Wrote {result.compact_path} for workspace {result.workspace_id}."
            ),
            panels=[
                ResultPanel(
                    title="Compaction",
                    content={
                        "workspace_id": result.workspace_id,
                        "compact_path": result.compact_path,
                        "summary_lines": result.after_size.get("summary_lines"),
                        "generated_at": result.generated_at,
                    },
                )
            ],
            warnings=list(result.warnings),
        )

    if subcommand == "clean":
        workspace = get_or_create_latest_workspace()
        dry_run = parsed.options.get("dry-run", False) is True
        result = clean_workspace(workspace.workspace_id, dry_run=dry_run)
        panel_title = "Clean Plan" if result.dry_run else "Clean Result"
        summary = (
            f"Dry run clean plan for workspace {result.workspace_id}."
            if result.dry_run
            else f"Cleaned workspace {result.workspace_id}."
        )
        return CommandResult(
            status="SUCCESS",
            title="/context clean",
            summary=summary,
            panels=[
                ResultPanel(
                    title=panel_title,
                    content={
                        "workspace_id": result.workspace_id,
                        "dry_run": result.dry_run,
                        "archive_first": result.plan.archive_first if result.plan else False,
                        "keep": result.plan.keep if result.plan else [],
                        "archive": result.plan.archive if result.plan else [],
                        "remove": result.plan.remove if result.plan else [],
                        "needs_confirmation": result.plan.needs_confirmation if result.plan else [],
                        "protected": result.plan.protected if result.plan else [],
                        "archived": result.archived,
                        "removed": result.removed,
                        "generated_at": result.generated_at,
                    },
                )
            ],
            warnings=list(result.warnings),
        )

    raise CommandValidationError(
        f"Unsupported /context subcommand: {subcommand}. Supported: status, compact, clean."
    )
