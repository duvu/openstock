"""Query-backed artifact-reference construction."""

from __future__ import annotations


class ArtifactReferenceBuilder:
    """Collect unique logical refs only after persisted data is confirmed."""

    __slots__ = ("_refs", "_seen")

    def __init__(self) -> None:
        self._refs: list[str] = []
        self._seen: set[str] = set()

    def add_if_present(self, kind: str, key: str, exists: bool) -> None:
        """Add ``kind:key`` only when its backing query confirmed a row."""

        if not exists:
            return
        reference = f"{kind}:{key}"
        if reference in self._seen:
            return
        self._seen.add(reference)
        self._refs.append(reference)

    def build(self) -> list[str]:
        return list(self._refs)


__all__ = ["ArtifactReferenceBuilder"]
