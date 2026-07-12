from __future__ import annotations

import re
from pathlib import Path

from vnalpha.closed_loop.errors import ClosedLoopBoundaryError

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def validate_identifier(value: str, field: str = "identifier") -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ClosedLoopBoundaryError(f"invalid {field}")
    return value


def resolve_under(root: Path, candidate: Path, field: str = "path") -> Path:
    base = root.expanduser().resolve()
    path = candidate if candidate.is_absolute() else base / candidate
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ClosedLoopBoundaryError(f"{field} escapes the closed-loop root") from exc
    return resolved


def resolve_component(root: Path, parent: str, value: str, field: str) -> Path:
    component = validate_identifier(value, field)
    return resolve_under(root, Path(parent) / component, field)


def resolve_file(root: Path, parent: str, value: str, suffix: str, field: str) -> Path:
    component = validate_identifier(value, field)
    return resolve_under(root, Path(parent) / f"{component}{suffix}", field)


def ensure_tree_confined(root: Path, candidate: Path, field: str) -> Path:
    resolved = resolve_under(root, candidate, field)
    for entry in resolved.rglob("*"):
        resolve_under(resolved, entry, field)
    return resolved
