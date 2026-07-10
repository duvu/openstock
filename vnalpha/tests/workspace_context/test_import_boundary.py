from __future__ import annotations

import vnalpha.workspace_context as workspace_context
from vnalpha.workspace_context import (
    WorkspaceState,
    build_workspace_context_prompt_prefix,
    create_workspace,
    load_workspace_state,
    render_context_markdown,
    resume_workspace,
    save_workspace_state,
)
from vnalpha.workspace_context.integration import (
    build_workspace_context_prompt_prefix as integration_build_prompt_prefix,
)
from vnalpha.workspace_context.integration import (
    render_context_markdown as integration_render_context_markdown,
)
from vnalpha.workspace_context.lifecycle import (
    create_workspace as lifecycle_create_workspace,
)
from vnalpha.workspace_context.lifecycle import (
    resume_workspace as lifecycle_resume_workspace,
)
from vnalpha.workspace_context.models import WorkspaceState as ModelWorkspaceState
from vnalpha.workspace_context.storage import (
    load_workspace_state as storage_load_workspace_state,
)
from vnalpha.workspace_context.storage import (
    save_workspace_state as storage_save_workspace_state,
)


def test_package_exports_workspace_context_boundary() -> None:
    assert workspace_context.WorkspaceState is WorkspaceState is ModelWorkspaceState
    assert (
        workspace_context.load_workspace_state
        is load_workspace_state
        is storage_load_workspace_state
    )
    assert (
        workspace_context.save_workspace_state
        is save_workspace_state
        is storage_save_workspace_state
    )
    assert (
        workspace_context.create_workspace
        is create_workspace
        is lifecycle_create_workspace
    )
    assert (
        workspace_context.resume_workspace
        is resume_workspace
        is lifecycle_resume_workspace
    )
    assert (
        workspace_context.build_workspace_context_prompt_prefix
        is build_workspace_context_prompt_prefix
        is integration_build_prompt_prefix
    )
    assert (
        workspace_context.render_context_markdown
        is render_context_markdown
        is integration_render_context_markdown
    )
