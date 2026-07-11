"""Typed IDs and opaque logical fixture-URI parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NewType

ClaimId = NewType("ClaimId", str)
FactId = NewType("FactId", str)
ArtifactId = NewType("ArtifactId", str)

_FIXTURE_URI = re.compile(
    r"fixture://(?P<authority>[A-Za-z][A-Za-z0-9_-]*)/"
    r"(?P<logical_name>[A-Za-z][A-Za-z0-9_.-]*)\Z"
)
_LOGICAL_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z")


class InvalidFixtureUriError(ValueError):
    """Raised when an artifact identity is not a safe logical fixture URI."""


class InvalidLogicalIdentifierError(ValueError):
    """Raised when a claim or fact identity is not safe lower snake case."""


@dataclass(frozen=True, slots=True)
class FixtureUri:
    """Parsed logical fixture identity with no filesystem semantics."""

    value: ArtifactId
    authority: str
    logical_name: str


def parse_fixture_uri(value: ArtifactId) -> FixtureUri:
    """Parse a fixture URI while rejecting paths, traversal, and query syntax."""

    match = _FIXTURE_URI.fullmatch(value)
    if match is None:
        raise InvalidFixtureUriError(f"invalid fixture URI: {value}")
    return FixtureUri(
        value=value,
        authority=match.group("authority"),
        logical_name=match.group("logical_name"),
    )


def parse_logical_identifier(value: str) -> str:
    """Validate a non-empty lower-snake-case claim or fact identity."""

    if _LOGICAL_IDENTIFIER.fullmatch(value) is None:
        raise InvalidLogicalIdentifierError(f"invalid logical identifier: {value}")
    return value
