"""Immutable, deterministic inventory of persisted sandbox artifacts."""

from __future__ import annotations

import json
import string
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Final, TypedDict, final

from typing_extensions import override

_SHA256_HEX_DIGITS: Final = frozenset(string.hexdigits)
_MANIFEST_PATH: Final = "manifest.json"


class _ManifestEntryPayload(TypedDict):
    byte_length: int
    media_type: str
    path: str
    sha256: str


class _ManifestPayload(TypedDict):
    entries: list[_ManifestEntryPayload]


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactManifestError(ValueError):
    """A manifest entry violates the canonical artifact inventory contract."""

    detail: str

    @override
    def __str__(self) -> str:
        return f"invalid sandbox artifact manifest: {self.detail}"


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactManifestEntry:
    """One canonical job-relative artifact and its immutable byte inventory."""

    path: str
    sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        _validate_path(self.path)
        _validate_digest(self.sha256)
        if self.byte_length < 0:
            raise SandboxArtifactManifestError("byte length must not be negative")
        if not self.media_type.strip():
            raise SandboxArtifactManifestError("media type must not be blank")

    def to_payload(self) -> _ManifestEntryPayload:
        """Return the fixed JSON-compatible representation of this entry."""

        return {
            "byte_length": self.byte_length,
            "media_type": self.media_type,
            "path": self.path,
            "sha256": self.sha256,
        }


@final
@dataclass(frozen=True, slots=True)
class SandboxArtifactManifest:
    """A deterministic immutable inventory that deliberately excludes itself."""

    entries: tuple[SandboxArtifactManifestEntry, ...]

    def __post_init__(self) -> None:
        paths = tuple(entry.path for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise SandboxArtifactManifestError(
                "entry paths must not contain duplicates"
            )

    def to_json_bytes(self) -> bytes:
        """Serialize entries with stable ordering and canonical UTF-8 JSON formatting."""

        payload: _ManifestPayload = {
            "entries": [
                entry.to_payload() for entry in sorted(self.entries, key=_entry_path)
            ]
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")


def _entry_path(entry: SandboxArtifactManifestEntry) -> str:
    return entry.path


def _validate_path(path_value: str) -> None:
    path = PurePosixPath(path_value)
    windows_path = PureWindowsPath(path_value)
    is_safe = (
        bool(path.parts)
        and not path.is_absolute()
        and not windows_path.is_absolute()
        and ".." not in path.parts
        and ".." not in windows_path.parts
        and path_value != "."
        and "\\" not in path_value
        and path.as_posix() == path_value
        and path_value != _MANIFEST_PATH
    )
    if not is_safe:
        raise SandboxArtifactManifestError(
            "path must be canonical, job-relative, and must not be manifest.json"
        )


def _validate_digest(digest: str) -> None:
    is_sha256 = len(digest) == 64 and all(
        character in _SHA256_HEX_DIGITS for character in digest
    )
    if not is_sha256:
        raise SandboxArtifactManifestError(
            "sha256 must be a 64-character hexadecimal digest"
        )
