from __future__ import annotations

import importlib.metadata
import os
import sys
from dataclasses import dataclass
from pathlib import Path

_SYSTEM_RELEASE_PATH = Path("/opt/vnalpha/RELEASE")


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    package_version: str
    source_commit: str | None = None
    tree_state: str | None = None

    @property
    def display(self) -> str:
        parts = [f"vnalpha-{self.package_version}"]
        if self.source_commit:
            parts.append(f"commit={self.source_commit}")
        if self.tree_state:
            parts.append(f"tree={self.tree_state}")
        return ";".join(parts)


def resolve_software_identity(release_path: Path | None = None) -> SoftwareIdentity:
    resolved_release_path = release_path or _default_release_path()
    values: dict[str, str] = {}
    try:
        for line in resolved_release_path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and value.strip():
                values[key.strip().lower()] = value.strip()
    except OSError:
        pass

    version = values.get("version")
    if not version:
        try:
            version = importlib.metadata.version("vnalpha")
        except importlib.metadata.PackageNotFoundError:
            version = "dev"

    source_commit = values.get("commit")
    if source_commit and not source_commit.strip("0"):
        source_commit = None
    return SoftwareIdentity(
        package_version=version,
        source_commit=source_commit,
        tree_state=values.get("tree_state"),
    )


def _default_release_path() -> Path:
    configured_path = os.getenv("OPENSTOCK_RELEASE_FILE")
    if configured_path:
        return Path(configured_path)
    runtime_release_path = Path(sys.prefix).resolve().parent / "RELEASE"
    if runtime_release_path.is_file():
        return runtime_release_path
    return _SYSTEM_RELEASE_PATH


__all__ = ["SoftwareIdentity", "resolve_software_identity"]
