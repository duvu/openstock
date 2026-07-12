from __future__ import annotations

from vnalpha.workspace_context.integration import (
    build_workspace_context_prompt_prefix,
    render_context_markdown,
)
from vnalpha.workspace_context.lifecycle import (
    WorkspaceLifecycleError,
    check_lifecycle_invariants,
    create_workspace,
    reactivate_workspace,
    resume_workspace,
)
from vnalpha.workspace_context.migration import (
    LegacyWorkspaceNotFoundError,
    WorkspaceMigrationConflictError,
    WorkspaceMigrationResult,
    detect_legacy_workspace_roots,
    migrate_legacy_workspaces,
)
from vnalpha.workspace_context.models import (
    CleanPlan,
    CleanResult,
    CompactionResult,
    ExportResult,
    WorkspaceArtifactRef,
    WorkspaceInputRef,
    WorkspaceState,
    WorkspaceStatus,
    WorkspaceStatusReport,
    WorkspaceTask,
)
from vnalpha.workspace_context.storage import (
    load_workspace_state,
    save_workspace_state,
)

__all__ = [
    "CleanPlan",
    "CleanResult",
    "CompactionResult",
    "ExportResult",
    "WorkspaceArtifactRef",
    "WorkspaceInputRef",
    "WorkspaceState",
    "WorkspaceStatus",
    "WorkspaceStatusReport",
    "WorkspaceTask",
    "WorkspaceLifecycleError",
    "check_lifecycle_invariants",
    "LegacyWorkspaceNotFoundError",
    "WorkspaceMigrationConflictError",
    "WorkspaceMigrationResult",
    "build_workspace_context_prompt_prefix",
    "create_workspace",
    "detect_legacy_workspace_roots",
    "load_workspace_state",
    "migrate_legacy_workspaces",
    "reactivate_workspace",
    "render_context_markdown",
    "resume_workspace",
    "save_workspace_state",
]
