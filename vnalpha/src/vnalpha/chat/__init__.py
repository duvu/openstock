"""vnalpha.chat — public API for the chat workspace module."""

from vnalpha.chat.context import (
    ChatContext,
    build_context_prompt_prefix,
    resolve_entity_reference,
    update_context_from_command,
)
from vnalpha.chat.errors import (
    MAX_PUBLIC_ERROR_CHARS,
    ChatError,
    ChatErrorKind,
    error_to_message_type,
    format_refusal,
    format_runtime_error,
    format_tool_failure,
    format_validation_error,
    sanitize_public_error,
)
from vnalpha.chat.events import (
    AssistantStage,
    AssistantStageEvent,
    format_stage_event,
    stage_to_style,
)
from vnalpha.chat.safety import (
    PermissionState,
    filter_safe_tools,
    get_permission_state,
    is_tool_allowed_in_chat,
    validate_tool_call,
)

__all__ = [
    "ChatContext",
    "MAX_PUBLIC_ERROR_CHARS",
    "build_context_prompt_prefix",
    "resolve_entity_reference",
    "update_context_from_command",
    "ChatError",
    "ChatErrorKind",
    "error_to_message_type",
    "format_refusal",
    "format_runtime_error",
    "format_tool_failure",
    "format_validation_error",
    "sanitize_public_error",
    "AssistantStage",
    "AssistantStageEvent",
    "format_stage_event",
    "stage_to_style",
    "PermissionState",
    "filter_safe_tools",
    "get_permission_state",
    "is_tool_allowed_in_chat",
    "validate_tool_call",
]
