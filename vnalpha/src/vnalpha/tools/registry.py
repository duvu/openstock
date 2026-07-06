"""LocalToolRegistry — allowlisted tools only."""

from __future__ import annotations

from typing import Any, Callable

from vnalpha.tools.errors import ToolNotFoundError, ToolPermissionError
from vnalpha.tools.models import (
    FORBIDDEN_PERMISSIONS,
    ToolOutput,
    ToolPermission,
    ToolSpec,
)


class LocalToolRegistry:
    """Registry of Phase 5.8 local research tools.

    Only explicitly registered tools may be called.
    Forbidden permissions (NETWORK_ACCESS, PYTHON_EXECUTION, etc.) are blocked
    at registration time.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._impls: dict[str, Callable[..., ToolOutput]] = {}

    def register(
        self,
        spec: ToolSpec,
        impl: Callable[..., ToolOutput],
    ) -> None:
        """Register a tool spec + implementation.

        Raises ValueError if the permission is forbidden or the name is a duplicate.
        """
        if spec.permission.value in FORBIDDEN_PERMISSIONS:
            raise ValueError(
                f"Tool '{spec.name}' attempted to use forbidden permission "
                f"'{spec.permission.value}'."
            )
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered.")
        self._tools[spec.name] = spec
        self._impls[spec.name] = impl

    def call(
        self,
        name: str,
        granted_permissions: set[ToolPermission],
        **kwargs: Any,
    ) -> ToolOutput:
        """Call a registered tool with permission check.

        Raises ToolNotFoundError or ToolPermissionError on access violations.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        spec = self._tools[name]
        if spec.permission not in granted_permissions:
            raise ToolPermissionError(name, spec.permission.value)
        return self._impls[name](**kwargs)

    def get_spec(self, name: str) -> ToolSpec:
        """Return the ToolSpec for a registered tool."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def names(self) -> list[str]:
        """Return all registered tool names."""
        return sorted(self._tools.keys())
