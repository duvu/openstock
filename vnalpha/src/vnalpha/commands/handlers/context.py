from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.workspace_context.cleaning import clean_workspace
from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.export import export_workspace
from vnalpha.workspace_context.lifecycle import (
    get_or_create_latest_workspace,
    get_resume_summary,
    get_status,
    list_workspaces,
    new_workspace,
)


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
        llm_client = kwargs.get("llm_client")
        if parsed.options.get("llm", False) is True and llm_client is None:
            from vnalpha.assistant.gateway import LLMGatewayClient

            llm_client = LLMGatewayClient()
        result = compact_workspace(workspace.workspace_id, llm_client=llm_client)
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
                        "llm_requested": parsed.options.get("llm", False) is True,
                        "generated_at": result.generated_at,
                    },
                )
            ],
            warnings=list(result.warnings),
        )

    if subcommand == "clean":
        workspace = get_or_create_latest_workspace()
        dry_run = parsed.options.get("execute", False) is not True
        resolved_errors = parsed.options.get("resolved-errors", False) is True
        result = clean_workspace(
            workspace.workspace_id,
            dry_run=dry_run,
            resolved_errors=resolved_errors,
        )
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
                        "archive_first": result.plan.archive_first
                        if result.plan
                        else False,
                        "keep": result.plan.keep if result.plan else [],
                        "archive": result.plan.archive if result.plan else [],
                        "remove": result.plan.remove if result.plan else [],
                        "needs_confirmation": result.plan.needs_confirmation
                        if result.plan
                        else [],
                        "protected": result.plan.protected if result.plan else [],
                        "archived": result.archived,
                        "removed": result.removed,
                        "generated_at": result.generated_at,
                    },
                )
            ],
            warnings=list(result.warnings),
        )

    if subcommand == "new":
        workspace = new_workspace(
            no_compact=parsed.options.get("no-compact", False) is True
        )
        return CommandResult(
            status="SUCCESS",
            title="/context new",
            summary=f"Started workspace {workspace.workspace_id}.",
            panels=[
                ResultPanel(
                    title="New Workspace",
                    content={
                        "workspace_id": workspace.workspace_id,
                        "title": workspace.title,
                        "status": workspace.status,
                        "mode": workspace.mode,
                        "created_at": workspace.created_at,
                    },
                )
            ],
        )

    if subcommand == "resume":
        workspace_id = parsed.positional[1] if len(parsed.positional) > 1 else None
        summary = get_resume_summary(workspace_id=workspace_id)
        return CommandResult(
            status="SUCCESS",
            title="/context resume",
            summary=f"Resumed workspace {summary.workspace_id}.",
            panels=[
                ResultPanel(
                    title="Resume Summary",
                    content={
                        "workspace_id": summary.workspace_id,
                        "title": summary.title,
                        "status": summary.status,
                        "mode": summary.mode,
                        "active_date": summary.active_date,
                        "active_symbols": list(summary.active_symbols),
                        "open_task_count": summary.open_task_count,
                        "last_compacted_at": summary.last_compacted_at,
                    },
                )
            ],
            warnings=list(summary.warnings),
        )

    if subcommand == "list":
        workspaces = list_workspaces()
        return CommandResult(
            status="SUCCESS",
            title="/context list",
            summary=f"{len(workspaces)} workspace(s) available.",
            panels=[
                ResultPanel(
                    title="Workspaces",
                    content={
                        "count": len(workspaces),
                        "workspaces": [
                            {
                                "workspace_id": workspace.workspace_id,
                                "title": workspace.title,
                                "status": workspace.status,
                                "mode": workspace.mode,
                                "updated_at": workspace.updated_at,
                            }
                            for workspace in workspaces
                        ],
                    },
                )
            ],
        )

    if subcommand == "export":
        workspace_id = parsed.positional[1] if len(parsed.positional) > 1 else None
        workspace = get_or_create_latest_workspace() if workspace_id is None else None
        result = export_workspace(workspace_id or workspace.workspace_id)
        return CommandResult(
            status="SUCCESS",
            title="/context export",
            summary=f"Exported workspace {result.workspace_id}.",
            panels=[
                ResultPanel(
                    title="Workspace Export",
                    content={
                        "workspace_id": result.workspace_id,
                        "bundle_dir": result.bundle_dir,
                        "manifest_path": result.manifest_path,
                        "exported_files": list(result.exported_files),
                        "generated_at": result.generated_at,
                    },
                )
            ],
        )

    raise CommandValidationError(
        "Unsupported /context subcommand: "
        f"{subcommand}. Supported: status, compact, clean, new, resume, list, export."
    )
