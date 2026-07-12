from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Final, TypeVar

JsonDict = dict[str, Any]
T = TypeVar("T")
WORKSPACE_SCHEMA_VERSION: Final[int] = 2


class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CORRUPT = "corrupt"
    TEMPORARY = "temporary"


def _to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_dict(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class WorkspaceArtifactRef:
    artifact_id: str
    artifact_type: str
    path: str
    summary: str
    created_at: str
    source_refs: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)
    pinned: bool = False

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> WorkspaceArtifactRef:
        return cls(
            artifact_id=payload["artifact_id"],
            artifact_type=payload["artifact_type"],
            path=payload["path"],
            summary=payload["summary"],
            created_at=payload["created_at"],
            source_refs=list(payload.get("source_refs", [])),
            metadata=dict(payload.get("metadata", {})),
            pinned=bool(payload.get("pinned", False)),
        )


@dataclass(frozen=True)
class WorkspaceInputRef:
    input_id: str
    input_kind: str
    summary: str
    redaction_status: str
    created_at: str
    source: str
    content: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> WorkspaceInputRef:
        return cls(
            input_id=payload["input_id"],
            input_kind=payload["input_kind"],
            summary=payload["summary"],
            redaction_status=payload["redaction_status"],
            created_at=payload["created_at"],
            source=payload["source"],
            content=payload.get("content"),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class WorkspaceTask:
    task_id: str
    text: str
    status: str
    priority: str
    created_at: str
    updated_at: str
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> WorkspaceTask:
        return cls(
            task_id=payload["task_id"],
            text=payload["text"],
            status=payload["status"],
            priority=payload["priority"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            source_refs=list(payload.get("source_refs", [])),
        )


@dataclass(frozen=True)
class WorkspaceState:
    workspace_id: str
    title: str
    status: str
    mode: str
    created_at: str
    updated_at: str
    schema_version: int = WORKSPACE_SCHEMA_VERSION
    active_date: str | None = None
    active_symbols: list[str] = field(default_factory=list)
    active_artifacts: list[WorkspaceArtifactRef] = field(default_factory=list)
    recent_inputs: list[WorkspaceInputRef] = field(default_factory=list)
    open_tasks: list[WorkspaceTask] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data_freshness: JsonDict = field(default_factory=dict)
    last_compacted_at: str | None = None
    context_size: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "workspace_id": self.workspace_id,
            "title": self.title,
            "status": self.status,
            "mode": self.mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
            "active_date": self.active_date,
            "active_symbols": list(self.active_symbols),
            "active_artifacts": [item.to_dict() for item in self.active_artifacts],
            "recent_inputs": [item.to_dict() for item in self.recent_inputs],
            "open_tasks": [item.to_dict() for item in self.open_tasks],
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "data_freshness": dict(self.data_freshness),
            "last_compacted_at": self.last_compacted_at,
            "context_size": dict(self.context_size),
        }

    @classmethod
    def from_dict(cls, payload: JsonDict) -> WorkspaceState:
        status = str(payload["status"])
        WorkspaceStatus(status)
        return cls(
            workspace_id=payload["workspace_id"],
            title=payload["title"],
            status=status,
            mode=payload["mode"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            schema_version=WORKSPACE_SCHEMA_VERSION,
            active_date=payload.get("active_date"),
            active_symbols=list(payload.get("active_symbols", [])),
            active_artifacts=[
                WorkspaceArtifactRef.from_dict(item)
                for item in payload.get("active_artifacts", [])
            ],
            recent_inputs=[
                WorkspaceInputRef.from_dict(item)
                for item in payload.get("recent_inputs", [])
            ],
            open_tasks=[
                WorkspaceTask.from_dict(item) for item in payload.get("open_tasks", [])
            ],
            assumptions=list(payload.get("assumptions", [])),
            warnings=list(payload.get("warnings", [])),
            errors=list(payload.get("errors", [])),
            data_freshness=dict(payload.get("data_freshness", {})),
            last_compacted_at=payload.get("last_compacted_at"),
            context_size=dict(payload.get("context_size", {})),
        )


@dataclass(frozen=True)
class WorkspaceStatusReport:
    workspace_id: str
    title: str
    mode: str
    status: str
    active_date: str | None = None
    active_symbols: list[str] = field(default_factory=list)
    open_tasks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    last_updated_at: str | None = None
    last_compacted_at: str | None = None
    context_size: JsonDict = field(default_factory=dict)
    stale_artifacts: list[str] = field(default_factory=list)
    suggested_action: str | None = None
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> WorkspaceStatusReport:
        return cls(
            workspace_id=payload["workspace_id"],
            title=payload["title"],
            mode=payload["mode"],
            status=payload["status"],
            active_date=payload.get("active_date"),
            active_symbols=list(payload.get("active_symbols", [])),
            open_tasks=list(payload.get("open_tasks", [])),
            warnings=list(payload.get("warnings", [])),
            errors=list(payload.get("errors", [])),
            last_updated_at=payload.get("last_updated_at"),
            last_compacted_at=payload.get("last_compacted_at"),
            context_size=dict(payload.get("context_size", {})),
            stale_artifacts=list(payload.get("stale_artifacts", [])),
            suggested_action=payload.get("suggested_action"),
            source_refs=list(payload.get("source_refs", [])),
        )


@dataclass(frozen=True)
class WorkspaceResumeSummary:
    workspace_id: str
    title: str
    mode: str
    status: str
    active_date: str | None = None
    active_symbols: list[str] = field(default_factory=list)
    open_task_count: int = 0
    last_compacted_at: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return _to_dict(self)


@dataclass(frozen=True)
class CompactionResult:
    workspace_id: str
    compact_path: str
    before_size: JsonDict = field(default_factory=dict)
    after_size: JsonDict = field(default_factory=dict)
    preserved_items: list[str] = field(default_factory=list)
    archived_items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: str | None = None

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> CompactionResult:
        return cls(
            workspace_id=payload["workspace_id"],
            compact_path=payload["compact_path"],
            before_size=dict(payload.get("before_size", {})),
            after_size=dict(payload.get("after_size", {})),
            preserved_items=list(payload.get("preserved_items", [])),
            archived_items=list(payload.get("archived_items", [])),
            warnings=list(payload.get("warnings", [])),
            generated_at=payload.get("generated_at"),
        )


@dataclass(frozen=True)
class CleanPlan:
    workspace_id: str
    dry_run: bool
    archive_first: bool
    keep: list[str] = field(default_factory=list)
    archive: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    needs_confirmation: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> CleanPlan:
        return cls(
            workspace_id=payload["workspace_id"],
            dry_run=bool(payload["dry_run"]),
            archive_first=bool(payload["archive_first"]),
            keep=list(payload.get("keep", [])),
            archive=list(payload.get("archive", [])),
            remove=list(payload.get("remove", [])),
            needs_confirmation=list(payload.get("needs_confirmation", [])),
            protected=list(payload.get("protected", [])),
            summary=payload.get("summary"),
        )


@dataclass(frozen=True)
class CleanResult:
    workspace_id: str
    dry_run: bool
    archived: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: str | None = None
    plan: CleanPlan | None = None

    def to_dict(self) -> JsonDict:
        payload = _to_dict(self)
        if self.plan is not None:
            payload["plan"] = self.plan.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: JsonDict) -> CleanResult:
        plan_payload = payload.get("plan")
        return cls(
            workspace_id=payload["workspace_id"],
            dry_run=bool(payload["dry_run"]),
            archived=list(payload.get("archived", [])),
            removed=list(payload.get("removed", [])),
            kept=list(payload.get("kept", [])),
            warnings=list(payload.get("warnings", [])),
            generated_at=payload.get("generated_at"),
            plan=CleanPlan.from_dict(plan_payload) if plan_payload else None,
        )


@dataclass(frozen=True)
class ExportResult:
    workspace_id: str
    bundle_dir: str
    manifest_path: str
    exported_files: list[str] = field(default_factory=list)
    checksums: JsonDict = field(default_factory=dict)
    generated_at: str | None = None

    def to_dict(self) -> JsonDict:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, payload: JsonDict) -> ExportResult:
        return cls(
            workspace_id=payload["workspace_id"],
            bundle_dir=payload["bundle_dir"],
            manifest_path=payload["manifest_path"],
            exported_files=list(payload.get("exported_files", [])),
            checksums=dict(payload.get("checksums", {})),
            generated_at=payload.get("generated_at"),
        )
